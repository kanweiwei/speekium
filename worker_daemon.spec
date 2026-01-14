# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Speekium worker daemon

This creates a standalone executable that bundles all Python dependencies
for the voice assistant daemon, used as a Tauri sidecar.

Build commands:
    macOS:   pyinstaller worker_daemon.spec
    Windows: pyinstaller worker_daemon.spec
"""

import sys
import os
import importlib.util
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_dynamic_libs

# Platform detection
is_macos = sys.platform == 'darwin'
is_windows = sys.platform == 'win32'

# Project paths
project_root = os.path.dirname(os.path.abspath(SPEC))

# Helper function to check if a module is available
def is_module_available(module_name):
    return importlib.util.find_spec(module_name) is not None

# Helper function to safely collect data files
def safe_collect_data_files(package, **kwargs):
    try:
        if is_module_available(package):
            return collect_data_files(package, **kwargs)
    except Exception as e:
        print(f"Warning: Could not collect data files for {package}: {e}")
    return []

# Helper function to safely collect submodules
def safe_collect_submodules(package):
    try:
        if is_module_available(package):
            return collect_submodules(package)
    except Exception as e:
        print(f"Warning: Could not collect submodules for {package}: {e}")
    return []

# Helper function to safely collect dynamic libs
def safe_collect_dynamic_libs(package):
    try:
        if is_module_available(package):
            return collect_dynamic_libs(package)
    except Exception as e:
        print(f"Warning: Could not collect dynamic libs for {package}: {e}")
    return []

# =============================================================================
# Data files and binaries collection
# =============================================================================

# Collect data files from packages that need them
datas = []

# FunASR model configurations and resources
datas += safe_collect_data_files('funasr', include_py_files=True)

# Edge-TTS voice data
datas += safe_collect_data_files('edge_tts')

# Torch and audio libraries
datas += safe_collect_data_files('torch')
datas += safe_collect_data_files('torchaudio')

# =============================================================================
# Hidden imports - packages with dynamic imports
# =============================================================================

hiddenimports = []

# Core PyTorch and audio
hiddenimports += safe_collect_submodules('torch')
hiddenimports += safe_collect_submodules('torchaudio')

# FunASR speech recognition
hiddenimports += safe_collect_submodules('funasr')

# NumPy and SciPy
hiddenimports += safe_collect_submodules('numpy')
hiddenimports += safe_collect_submodules('scipy')

# Async HTTP client
hiddenimports += safe_collect_submodules('httpx')
hiddenimports += safe_collect_submodules('httpcore')
hiddenimports += safe_collect_submodules('anyio')

# Audio I/O
hiddenimports += safe_collect_submodules('sounddevice')

# Input handling for hotkeys
hiddenimports += safe_collect_submodules('pynput')

# Structured logging
hiddenimports += safe_collect_submodules('structlog')

# Additional commonly missed hidden imports
hiddenimports += [
    # Standard library modules that might be dynamically imported
    'json',
    'asyncio',
    'signal',
    'resource',
    'traceback',
    'queue',
    'threading',
    'multiprocessing',

    # Numba JIT compiler (funasr dependency)
    'numba',
    'llvmlite',
    'llvmlite.binding',

    # SSL/TLS for edge-tts
    'ssl',
    'certifi',

    # macOS-specific
    'Foundation' if is_macos else None,
    'AppKit' if is_macos else None,
    'objc' if is_macos else None,

    # Windows-specific
    'win32api' if is_windows else None,
    'win32con' if is_windows else None,
    'pywintypes' if is_windows else None,
]

# Remove None values from list
hiddenimports = [x for x in hiddenimports if x is not None]

# =============================================================================
# Binaries - Dynamic libraries
# =============================================================================

binaries = []

# Collect dynamic libraries for audio
binaries += safe_collect_dynamic_libs('sounddevice')

# PyTorch dynamic libraries
binaries += safe_collect_dynamic_libs('torch')
binaries += safe_collect_dynamic_libs('torchaudio')

# =============================================================================
# Analysis
# =============================================================================

a = Analysis(
    ['worker_daemon.py'],
    pathex=[project_root],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude packages not needed at runtime
        'tkinter',
        'matplotlib',
        'PIL',  # Only needed for tray_manager which is not used in daemon
        'pystray',  # Not used in worker_daemon
        'pywebview',  # Not used in worker_daemon
        # Exclude NLP/ML packages not used by worker_daemon
        'nltk',  # Not needed, causes runtime issues
        'transformers',  # Uses local FunASR models only
        'tensorflow',
        'keras',
        # Exclude test modules
        'pytest',
        'pytest_asyncio',
        'pytest_cov',
        'pytest_mock',
        'pytest_timeout',
        # Exclude development tools
        'ruff',
        'bandit',
        'safety',
        'pip_audit',
    ],
    noarchive=False,
    optimize=2,  # Apply Python bytecode optimization
)

# =============================================================================
# PYZ Archive
# =============================================================================

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=None,
)

# =============================================================================
# Executable
# =============================================================================

exe = EXE(
    pyz,
    a.scripts,
    [],  # Don't include binaries/datas in EXE for onedir mode
    exclude_binaries=True,  # Required for onedir mode
    name='worker_daemon',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,  # Don't strip symbols on macOS (signing issues)
    upx=True if is_windows else False,  # UPX compression only on Windows
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Console app (no GUI)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,  # Use native architecture
    codesign_identity=None,  # Will be signed by Tauri build process
    entitlements_file=None,
)

# =============================================================================
# Collect all files into a directory (onedir mode)
# =============================================================================

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True if is_windows else False,
    upx_exclude=[],
    name='worker_daemon',
)

# =============================================================================
# macOS App Bundle (optional, for standalone testing)
# =============================================================================

if is_macos:
    app = BUNDLE(
        exe,
        name='WorkerDaemon.app',
        icon=None,
        bundle_identifier='com.speekium.worker-daemon',
        info_plist={
            'CFBundleShortVersionString': '0.1.0',
            'NSHighResolutionCapable': True,
            'NSMicrophoneUsageDescription': 'Speekium needs microphone access for voice recognition.',
        },
    )
