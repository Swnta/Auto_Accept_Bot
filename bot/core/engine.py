"""Accept-button watcher: screen scan → click → optional Telegram notify."""

from __future__ import annotations

import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import cv2
import mss
import numpy as np

from bot.actions.click import click_at, ensure_dpi_aware
from bot.actions.telegram import send_message, send_photo
from bot.vision.match import TemplateMatcher


SettingsProvider = Callable[[], dict[str, Any]]
StatusCallback = Callable[[str], None]


class AcceptEngine:
    """Background loop: find Accept button, click (if enabled), notify Telegram."""

    POLL_SEC = 0.25
    COOLDOWN_SEC = 6.0

    def __init__(
        self,
        template_path: Path,
        get_settings: SettingsProvider,
        on_status: StatusCallback | None = None,
    ) -> None:
        self.template_path = Path(template_path)
        self.get_settings = get_settings
        self.on_status = on_status
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._matcher: TemplateMatcher | None = None
        self._last_hit = 0.0

    @property
    def alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.alive:
            return
        ensure_dpi_aware()
        self._matcher = TemplateMatcher(self.template_path)
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="accept-engine", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
        self._thread = None

    def _emit(self, text: str) -> None:
        if self.on_status:
            try:
                self.on_status(text)
            except Exception:
                pass

    def _grab_monitor(self, sct, monitor: dict) -> tuple[np.ndarray, int, int]:
        """Capture one monitor; return BGR + absolute origin (left, top)."""
        shot = sct.grab(monitor)
        frame = np.asarray(shot, dtype=np.uint8)
        bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        return bgr, int(monitor["left"]), int(monitor["top"])

    def _iter_monitors(self, sct) -> list[dict]:
        # monitors[0] is the full virtual desktop; scan each physical display instead
        mons = list(sct.monitors[1:]) if len(sct.monitors) > 1 else list(sct.monitors[:1])
        return mons

    def _tg_credentials(self, settings: dict[str, Any]) -> tuple[str, str] | None:
        if not settings.get("tg_enabled"):
            return None
        token = str(settings.get("tg_token", "")).strip()
        chat_id = str(settings.get("tg_chat_id", "")).strip()
        if not token or not chat_id:
            self._emit("Telegram: не задан Token/Chat ID")
            return None
        return token, chat_id

    def _send_found(self, settings: dict[str, Any], screen_bgr: np.ndarray) -> None:
        creds = self._tg_credentials(settings)
        if not creds:
            return
        token, chat_id = creds
        text = "Игра найдена!"

        if settings.get("tg_screenshot", True):
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                path = Path(tmp.name)
            try:
                cv2.imwrite(str(path), screen_bgr)
                ok = send_photo(token, chat_id, path, caption=text)
            finally:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
            if not ok:
                send_message(token, chat_id, text)
                self._emit("Telegram: скрин не отправился, текст отправлен")
            else:
                self._emit("Telegram: игра найдена (со скрином)")
            return

        if send_message(token, chat_id, text):
            self._emit("Telegram: игра найдена")
        else:
            self._emit("Telegram: ошибка отправки")

    def _send_accepted(self, settings: dict[str, Any]) -> None:
        creds = self._tg_credentials(settings)
        if not creds:
            return
        token, chat_id = creds
        text = "✅ Принял игру!"
        if send_message(token, chat_id, text):
            self._emit("Telegram: игра принята")
        else:
            self._emit("Telegram: ошибка отправки статуса пика")

    def _run(self) -> None:
        assert self._matcher is not None
        try:
            # mss.MSS preferred; fall back to legacy mss.mss()
            sct_factory = getattr(mss, "MSS", None) or mss.mss
            with sct_factory() as sct:
                while not self._stop.is_set():
                    settings = self.get_settings() or {}
                    now = time.monotonic()
                    if (now - self._last_hit) < self.COOLDOWN_SEC:
                        if self._stop.wait(self.POLL_SEC):
                            break
                        continue

                    hit = None  # (match, screen, origin_x, origin_y)
                    try:
                        for monitor in self._iter_monitors(sct):
                            screen, origin_x, origin_y = self._grab_monitor(sct, monitor)
                            match = self._matcher.find(screen)
                            if match is None:
                                continue
                            if hit is None or match.confidence > hit[0].confidence:
                                hit = (match, screen, origin_x, origin_y)
                    except Exception:
                        time.sleep(self.POLL_SEC)
                        continue

                    if hit is not None:
                        match, screen, origin_x, origin_y = hit
                        self._last_hit = time.monotonic()
                        auto_accept = bool(settings.get("auto_accept", True))
                        self._emit(f"Найдено ({match.confidence:.0%})")

                        try:
                            self._send_found(settings, screen)
                        except Exception:
                            self._emit("Telegram: сбой уведомления")

                        if auto_accept:
                            cx, cy = match.center
                            click_at(cx + origin_x, cy + origin_y)
                            time.sleep(0.05)
                            click_at(cx + origin_x, cy + origin_y)
                            self._emit(f"Принято ({match.confidence:.0%})")
                            try:
                                self._send_accepted(settings)
                            except Exception:
                                self._emit("Telegram: сбой статуса пика")
                        else:
                            self._emit("Клик отключён (автопринятие выкл.)")

                    if self._stop.wait(self.POLL_SEC):
                        break
        except Exception:
            self._emit("Ошибка движка — остановлен")
