# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec file for Velocity Bridge GUI
# Usage: python3 -m PyInstaller velocity-gui.spec
#

from pathlib import Path
import sys

# SPECPATH is provided by PyInstaller
SCRIPT_DIR = Path(SPECPATH).resolve()
GUI_DIR = SCRIPT_DIR / "gui"

block_cipher = None

# Data files to include
datas = [
    (str(GUI_DIR / "velocity-icon-final.png"), "."),
    (str(GUI_DIR / "velocity-gui.desktop"), "."),
    (str(SCRIPT_DIR / "main.py"), "."),
    (str(SCRIPT_DIR / "velocity-avahi.service"), "."),
]

# Check for assets directory
if (GUI_DIR / "assets").exists():
    datas.append((str(GUI_DIR / "assets"), "assets"))

a = Analysis(
    [str(GUI_DIR / "app.py")],
    pathex=[str(SCRIPT_DIR), str(GUI_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'customtkinter',
        'PIL',
        'PIL._imagingtk',
        'PIL._tkinter_finder',
        'pystray',
        'pystray._xorg',
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'fastapi',
        'starlette',
        'pydantic',
        'qrcode',
        'qrcode.image.pil',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='velocity-bridge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(GUI_DIR / "velocity-icon-final.png") if (GUI_DIR / "velocity-icon-final.png").exists() else None,
)
