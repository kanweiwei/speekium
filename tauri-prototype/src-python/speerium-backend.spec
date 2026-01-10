# -*- mode: python ; coding: utf-8 -*-

"""
PyInstaller spec file for Speekium Python backend
Configures standalone binary for Tauri sidecar integration
"""

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# ===== Basic Configuration =====
block_cipher = None

# Python backend entry point
backend_script = os.path.join("src-python", "backend_main.py")

# Collect data files from packages
datas = [
    # Add any configuration files or resources here
]

# Collect hidden imports
hiddenimports = [
    "pytauri",
    "pydantic",
    "asyncio",
    "sounddevice",
    "numpy",
    "torch",
    "scipy",
    "edge_tts",
    "httpx",
    "funasr",
]

# ===== Analysis =====
a = Analysis(
    [backend_script],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# ===== PYZ (Python Zip Archive) =====
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ===== EXE =====
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="speekium-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Keep console for debugging (set False for production)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
