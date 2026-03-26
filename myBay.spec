# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for myBay

Build with:
    pyinstaller myBay.spec

This creates a desktop build in dist/.
On macOS it also creates a .app bundle.
"""

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

# Get the project root
project_root = Path(SPECPATH)

block_cipher = None

# Bundle default data files.
import customtkinter
ctk_path = Path(customtkinter.__path__[0])

datas = [
    # Include HTML templates
    ('server/templates', 'server/templates'),
    # CustomTkinter assets (themes, JSON files)
    (str(ctk_path), 'customtkinter'),
]

# Collect entire packages that PyInstaller struggles with
extra_datas = []
extra_binaries = []
extra_hiddenimports = []

for pkg in ['uvicorn', 'fastapi', 'starlette', 'httpx', 'anyio', 'dotenv', 'multipart']:
    try:
        d, b, h = collect_all(pkg)
        extra_datas.extend(d)
        extra_binaries.extend(b)
        extra_hiddenimports.extend(h)
    except Exception:
        pass

datas.extend(extra_datas)

# Optional: include local secrets/state only when explicitly requested.
# Default is OFF for safer production/distribution builds.
bundle_local_state = os.environ.get('BUNDLE_LOCAL_STATE', '0') == '1'
if bundle_local_state:
    env_file = project_root / '.env'
    if env_file.exists():
        datas.append((str(env_file), '.'))

    ebay_config_file = project_root / '.ebay_config.json'
    if ebay_config_file.exists():
        datas.append((str(ebay_config_file), '.'))

    db_file = project_root / 'mybay.db'
    if db_file.exists():
        datas.append((str(db_file), '.'))

# Optional: bundle ngrok binary for turnkey desktop installs.
# Default is OFF for safer production/distribution builds.
bundle_ngrok = os.environ.get('BUNDLE_NGROK', '0') == '1'
if bundle_ngrok:
    ngrok_candidates = [
        project_root / 'ngrok',
        project_root / 'bin' / 'ngrok',
        Path('/opt/homebrew/bin/ngrok'),
        Path('/usr/local/bin/ngrok'),
    ]
    for ngrok_candidate in ngrok_candidates:
        if ngrok_candidate.exists():
            datas.append((str(ngrok_candidate), '.'))
            break

# Collect all Python files
a = Analysis(
    ['run.py'],
    pathex=[str(project_root)],
    binaries=extra_binaries,
    datas=datas,
    hiddenimports=[
        # Core modules
        'core.paths',
        'core.vision',
        'core.assistant',
        'core.image_utils',
        'core.qr_code',
        'core.watcher',
        'core.integration',
        'core.ngrok',
        'core.turbo',
        'core.retry',
        'core.presets',
        # Data modules
        'data.database',
        # GUI modules
        'gui.app',
        'gui.admin_view',
        'gui.wizard',
        # Server modules
        'server.main',
        # eBay modules
        'ebay.auth',
        'ebay.config',
        'ebay.images',
        'ebay.taxonomy',
        'ebay.inventory',
        'ebay.pricing',
        # Dependencies
        'customtkinter',
        'darkdetect',
        'PIL',
        'PIL.Image',
        'httpx',
        'fastapi',
        'starlette',
        'uvicorn',
        'dotenv',
        'watchdog',
        'watchdog.observers',
        'qrcode',
        'qrcode.image.pil',
        'sqlite3',
        'json',
        'xml.etree.ElementTree',
    ] + extra_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy.testing',
        'scipy',
        'pandas',
        'IPython',
        'jupyter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=True,  # Extract .pyc files so COLLECT picks them up
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='myBay',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No terminal window
    disable_windowed_traceback=False,
    argv_emulation=(sys.platform == 'darwin'),  # macOS app behavior
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='myBay',
)

# Create macOS app bundle only on macOS builds.
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='myBay.app',
        icon='assets/icon.icns',
        bundle_identifier='com.mybay.app',
        info_plist={
            'CFBundleName': 'myBay',
            'CFBundleDisplayName': 'myBay',
            'CFBundleVersion': '1.0.0',
            'CFBundleShortVersionString': '1.0.0',
            'NSHighResolutionCapable': True,
            'NSRequiresAquaSystemAppearance': False,
            'LSMinimumSystemVersion': '10.15.0',
            'CFBundleDocumentTypes': [],
            'NSCameraUsageDescription': 'myBay needs camera access to take product photos.',
            'NSPhotoLibraryUsageDescription': 'myBay needs photo access to select product images.',
        },
    )
