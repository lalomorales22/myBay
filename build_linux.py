#!/usr/bin/env python3
"""Build myBay for Linux (.AppImage)."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

APP_NAME = "myBay"
VERSION = "1.0.0"
PROJECT_ROOT = Path(__file__).parent
DIST_DIR = PROJECT_ROOT / "dist"
LINUX_DIST_DIR = DIST_DIR / "linux"
BUILD_DIR = PROJECT_ROOT / "build" / "linux"
APPDIR = DIST_DIR / "AppDir"
APPIMAGE_TOOL_PATH = BUILD_DIR / "appimagetool-x86_64.AppImage"
APPIMAGE_URL = "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"


def run_command(cmd: list[str], env: dict[str, str] | None = None) -> bool:
    print(f"  -> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env)
    return result.returncode == 0


def clean() -> None:
    for path in [LINUX_DIST_DIR, BUILD_DIR, APPDIR]:
        if path.exists():
            print(f"  removing {path}")
            shutil.rmtree(path)


def check_platform() -> bool:
    if not sys.platform.startswith("linux"):
        print("❌ build_linux.py must be run on Linux (native).")
        return False
    return True


def check_dependencies() -> bool:
    if sys.version_info < (3, 10):
        print("❌ Python 3.10+ required")
        return False

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("❌ PyInstaller is not installed. Run: pip install pyinstaller")
        return False

    return True


def build_pyinstaller() -> bool:
    LINUX_DIST_DIR.mkdir(parents=True, exist_ok=True)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    return run_command(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--clean",
            "--noconfirm",
            "--distpath",
            str(LINUX_DIST_DIR),
            "--workpath",
            str(BUILD_DIR),
            "myBay.spec",
        ]
    )


def prepare_appdir() -> bool:
    source_dir = LINUX_DIST_DIR / APP_NAME
    source_exe = source_dir / APP_NAME
    if not source_exe.exists():
        print(f"❌ Linux executable not found: {source_exe}")
        return False

    if APPDIR.exists():
        shutil.rmtree(APPDIR)

    target_bin = APPDIR / "usr" / "bin"
    target_bin.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, target_bin, dirs_exist_ok=True)

    apprun = APPDIR / "AppRun"
    apprun.write_text(
        "#!/bin/sh\n"
        "HERE=\"$(dirname \"$(readlink -f \"$0\")\")\"\n"
        "exec \"$HERE/usr/bin/myBay\" \"$@\"\n",
        encoding="utf-8",
    )
    apprun.chmod(0o755)

    desktop = APPDIR / f"{APP_NAME}.desktop"
    desktop.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APP_NAME}\n"
        f"Exec={APP_NAME}\n"
        f"Icon={APP_NAME}\n"
        "Categories=Utility;\n"
        "Terminal=false\n",
        encoding="utf-8",
    )

    icon_target = APPDIR / f"{APP_NAME}.png"
    icon_source = PROJECT_ROOT / "assets" / "icon.png"
    if icon_source.exists():
        shutil.copy2(icon_source, icon_target)
    else:
        icon_target.write_bytes(b"\x89PNG\r\n\x1a\n")

    return True


def ensure_appimagetool() -> bool:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    if APPIMAGE_TOOL_PATH.exists():
        return True

    print(f"  downloading appimagetool from {APPIMAGE_URL}")
    if not run_command(["curl", "-L", "-o", str(APPIMAGE_TOOL_PATH), APPIMAGE_URL]):
        return False

    APPIMAGE_TOOL_PATH.chmod(0o755)
    return True


def build_appimage() -> bool:
    output = DIST_DIR / f"{APP_NAME}-{VERSION}-x86_64.AppImage"
    if output.exists():
        output.unlink()

    env = os.environ.copy()
    env["ARCH"] = "x86_64"
    env["APPIMAGE_EXTRACT_AND_RUN"] = "1"

    ok = run_command([str(APPIMAGE_TOOL_PATH), str(APPDIR), str(output)], env=env)
    if not ok:
        print("❌ AppImage packaging failed. Ensure FUSE/libfuse support and appimagetool compatibility on this host.")
        return False

    if not output.exists():
        print(f"❌ AppImage step reported success but file is missing: {output}")
        return False

    print(f"✅ Linux AppImage ready: {output}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Linux AppImage")
    parser.add_argument("--clean", action="store_true", help="Clean build outputs first")
    args = parser.parse_args()

    if args.clean:
        clean()

    if not check_platform():
        return 1
    if not check_dependencies():
        return 1
    if not build_pyinstaller():
        return 1
    if not prepare_appdir():
        return 1
    if not ensure_appimagetool():
        return 1
    if not build_appimage():
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
