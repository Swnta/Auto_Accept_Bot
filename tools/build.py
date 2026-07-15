"""Build Auto_Accept_Bot.exe into the project root."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "main.py"
ICON = ROOT / "assets" / "icon.ico"
OUT_NAME = "Auto_Accept_Bot"
OLD_NAMES = ("AutoAccept Bot",)
BUILD_DIR = ROOT / ".build"
DIST_TMP = BUILD_DIR / "dist"


def main() -> int:
    if not SRC.exists():
        print(f"Source not found: {SRC}")
        return 1

    if not ICON.exists():
        print("Generating icon…")
        result = subprocess.run([sys.executable, str(ROOT / "tools" / "make_icon.py")], cwd=ROOT)
        if result.returncode != 0 or not ICON.exists():
            print("Icon generation failed")
            return 1
    else:
        subprocess.run([sys.executable, str(ROOT / "tools" / "make_icon.py")], cwd=ROOT, check=False)

    BUILD_DIR.mkdir(exist_ok=True)

    add_data_assets = f"{ICON.parent};assets"
    add_data_bot = f"{ROOT / 'bot'};bot"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        f"--name={OUT_NAME}",
        f"--icon={ICON}",
        f"--paths={ROOT}",
        f"--add-data={add_data_assets}",
        f"--add-data={add_data_bot}",
        "--hidden-import=bot",
        "--hidden-import=bot.core",
        "--hidden-import=bot.core.engine",
        "--hidden-import=bot.actions",
        "--hidden-import=bot.actions.click",
        "--hidden-import=bot.actions.telegram",
        "--hidden-import=bot.vision",
        "--hidden-import=bot.vision.match",
        "--hidden-import=cv2",
        "--hidden-import=mss",
        "--hidden-import=numpy",
        f"--distpath={DIST_TMP}",
        f"--workpath={BUILD_DIR / 'work'}",
        f"--specpath={BUILD_DIR}",
        str(SRC),
    ]
    print(" ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        return result.returncode

    built = DIST_TMP / f"{OUT_NAME}.exe"
    target = ROOT / f"{OUT_NAME}.exe"
    if not built.exists():
        print(f"Build missing: {built}")
        return 1

    shutil.copy2(built, target)
    for old in OLD_NAMES:
        old_path = ROOT / f"{old}.exe"
        if old_path.exists():
            old_path.unlink()
            print(f"removed {old_path.name}")
    print(f"OK -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
