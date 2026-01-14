#!/bin/bash
# Script to add Python daemon sidecar to Tauri app bundle
# This script is called after Tauri build to inject the sidecar

set -e

SIDECAR_PATH="$1"
PLATFORM="$2"
BUILD_TYPE="$3"  # "unsigned" or "signed"

if [ -z "$SIDECAR_PATH" ] || [ -z "$PLATFORM" ]; then
    echo "Usage: $0 <sidecar_path> <platform> [build_type]"
    exit 1
fi

echo "🔧 Adding sidecar to app bundle..."
echo "   Sidecar: $SIDECAR_PATH"
echo "   Platform: $PLATFORM"
echo "   Build type: ${BUILD_TYPE:-unsigned}"

if [ "$PLATFORM" == "macos" ]; then
    # Find the app bundle
    if [ "$BUILD_TYPE" == "signed" ]; then
        APP_PATH=$(find src-tauri/target/universal-apple-darwin/release/bundle/macos -name "*.app" -type d | head -1)
    else
        APP_PATH=$(find src-tauri/target/universal-apple-darwin/release/bundle/macos -name "*.app" -type d 2>/dev/null || \
                   find src-tauri/target/release/bundle/macos -name "*.app" -type d 2>/dev/null | head -1)
    fi

    if [ -z "$APP_PATH" ]; then
        echo "❌ App bundle not found!"
        exit 1
    fi

    echo "   App bundle: $APP_PATH"

    # Copy sidecar to Contents/MacOS/
    cp "$SIDECAR_PATH" "$APP_PATH/Contents/MacOS/worker_daemon"
    chmod +x "$APP_PATH/Contents/MacOS/worker_daemon"

    echo "✅ Sidecar added to macOS app bundle"
    ls -la "$APP_PATH/Contents/MacOS/"

    # If this is a signed build, we need to re-sign the sidecar
    if [ "$BUILD_TYPE" == "signed" ] && [ -n "$APPLE_SIGNING_IDENTITY" ]; then
        echo "🔏 Signing sidecar..."
        codesign --force --options runtime --sign "$APPLE_SIGNING_IDENTITY" "$APP_PATH/Contents/MacOS/worker_daemon"
        echo "✅ Sidecar signed"

        # Re-sign the app bundle
        echo "🔏 Re-signing app bundle..."
        codesign --force --deep --options runtime --sign "$APPLE_SIGNING_IDENTITY" "$APP_PATH"
        echo "✅ App bundle re-signed"
    fi

elif [ "$PLATFORM" == "windows" ]; then
    # For Windows, we need to copy to the installer directory
    # The actual location depends on the installer type

    # For NSIS
    NSIS_DIR="src-tauri/target/release/bundle/nsis"
    if [ -d "$NSIS_DIR" ]; then
        # Copy sidecar to same directory as main exe
        cp "$SIDECAR_PATH" "$NSIS_DIR/worker_daemon.exe"
        echo "✅ Sidecar added to NSIS bundle"
    fi

    # Note: MSI bundling requires modifying the WiX config, which is more complex
    echo "⚠️  Note: MSI installer may need additional configuration"
else
    echo "❌ Unknown platform: $PLATFORM"
    exit 1
fi

echo "✅ Sidecar injection complete"
