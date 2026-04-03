# -*- mode: python ; coding: utf-8 -*-
#
# opensak.spec — PyInstaller byggekonfiguration
# Bruges af GitHub Actions til at bygge .exe (Windows), .app (macOS) og binær (Linux)
#
# Kør manuelt:
#   pyinstaller opensak.spec
#

import sys
import os
from pathlib import Path

block_cipher = None

# Detect platform
IS_WINDOWS = sys.platform == "win32"
IS_MACOS   = sys.platform == "darwin"
IS_LINUX   = sys.platform.startswith("linux")

# ------------------------------------------------------------
# Saml alle data-filer der skal med i pakken
# ------------------------------------------------------------
datas = [
    # Sprogfiler skal med eksplicit da de indlæses dynamisk (ikke via import)
    ('src/opensak/lang/*.py', 'opensak/lang'),
    # Eventuelle ikoner, assets osv. tilføjes her
    # ('src/opensak/assets', 'opensak/assets'),
]

# ------------------------------------------------------------
# Hidden imports — moduler PyInstaller ikke finder automatisk
# ------------------------------------------------------------
hiddenimports = [
    'sqlalchemy.dialects.sqlite',
    'sqlalchemy.pool',
    'lxml.etree',
    'lxml._elementpath',
    'PySide6.QtWebEngineCore',
    'PySide6.QtWebEngineWidgets',
    'PySide6.QtWebChannel',
    'PySide6.QtNetwork',
    'PySide6.QtPrintSupport',
    'alembic',
    'alembic.runtime.migration',
    'alembic.operations',
]


# ------------------------------------------------------------
# Analysis — PyInstaller finder alle imports
# ------------------------------------------------------------
a = Analysis(
    ['run.py'],
    pathex=['.', 'src'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ------------------------------------------------------------
# EXE — selve den eksekverbare fil
# ------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='OpenSAK',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,           # False = intet sort konsol-vindue på Windows
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Eksplicit ingen admin-rettigheder — forhindrer UAC-prompt på Windows
    uac_admin=False,
    uac_uiaccess=False,
    # Windows manifest: asInvoker + DPI-awareness + kompatibilitet
    manifest='opensak.manifest',
    # icon='src/opensak/assets/opensak.ico',  # Tilføj ikon når det findes
)

# ------------------------------------------------------------
# COLLECT — samler alle filer i én mappe (dist/OpenSAK/)
# ------------------------------------------------------------
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='OpenSAK',
)

# ------------------------------------------------------------
# BUNDLE — kun macOS: laver .app mappen
# ------------------------------------------------------------
if IS_MACOS:
    app = BUNDLE(
        coll,
        name='OpenSAK.app',
        # icon='src/opensak/assets/opensak.icns',  # Tilføj ikon når det findes
        bundle_identifier='dk.opensak.app',
        info_plist={
            'NSPrincipalClass': 'NSApplication',
            'NSAppleScriptEnabled': False,
            'CFBundleDocumentTypes': [],
            'LSMinimumSystemVersion': '11.0',
            'NSHighResolutionCapable': True,
        },
    )
