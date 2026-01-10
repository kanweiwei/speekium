#!/usr/bin/env python3
"""
Build script for Speekium Python backend using PyInstaller
Creates platform-specific binaries with target-triple naming for Tauri sidecar
"""

import os
import subprocess
import sys
import platform
from pathlib import Path


def get_target_triple():
    """Get Rust target triple for current platform"""
    try:
        # Try to get from rustc (most accurate)
        result = subprocess.run(
            ["rustc", "-Vv"], capture_output=True, text=True, check=True
        )
        for line in result.stderr.split("\n"):
            if line.startswith("host:"):
                return line.split(":")[1].strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Fallback to platform detection
    system = platform.system()
    machine = platform.machine()

    if system == "Darwin":
        if machine == "x86_64":
            return "x86_64-apple-darwin"
        elif machine == "arm64":
            return "aarch64-apple-darwin"
    elif system == "Windows":
        return "x86_64-pc-windows-msvc"
    elif system == "Linux":
        if machine == "x86_64":
            return "x86_64-unknown-linux-gnu"
        elif machine == "aarch64":
            return "aarch64-unknown-linux-gnu"

    raise ValueError(f"Unsupported platform: {system} {machine}")


def build_python_backend():
    """Build Python backend executable with PyInstaller"""
    target_triple = get_target_triple()
    project_root = Path(__file__).parent.parent
    binary_dir = project_root / "src-tauri" / "binaries"
    entry_point = project_root / "src-python" / "backend_main.py"

    # Create binaries directory
    binary_dir.mkdir(parents=True, exist_ok=True)

    print(f"Building Python backend for target: {target_triple}")
    print(f"Entry point: {entry_point}")
    print(f"Output directory: {binary_dir}")

    # Determine executable extension
    if platform.system() == "Windows":
        exe_name = f"speerium-backend-{target_triple}.exe"
    else:
        exe_name = f"speerium-backend-{target_triple}"

    # PyInstaller command
    pyinstaller_cmd = [
        "pyinstaller",
        "--onefile",  # Single executable
        "--name",
        exe_name,
        "--distpath",
        str(binary_dir),
        "--clean",  # Clean build
        "--noconfirm",  # Auto-confirm
        str(entry_point),
    ]

    print(f"\nRunning PyInstaller...")
    print(f"Command: {' '.join(pyinstaller_cmd)}")

    try:
        subprocess.run(pyinstaller_cmd, check=True)
        print(f"\n✅ Build successful!")
        print(f"Output: {binary_dir / exe_name}")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Build failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    build_python_backend()
