#!/usr/bin/env python3
"""
Build script for myBay

Creates a macOS .app bundle and optional .dmg installer.

Usage:
    python build.py           # Build .app only
    python build.py --dmg     # Build .app and .dmg
    python build.py --dmg --sign --notarize  # Build, sign, notarize
    python build.py --clean   # Clean build artifacts
"""

import os
import sys
import shutil
import subprocess
import argparse
from pathlib import Path


# Build configuration
APP_NAME = "myBay"
VERSION = "1.0.0"
BUNDLE_ID = "com.mybay.app"

PROJECT_ROOT = Path(__file__).parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
ASSETS_DIR = PROJECT_ROOT / "assets"


def run_command(cmd: list, cwd: Path = None) -> bool:
    """Run a command and return success status."""
    print(f"  → {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd or PROJECT_ROOT)
    return result.returncode == 0


def get_env(name: str) -> str:
    """Read and trim an environment variable."""
    return os.environ.get(name, "").strip()


def ensure_assets():
    """Create assets directory and icon if needed."""
    ASSETS_DIR.mkdir(exist_ok=True)
    
    icon_path = ASSETS_DIR / "icon.icns"
    if not icon_path.exists():
        print("\n📦 Creating app icon...")
        create_icon()


def create_icon():
    """Create a simple app icon using Python."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        # Create a 1024x1024 icon
        size = 1024
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Draw rounded rectangle background
        margin = 100
        radius = 180
        bg_color = (31, 83, 141)  # Nice blue
        
        # Simple rounded rect approximation
        draw.rectangle(
            [margin, margin, size - margin, size - margin],
            fill=bg_color,
        )
        
        # Draw a "m" letter
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 600)
        except:
            font = ImageFont.load_default()

        draw.text(
            (size // 2, size // 2 - 50),
            "m",
            fill=(255, 255, 255),
            font=font,
            anchor="mm",
        )
        
        # Draw a small eBay-like box icon
        box_size = 150
        box_x = size - margin - box_size - 50
        box_y = size - margin - box_size - 50
        draw.rectangle(
            [box_x, box_y, box_x + box_size, box_y + box_size],
            fill=(255, 203, 5),  # eBay yellow
            outline=(0, 0, 0),
            width=8,
        )
        
        # Save PNG first
        png_path = ASSETS_DIR / "icon.png"
        img.save(png_path)
        
        # Convert to icns using sips (macOS)
        icns_path = ASSETS_DIR / "icon.icns"
        iconset_path = ASSETS_DIR / "icon.iconset"
        
        # Create iconset directory
        iconset_path.mkdir(exist_ok=True)
        
        # Create all required sizes
        sizes = [16, 32, 64, 128, 256, 512, 1024]
        for s in sizes:
            resized = img.resize((s, s), Image.Resampling.LANCZOS)
            resized.save(iconset_path / f"icon_{s}x{s}.png")
            if s <= 512:
                # Also save @2x versions
                resized2x = img.resize((s * 2, s * 2), Image.Resampling.LANCZOS)
                resized2x.save(iconset_path / f"icon_{s}x{s}@2x.png")
        
        # Use iconutil to create .icns
        run_command([
            "iconutil", "-c", "icns",
            str(iconset_path),
            "-o", str(icns_path),
        ])
        
        # Clean up iconset
        shutil.rmtree(iconset_path)
        
        print(f"  ✅ Created icon at {icns_path}")
        
    except ImportError:
        print("  ⚠️ PIL not available, using placeholder icon")
        # Create empty file as placeholder
        (ASSETS_DIR / "icon.icns").touch()


def clean():
    """Clean build artifacts."""
    print("\n🧹 Cleaning build artifacts...")
    
    for path in [DIST_DIR, BUILD_DIR]:
        if path.exists():
            print(f"  Removing {path}")
            shutil.rmtree(path)
    
    # Remove PyInstaller cache
    pycache = PROJECT_ROOT / "__pycache__"
    if pycache.exists():
        shutil.rmtree(pycache)
    
    print("  ✅ Clean complete")


def check_dependencies():
    """Check that required build tools are installed."""
    print("\n🔍 Checking dependencies...")
    
    # Check Python version
    if sys.version_info < (3, 10):
        print("  ❌ Python 3.10+ required")
        return False
    print(f"  ✅ Python {sys.version_info.major}.{sys.version_info.minor}")
    
    # Check PyInstaller
    try:
        import PyInstaller
        print(f"  ✅ PyInstaller {PyInstaller.__version__}")
    except ImportError:
        print("  ❌ PyInstaller not installed")
        print("     Run: pip install pyinstaller")
        return False
    
    # Check customtkinter
    try:
        import customtkinter
        print("  ✅ CustomTkinter")
    except ImportError:
        print("  ⚠️ CustomTkinter not installed (will be bundled)")
    
    return True


def check_release_security() -> bool:
    """Prevent accidental secret/state bundling in distribution builds."""
    bundle_local_state = os.environ.get("BUNDLE_LOCAL_STATE", "0") == "1"
    bundle_ngrok = os.environ.get("BUNDLE_NGROK", "0") == "1"

    if bundle_local_state and os.environ.get("ALLOW_BUNDLED_SECRETS", "0") != "1":
        print("\n  ❌ Refusing to build with BUNDLE_LOCAL_STATE=1 without explicit confirmation.")
        print("     This can embed .env/.ebay_config.json/local DB into distributable artifacts.")
        print("     If you really want this for a private/internal build, set:")
        print("     ALLOW_BUNDLED_SECRETS=1")
        return False

    if bundle_local_state:
        print("\n  ⚠️  BUNDLE_LOCAL_STATE=1 enabled (private/internal build mode).")
    if bundle_ngrok:
        print("\n  ⚠️  BUNDLE_NGROK=1 enabled (bundling local ngrok binary).")

    return True


def check_signing_prerequisites(sign: bool, notarize: bool, create_dmg_flag: bool) -> bool:
    """Validate codesign/notarization prerequisites."""
    if not sign and not notarize:
        return True

    if sys.platform != "darwin":
        print("\n  ❌ macOS signing/notarization is only available on macOS hosts.")
        return False

    if notarize and not sign:
        print("\n  ❌ --notarize requires --sign.")
        return False
    if notarize and not create_dmg_flag:
        print("\n  ❌ --notarize requires --dmg.")
        return False

    if sign and get_env("MACOS_SIGN_IDENTITY") == "":
        print("\n  ❌ MACOS_SIGN_IDENTITY is required when using --sign.")
        print("     Example: export MACOS_SIGN_IDENTITY='Developer ID Application: Your Name (TEAMID)'")
        return False

    if notarize and get_env("MACOS_NOTARY_PROFILE") == "":
        print("\n  ❌ MACOS_NOTARY_PROFILE is required when using --notarize.")
        print("     Create one first with:")
        print("     xcrun notarytool store-credentials <PROFILE> --apple-id <id> --team-id <team> --password <app-password>")
        return False

    return True


def build_app():
    """Build the .app bundle with PyInstaller."""
    print("\n🔨 Building application...")
    
    ensure_assets()
    
    success = run_command([
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--noconfirm",
        "myBay.spec",
    ])
    
    if success:
        app_path = DIST_DIR / f"{APP_NAME}.app"
        print(f"\n  ✅ App built: {app_path}")
        return True
    else:
        print("\n  ❌ Build failed")
        return False


def create_dmg():
    """Create a .dmg installer."""
    print("\n📦 Creating DMG installer...")
    
    app_path = DIST_DIR / f"{APP_NAME}.app"
    dmg_path = DIST_DIR / f"{APP_NAME}-{VERSION}.dmg"
    
    if not app_path.exists():
        print(f"  ❌ App not found at {app_path}")
        return False
    
    # Remove existing DMG
    if dmg_path.exists():
        dmg_path.unlink()
    
    # Create DMG using hdiutil
    temp_dmg = DIST_DIR / "temp.dmg"
    volume_name = f"myBay {VERSION}"
    
    # Create a temporary DMG
    success = run_command([
        "hdiutil", "create",
        "-volname", volume_name,
        "-srcfolder", str(app_path),
        "-ov", "-format", "UDRW",
        str(temp_dmg),
    ])
    
    if not success:
        return False
    
    # Convert to compressed DMG
    success = run_command([
        "hdiutil", "convert",
        str(temp_dmg),
        "-format", "UDZO",
        "-o", str(dmg_path),
    ])
    
    # Clean up
    temp_dmg.unlink()
    
    if success:
        print(f"\n  ✅ DMG created: {dmg_path}")
        print(f"     Size: {dmg_path.stat().st_size / 1024 / 1024:.1f} MB")
        return True
    
    return False


def sign_app_bundle(app_path: Path) -> bool:
    """Code-sign the macOS app bundle."""
    identity = get_env("MACOS_SIGN_IDENTITY")
    entitlements = get_env("MACOS_ENTITLEMENTS_FILE")

    print("\n🔏 Code-signing app bundle...")
    cmd = [
        "codesign",
        "--force",
        "--deep",
        "--options",
        "runtime",
        "--timestamp",
    ]
    if entitlements:
        cmd.extend(["--entitlements", entitlements])
    cmd.extend(["--sign", identity, str(app_path)])

    if not run_command(cmd):
        return False

    return run_command([
        "codesign",
        "--verify",
        "--deep",
        "--strict",
        "--verbose=2",
        str(app_path),
    ])


def sign_dmg(dmg_path: Path) -> bool:
    """Code-sign the DMG."""
    identity = get_env("MACOS_SIGN_IDENTITY")

    print("\n🔏 Code-signing DMG...")
    if not run_command([
        "codesign",
        "--force",
        "--timestamp",
        "--sign",
        identity,
        str(dmg_path),
    ]):
        return False

    return run_command([
        "codesign",
        "--verify",
        "--verbose=2",
        str(dmg_path),
    ])


def notarize_dmg(app_path: Path, dmg_path: Path) -> bool:
    """Submit DMG for notarization and staple the result."""
    profile = get_env("MACOS_NOTARY_PROFILE")

    print("\n🧾 Submitting DMG for notarization...")
    if not run_command([
        "xcrun",
        "notarytool",
        "submit",
        str(dmg_path),
        "--keychain-profile",
        profile,
        "--wait",
    ]):
        return False

    print("\n📎 Stapling notarization ticket...")
    if not run_command(["xcrun", "stapler", "staple", str(dmg_path)]):
        return False
    if not run_command(["xcrun", "stapler", "staple", str(app_path)]):
        return False

    return run_command(["xcrun", "stapler", "validate", str(dmg_path)])


def main():
    parser = argparse.ArgumentParser(
        description="Build myBay for macOS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python build.py           Build .app bundle
    python build.py --dmg     Build .app and create .dmg
    python build.py --dmg --sign           Build + codesign app/dmg
    python build.py --dmg --sign --notarize  Build + codesign + notarize
    python build.py --clean   Remove build artifacts
        """,
    )
    parser.add_argument("--dmg", action="store_true", help="Create DMG installer")
    parser.add_argument("--sign", action="store_true", help="Code-sign output (requires MACOS_SIGN_IDENTITY)")
    parser.add_argument("--notarize", action="store_true", help="Notarize DMG (requires --dmg --sign and MACOS_NOTARY_PROFILE)")
    parser.add_argument("--clean", action="store_true", help="Clean build artifacts")
    parser.add_argument("--icon-only", action="store_true", help="Only create icon")
    
    args = parser.parse_args()
    
    print("=" * 50)
    print(f"  myBay — Build Script v{VERSION}")
    print("=" * 50)
    
    if args.clean:
        clean()
        return 0
    
    if args.icon_only:
        ensure_assets()
        return 0
    
    if not check_dependencies():
        return 1

    if not check_release_security():
        return 1

    if not check_signing_prerequisites(args.sign, args.notarize, args.dmg):
        return 1
    
    if not build_app():
        return 1

    app_path = DIST_DIR / f"{APP_NAME}.app"
    if args.sign:
        if not sign_app_bundle(app_path):
            return 1
    
    if args.dmg:
        if not create_dmg():
            return 1
        dmg_path = DIST_DIR / f"{APP_NAME}-{VERSION}.dmg"
        if args.sign:
            if not sign_dmg(dmg_path):
                return 1
        if args.notarize:
            if not notarize_dmg(app_path, dmg_path):
                return 1
    
    print("\n" + "=" * 50)
    print("  ✅ Build complete!")
    print("=" * 50)
    print(f"\n  App location: {DIST_DIR / f'{APP_NAME}.app'}")
    if args.dmg:
        print(f"  DMG location: {DIST_DIR / f'{APP_NAME}-{VERSION}.dmg'}")
    print("\n  To run: open dist/myBay.app")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
