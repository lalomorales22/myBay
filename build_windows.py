#!/usr/bin/env python3
"""Build myBay for Windows (.exe)."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

APP_NAME = "myBay"
PROJECT_ROOT = Path(__file__).parent
DIST_DIR = PROJECT_ROOT / "dist" / "windows"
BUILD_DIR = PROJECT_ROOT / "build" / "windows"


def get_env(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def run_command(cmd: list[str]) -> bool:
    print(f"  -> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    return result.returncode == 0


def clean() -> None:
    for path in [DIST_DIR, BUILD_DIR]:
        if path.exists():
            print(f"  removing {path}")
            shutil.rmtree(path)


def check_platform() -> bool:
    if sys.platform != "win32":
        print("❌ build_windows.py must be run on Windows (native).")
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


def get_exe_path() -> Path:
    return DIST_DIR / APP_NAME / f"{APP_NAME}.exe"


def build() -> bool:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    ok = run_command(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--clean",
            "--noconfirm",
            "--distpath",
            str(DIST_DIR),
            "--workpath",
            str(BUILD_DIR),
            "myBay.spec",
        ]
    )
    if not ok:
        return False

    exe_path = get_exe_path()
    if not exe_path.exists():
        print(f"❌ Build finished but executable was not found: {exe_path}")
        return False

    print(f"✅ Windows build ready: {exe_path}")
    return True


def check_signing_prerequisites() -> bool:
    sign_tool = get_env("WIN_SIGN_TOOL", "signtool")
    cert_file = get_env("WIN_CERT_FILE")
    cert_subject = get_env("WIN_CERT_SUBJECT")

    if cert_file == "" and cert_subject == "":
        print("❌ Windows signing requested but no certificate configured.")
        print("   Set WIN_CERT_FILE (+ optional WIN_CERT_PASSWORD), or WIN_CERT_SUBJECT for cert-store signing.")
        return False

    check_cmd = ["where", sign_tool]
    if subprocess.run(check_cmd, capture_output=True, text=True).returncode != 0:
        print(f"❌ Could not find signing tool '{sign_tool}' in PATH.")
        return False

    if cert_file and not Path(cert_file).exists():
        print(f"❌ WIN_CERT_FILE does not exist: {cert_file}")
        return False

    return True


def sign_executable(exe_path: Path) -> bool:
    sign_tool = get_env("WIN_SIGN_TOOL", "signtool")
    cert_file = get_env("WIN_CERT_FILE")
    cert_password = get_env("WIN_CERT_PASSWORD")
    cert_subject = get_env("WIN_CERT_SUBJECT")
    timestamp_url = get_env("WIN_TIMESTAMP_URL", "http://timestamp.digicert.com")
    file_digest = get_env("WIN_FILE_DIGEST", "SHA256")
    timestamp_digest = get_env("WIN_TIMESTAMP_DIGEST", "SHA256")

    cmd = [
        sign_tool,
        "sign",
        "/fd",
        file_digest,
        "/td",
        timestamp_digest,
        "/tr",
        timestamp_url,
    ]

    if cert_file:
        cmd.extend(["/f", cert_file])
        if cert_password:
            cmd.extend(["/p", cert_password])
    else:
        cmd.extend(["/n", cert_subject])

    cmd.append(str(exe_path))

    print("\n🔏 Signing Windows executable...")
    if not run_command(cmd):
        return False

    return run_command([sign_tool, "verify", "/pa", "/v", str(exe_path)])


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Windows executable")
    parser.add_argument("--clean", action="store_true", help="Clean build outputs first")
    parser.add_argument("--sign", action="store_true", help="Sign executable after build")
    parser.add_argument("--sign-only", action="store_true", help="Sign existing executable without rebuilding")
    args = parser.parse_args()

    if args.clean:
        clean()

    if not check_platform():
        return 1
    if not check_dependencies():
        return 1

    if args.sign and args.sign_only:
        print("❌ Use either --sign or --sign-only, not both.")
        return 1

    if args.sign_only:
        exe_path = get_exe_path()
        if not exe_path.exists():
            print(f"❌ No built executable found to sign: {exe_path}")
            return 1
        if not check_signing_prerequisites():
            return 1
        if not sign_executable(exe_path):
            return 1
        print(f"✅ Windows executable signed: {exe_path}")
        return 0

    if not build():
        return 1

    if args.sign:
        exe_path = get_exe_path()
        if not check_signing_prerequisites():
            return 1
        if not sign_executable(exe_path):
            return 1
        print(f"✅ Windows executable signed: {exe_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
