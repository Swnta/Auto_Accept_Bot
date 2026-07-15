"""Resolution-aware Accept-button detection for different screens / Dota UI scales."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass(frozen=True)
class MatchResult:
    x: int
    y: int
    width: int
    height: int
    confidence: float

    @property
    def center(self) -> tuple[int, int]:
        return self.x + self.width // 2, self.y + self.height // 2


class TemplateMatcher:
    """
    Find the green «ПРИНЯТЬ» button across resolutions:

    1) Green HSV ROI candidates (aspect-filtered) + template score
    2) Coarse search on a downscaled frame with button sizes relative to screen height
    3) Fine refine around the best coarse hit at full resolution
    """

    # Relative to screen height:
    # - fullscreen UI usually ~4–10%
    # - windowed 720p/1080p on a 4K monitor can be much smaller (~1.5–3%)
    MIN_H_FRAC = 0.014
    MAX_H_FRAC = 0.16
    ASPECT_MIN = 2.6
    ASPECT_MAX = 8.0
    COARSE_MAX_W = 1600
    THRESH_ROI = 0.58
    THRESH_COARSE = 0.60
    THRESH_FINE = 0.64

    def __init__(self, template_path: Path, threshold: float = 0.68) -> None:
        self.threshold = threshold
        self.path = Path(template_path)
        raw = cv2.imread(str(self.path), cv2.IMREAD_COLOR)
        if raw is None:
            raise FileNotFoundError(f"Cannot load template: {self.path}")
        self._template = self._autocrop(raw)
        self._template_gray = cv2.cvtColor(self._template, cv2.COLOR_BGR2GRAY)
        self._template_edges = cv2.Canny(self._template_gray, 60, 160)
        self._th0, self._tw0 = self._template_gray.shape[:2]
        self._aspect = self._tw0 / max(1, self._th0)
        self._hsv_lo, self._hsv_hi = self._estimate_green_range(self._template)

    @staticmethod
    def _autocrop(img: np.ndarray, pad: int = 2) -> np.ndarray:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, 18, 255, cv2.THRESH_BINARY)
        coords = cv2.findNonZero(mask)
        if coords is None:
            return img
        x, y, w, h = cv2.boundingRect(coords)
        x = max(0, x - pad)
        y = max(0, y - pad)
        w = min(img.shape[1] - x, w + 2 * pad)
        h = min(img.shape[0] - y, h + 2 * pad)
        if w < 8 or h < 8:
            return img
        return img[y : y + h, x : x + w]

    @staticmethod
    def _estimate_green_range(template_bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        hsv = cv2.cvtColor(template_bgr, cv2.COLOR_BGR2HSV)
        # Ignore almost-black / almost-white pixels; keep button body
        mask = cv2.inRange(hsv, (25, 25, 15), (100, 255, 200))
        if cv2.countNonZero(mask) < 30:
            # Fallback: typical Dota accept greens
            return np.array([28, 35, 15], np.uint8), np.array([95, 255, 190], np.uint8)
        mean = cv2.mean(hsv, mask=mask)[:3]
        h, s, v = mean
        lo = np.array(
            [max(0, int(h - 22)), max(20, int(s * 0.35)), max(10, int(v * 0.35))],
            np.uint8,
        )
        hi = np.array(
            [min(179, int(h + 22)), 255, min(255, int(v * 2.4 + 40))],
            np.uint8,
        )
        return lo, hi

    def _score_patch(self, patch_bgr: np.ndarray, tw: int, th: int) -> float:
        if patch_bgr.size == 0 or tw < 12 or th < 8:
            return 0.0
        gray = cv2.cvtColor(patch_bgr, cv2.COLOR_BGR2GRAY)
        templ = cv2.resize(
            self._template_gray,
            (tw, th),
            interpolation=cv2.INTER_AREA if tw < self._tw0 else cv2.INTER_CUBIC,
        )
        edges_t = cv2.resize(
            self._template_edges,
            (tw, th),
            interpolation=cv2.INTER_AREA if tw < self._tw0 else cv2.INTER_CUBIC,
        )
        if gray.shape[0] < th or gray.shape[1] < tw:
            return 0.0
        # Center-crop / exact size
        if gray.shape[0] != th or gray.shape[1] != tw:
            gray = cv2.resize(gray, (tw, th), interpolation=cv2.INTER_AREA)
        edges = cv2.Canny(gray, 60, 160)
        res_g = cv2.matchTemplate(gray, templ, cv2.TM_CCOEFF_NORMED)
        res_e = cv2.matchTemplate(edges, edges_t, cv2.TM_CCOEFF_NORMED)
        return float(0.72 * res_g[0, 0] + 0.28 * res_e[0, 0])

    def _green_rois(self, screen_bgr: np.ndarray) -> list[tuple[int, int, int, int]]:
        hsv = cv2.cvtColor(screen_bgr, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self._hsv_lo, self._hsv_hi)
        # Clean noise
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

        screen_h, screen_w = screen_bgr.shape[:2]
        min_h = max(12, int(screen_h * self.MIN_H_FRAC * 0.7))
        max_h = max(min_h + 1, int(screen_h * self.MAX_H_FRAC * 1.35))
        min_w = max(40, int(min_h * self.ASPECT_MIN * 0.8))
        max_w = min(screen_w - 2, int(max_h * self.ASPECT_MAX * 1.2))

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        rois: list[tuple[int, int, int, int]] = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if h < min_h or h > max_h or w < min_w or w > max_w:
                continue
            aspect = w / max(1, h)
            if aspect < self.ASPECT_MIN or aspect > self.ASPECT_MAX:
                continue
            # Expand a bit — button borders
            pad_x = max(2, w // 20)
            pad_y = max(2, h // 10)
            x0 = max(0, x - pad_x)
            y0 = max(0, y - pad_y)
            x1 = min(screen_w, x + w + pad_x)
            y1 = min(screen_h, y + h + pad_y)
            rois.append((x0, y0, x1 - x0, y1 - y0))

        # Prefer larger / more central green bars first
        rois.sort(key=lambda r: (-r[2] * r[3], abs((r[0] + r[2] / 2) - screen_w / 2)))
        return rois[:40]

    def _match_rois(self, screen_bgr: np.ndarray) -> MatchResult | None:
        best: MatchResult | None = None
        for x, y, w, h in self._green_rois(screen_bgr):
            patch = screen_bgr[y : y + h, x : x + w]
            # Score at candidate size and nearby aspect-locked sizes
            for scale in (0.92, 1.0, 1.08):
                tw = max(12, int(w * scale))
                th = max(8, int(round(tw / self._aspect)))
                if th > h + 8 or tw > w + 8:
                    # template slightly larger than ROI — score resized ROI
                    pass
                score = self._score_patch(patch, min(tw, w), min(th, h))
                if score < self.THRESH_ROI:
                    continue
                if best is None or score > best.confidence:
                    # place template-sized box centered in ROI
                    use_w = min(tw, w)
                    use_h = min(th, h)
                    bx = x + max(0, (w - use_w) // 2)
                    by = y + max(0, (h - use_h) // 2)
                    best = MatchResult(bx, by, use_w, use_h, score)
        return best

    def _target_heights(self, screen_h: int) -> list[int]:
        lo = max(12, int(screen_h * self.MIN_H_FRAC))
        hi = max(lo + 1, int(screen_h * self.MAX_H_FRAC))
        # denser sampling in the lower half (windowed / small UI scales)
        low = np.linspace(lo, (lo + hi) * 0.45, 14)
        high = np.linspace((lo + hi) * 0.45, hi, 14)
        return sorted({int(v) for v in np.concatenate([low, high]) if int(v) >= 12})

    def _match_multiscale(
        self,
        screen_gray: np.ndarray,
        screen_edges: np.ndarray,
        heights: list[int],
        threshold: float,
    ) -> MatchResult | None:
        screen_h, screen_w = screen_gray.shape[:2]
        best: MatchResult | None = None
        for th in heights:
            tw = max(16, int(round(th * self._aspect)))
            if tw >= screen_w or th >= screen_h:
                continue
            templ = cv2.resize(
                self._template_gray,
                (tw, th),
                interpolation=cv2.INTER_AREA if th < self._th0 else cv2.INTER_CUBIC,
            )
            edges_t = cv2.resize(
                self._template_edges,
                (tw, th),
                interpolation=cv2.INTER_AREA if th < self._th0 else cv2.INTER_CUBIC,
            )
            res_g = cv2.matchTemplate(screen_gray, templ, cv2.TM_CCOEFF_NORMED)
            res_e = cv2.matchTemplate(screen_edges, edges_t, cv2.TM_CCOEFF_NORMED)
            # Blend maps; empty edges → fall back to gray only
            blended = 0.75 * res_g + 0.25 * res_e
            _, max_val, _, max_loc = cv2.minMaxLoc(blended)
            if max_val < threshold:
                continue
            if best is None or max_val > best.confidence:
                best = MatchResult(
                    x=int(max_loc[0]),
                    y=int(max_loc[1]),
                    width=tw,
                    height=th,
                    confidence=float(max_val),
                )
        return best

    def _refine(
        self,
        screen_bgr: np.ndarray,
        seed: MatchResult,
        scale: float,
    ) -> MatchResult:
        """Re-score a neighborhood at full resolution around a coarse hit."""
        screen_h, screen_w = screen_bgr.shape[:2]
        # Map coarse coords back to full-res
        cx = int((seed.x + seed.width / 2) / scale)
        cy = int((seed.y + seed.height / 2) / scale)
        # Expected full-res size from screen height
        heights = self._target_heights(screen_h)
        # Keep only heights near seed mapped size
        seed_h = max(14, int(seed.height / scale))
        heights = [h for h in heights if abs(h - seed_h) <= max(10, seed_h * 0.35)] or [seed_h]

        pad = max(40, int(seed_h * 2.5))
        x0 = max(0, cx - pad)
        y0 = max(0, cy - pad)
        x1 = min(screen_w, cx + pad)
        y1 = min(screen_h, cy + pad)
        roi = screen_bgr[y0:y1, x0:x1]
        if roi.size == 0:
            return MatchResult(
                int(seed.x / scale),
                int(seed.y / scale),
                max(16, int(seed.width / scale)),
                max(12, int(seed.height / scale)),
                seed.confidence,
            )

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 60, 160)
        local = self._match_multiscale(gray, edges, heights, self.THRESH_FINE * 0.92)
        if local is None:
            return MatchResult(
                int(seed.x / scale),
                int(seed.y / scale),
                max(16, int(seed.width / scale)),
                max(12, int(seed.height / scale)),
                seed.confidence,
            )
        return MatchResult(
            x0 + local.x,
            y0 + local.y,
            local.width,
            local.height,
            local.confidence,
        )

    def find(self, screen_bgr: np.ndarray) -> MatchResult | None:
        if screen_bgr is None or screen_bgr.size == 0:
            return None

        screen_h, screen_w = screen_bgr.shape[:2]
        candidates: list[MatchResult] = []

        # 1) Color ROIs at full resolution (fast & resolution-agnostic)
        roi_hit = self._match_rois(screen_bgr)
        if roi_hit is not None:
            candidates.append(roi_hit)

        # 2) Coarse multiscale on downscaled frame (sizes relative to screen height)
        scale = 1.0
        work = screen_bgr
        if screen_w > self.COARSE_MAX_W:
            scale = self.COARSE_MAX_W / float(screen_w)
            work = cv2.resize(
                screen_bgr,
                (int(screen_w * scale), int(screen_h * scale)),
                interpolation=cv2.INTER_AREA,
            )
        work_gray = cv2.cvtColor(work, cv2.COLOR_BGR2GRAY)
        work_edges = cv2.Canny(work_gray, 60, 160)
        coarse = self._match_multiscale(
            work_gray,
            work_edges,
            self._target_heights(work.shape[0]),
            self.THRESH_COARSE,
        )
        if coarse is not None:
            refined = self._refine(screen_bgr, coarse, scale) if scale != 1.0 else coarse
            candidates.append(refined)

        if not candidates:
            # 3) Last resort: slightly lower threshold on full-res relative heights (smaller set)
            gray = cv2.cvtColor(screen_bgr, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 60, 160)
            heights = self._target_heights(screen_h)[::2]
            return self._match_multiscale(gray, edges, heights, self.threshold * 0.9)

        best = max(candidates, key=lambda m: m.confidence)
        if best.confidence < min(self.threshold, self.THRESH_FINE) * 0.9:
            return None
        return best
