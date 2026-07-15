"""Build logo assets: multi-size icon.ico + rail logo for the sidebar."""

from __future__ import annotations

import io
import struct
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
SRC = ASSETS / "logo.png"
ICO = ASSETS / "icon.ico"
RAIL_PNG = ASSETS / "logo_rail.png"

RAIL_RGB = (12, 12, 18)  # #0c0c12
EXE_BG = (11, 11, 16, 255)  # #0b0b10
SIZES = (16, 24, 32, 48, 64, 128, 256)


def square_crop(img: Image.Image) -> Image.Image:
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    w, h = img.size
    side = max(w, h)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(img, ((side - w) // 2, (side - h) // 2), img)
    return canvas


def tile(master: Image.Image, size: int, bg: tuple[int, int, int] | tuple[int, int, int, int]) -> Image.Image:
    if len(bg) == 3:
        bg = (*bg, 255)
    base = Image.new("RGBA", (size, size), bg)
    scaled = master.resize((size, size), Image.Resampling.LANCZOS)
    base.alpha_composite(scaled)
    # Flatten fully opaque — required for reliable Windows file icons
    flat = Image.new("RGBA", (size, size), bg)
    flat.alpha_composite(base)
    return flat


def write_ico(path: Path, images: list[Image.Image]) -> None:
    """Write Vista+ PNG-compressed multi-size .ico."""
    count = len(images)
    offset = 6 + 16 * count
    entries: list[tuple[int, int, int, int]] = []
    blobs: list[bytes] = []
    for im in images:
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        blob = buf.getvalue()
        w, h = im.size
        entries.append((0 if w >= 256 else w, 0 if h >= 256 else h, len(blob), offset))
        blobs.append(blob)
        offset += len(blob)

    out = bytearray()
    out += struct.pack("<HHH", 0, 1, count)
    for w, h, size, off in entries:
        out += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, size, off)
    for blob in blobs:
        out += blob
    path.write_bytes(out)


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"Missing source logo: {SRC}")

    master = square_crop(Image.open(SRC).convert("RGBA"))
    frames = [tile(master, s, EXE_BG) for s in SIZES]
    write_ico(ICO, frames)
    tile(master, 40, RAIL_RGB).save(RAIL_PNG, format="PNG")

    print(f"OK -> {ICO} ({ICO.stat().st_size} bytes, {len(frames)} sizes)")
    print(f"OK -> {RAIL_PNG}")


if __name__ == "__main__":
    main()
