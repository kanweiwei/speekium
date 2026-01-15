#!/bin/bash
# Local signed build script for macOS
set -e

# Parse arguments
SKIP_SIGN=false
SPECIFIED_ARCH=""
for arg in "$@"; do
  case $arg in
    --no-sign|--skip-sign)
      SKIP_SIGN=true
      ;;
    --arch=*)
      SPECIFIED_ARCH="${arg#*=}"
      ;;
    --arm64|--aarch64)
      SPECIFIED_ARCH="arm64"
      ;;
    --x86_64|--intel)
      SPECIFIED_ARCH="x86_64"
      ;;
  esac
done

# Determine architecture
if [ -n "$SPECIFIED_ARCH" ]; then
  ARCH="$SPECIFIED_ARCH"
  echo "🎯 Using specified architecture: $ARCH"
else
  ARCH=$(uname -m)
  echo "🔍 Detected architecture: $ARCH"
fi

# Map to Rust target
if [ "$ARCH" = "arm64" ] || [ "$ARCH" = "aarch64" ]; then
  RUST_TARGET="aarch64-apple-darwin"
elif [ "$ARCH" = "x86_64" ]; then
  RUST_TARGET="x86_64-apple-darwin"
else
  echo "❌ Unknown architecture: $ARCH"
  echo "   Supported: arm64, x86_64"
  exit 1
fi

if [ "$SKIP_SIGN" = true ]; then
  echo "🔧 Building Speekium (without signing/notarization)..."
else
  # Check required environment variables
  if [ -z "$APPLE_SIGNING_IDENTITY" ]; then
    echo "❌ APPLE_SIGNING_IDENTITY not set"
    echo "Run: security find-identity -v -p codesigning"
    echo "Then: export APPLE_SIGNING_IDENTITY=\"Developer ID Application: ...\""
    exit 1
  fi

  if [ -z "$APPLE_ID" ] || [ -z "$APPLE_APP_SPECIFIC_PASSWORD" ] || [ -z "$APPLE_TEAM_ID" ]; then
    echo "❌ Missing notarization credentials"
    echo "Set: APPLE_ID, APPLE_APP_SPECIFIC_PASSWORD, APPLE_TEAM_ID"
    exit 1
  fi

  echo "🔧 Building Speekium with signing and notarization..."
  echo "   Signing Identity: $APPLE_SIGNING_IDENTITY"
  echo "   Team ID: $APPLE_TEAM_ID"
fi

echo "🏗️  Building for architecture: $RUST_TARGET"

cd "$(dirname "$0")/.."

# Temporarily change bundle ID to macOS-specific one
TAURI_CONF="src-tauri/tauri.conf.json"
ORIGINAL_BUNDLE_ID="com.speekium.app"
MACOS_BUNDLE_ID="com.speekium.mac"

# Function to restore bundle ID
restore_bundle_id() {
  echo "🔄 Restoring bundle ID to $ORIGINAL_BUNDLE_ID..."
  sed -i '' "s/\"identifier\": \"$MACOS_BUNDLE_ID\"/\"identifier\": \"$ORIGINAL_BUNDLE_ID\"/" "$TAURI_CONF"
}

# Set trap to restore on exit (success or failure)
trap restore_bundle_id EXIT

echo "📝 Changing bundle ID to $MACOS_BUNDLE_ID..."
sed -i '' "s/\"identifier\": \"$ORIGINAL_BUNDLE_ID\"/\"identifier\": \"$MACOS_BUNDLE_ID\"/" "$TAURI_CONF"
grep "identifier" "$TAURI_CONF"

# Step 1: Build Python daemon with PyInstaller
echo "📦 Building Python daemon..."
source .venv/bin/activate
rm -rf sidecar_dist build/worker_daemon
pyinstaller worker_daemon.spec --noconfirm --distpath sidecar_dist
echo "✅ Python daemon built"

# Step 2: Build frontend
echo "🎨 Building frontend..."
npm run build

# Step 3: Build Tauri app (unsigned - we'll sign manually)
echo "🦀 Building Tauri app (without automatic signing)..."
# Save Apple credentials for later manual signing
SAVED_APPLE_SIGNING_IDENTITY="$APPLE_SIGNING_IDENTITY"
SAVED_APPLE_ID="$APPLE_ID"
SAVED_APPLE_APP_SPECIFIC_PASSWORD="$APPLE_APP_SPECIFIC_PASSWORD"
SAVED_APPLE_TEAM_ID="$APPLE_TEAM_ID"

# Unset ALL Apple variables to prevent Tauri's automatic signing/notarization
unset APPLE_SIGNING_IDENTITY
unset APPLE_ID
unset APPLE_APP_SPECIFIC_PASSWORD
unset APPLE_TEAM_ID
unset APPLE_CERTIFICATE
unset APPLE_CERTIFICATE_PASSWORD
unset APPLE_SIGNING_IDENTITY_TAURI
unset TAURI_SIGNING_PRIVATE_KEY

# Build without signing
CI=true npm run tauri build -- --target "$RUST_TARGET"

# Restore Apple credentials for manual signing
APPLE_SIGNING_IDENTITY="$SAVED_APPLE_SIGNING_IDENTITY"
APPLE_ID="$SAVED_APPLE_ID"
APPLE_APP_SPECIFIC_PASSWORD="$SAVED_APPLE_APP_SPECIFIC_PASSWORD"
APPLE_TEAM_ID="$SAVED_APPLE_TEAM_ID"
echo "✅ Tauri build complete, credentials restored"

# Step 4: Find the app bundle
APP_PATH=$(find "src-tauri/target/$RUST_TARGET/release/bundle/macos" -name "*.app" -type d | head -1)
if [ -z "$APP_PATH" ]; then
  echo "❌ App bundle not found!"
  exit 1
fi
echo "📱 Found app: $APP_PATH"

# Step 5: Add sidecar
echo "📥 Adding sidecar..."
SIDECAR_DIR="$APP_PATH/Contents/Resources/worker_daemon"
mkdir -p "$SIDECAR_DIR"
ditto sidecar_dist/worker_daemon "$SIDECAR_DIR"
chmod +x "$SIDECAR_DIR/worker_daemon"

# Clean up unnecessary files
find "$SIDECAR_DIR" -name ".gitignore" -delete 2>/dev/null || true
find "$SIDECAR_DIR" -name "*.pyc" -delete 2>/dev/null || true
find "$SIDECAR_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

if [ "$SKIP_SIGN" = true ]; then
  echo "⏭️  Skipping signing (--no-sign)"
else
  # Step 6: Sign from inside out with entitlements
  echo "🔏 Signing (inside-out with entitlements)..."

  # Entitlements files
  SCRIPT_DIR="$(dirname "$0")"
  PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
  APP_ENTITLEMENTS="$PROJECT_ROOT/src-tauri/Speekium.entitlements"
  SIDECAR_ENTITLEMENTS="$PROJECT_ROOT/src-tauri/WorkerDaemon.entitlements"

  # Verify entitlements files exist
  if [ ! -f "$APP_ENTITLEMENTS" ]; then
    echo "❌ Missing entitlements file: $APP_ENTITLEMENTS"
    exit 1
  fi
  if [ ! -f "$SIDECAR_ENTITLEMENTS" ]; then
    echo "❌ Missing entitlements file: $SIDECAR_ENTITLEMENTS"
    exit 1
  fi

  # Sign frameworks
  find "$SIDECAR_DIR" -name "*.framework" -type d | while read -r framework; do
    echo "  Signing framework: $(basename $framework)"
    codesign --force --options runtime --timestamp --sign "$APPLE_SIGNING_IDENTITY" \
      --entitlements "$SIDECAR_ENTITLEMENTS" "$framework" 2>/dev/null || true
  done

  # Sign dylibs and so files
  find "$SIDECAR_DIR" -type f \( -name "*.so" -o -name "*.dylib" \) ! -path "*.framework/*" | while read -r lib; do
    echo "  Signing: $(basename $lib)"
    codesign --force --options runtime --timestamp --sign "$APPLE_SIGNING_IDENTITY" \
      --entitlements "$SIDECAR_ENTITLEMENTS" "$lib" 2>/dev/null || true
  done

  # Sign sidecar executable with microphone entitlements
  echo "  Signing sidecar with microphone entitlements..."
  codesign --force --options runtime --timestamp --sign "$APPLE_SIGNING_IDENTITY" \
    --entitlements "$SIDECAR_ENTITLEMENTS" "$SIDECAR_DIR/worker_daemon"

  # Sign main app executable with microphone entitlements
  echo "  Signing main app with microphone entitlements..."
  codesign --force --options runtime --timestamp --sign "$APPLE_SIGNING_IDENTITY" \
    --entitlements "$APP_ENTITLEMENTS" "$APP_PATH/Contents/MacOS/speekium"

  # Sign app bundle with microphone entitlements
  codesign --force --options runtime --timestamp --sign "$APPLE_SIGNING_IDENTITY" \
    --entitlements "$APP_ENTITLEMENTS" "$APP_PATH"
  echo "✅ Signing complete (with microphone entitlements)"

  # Step 7: Verify signature
  echo "🔍 Verifying signature..."
  codesign --verify --deep --strict --verbose=2 "$APP_PATH" || {
    echo "⚠️ Signature verification failed"
    exit 1
  }
fi

if [ "$SKIP_SIGN" = true ]; then
  echo ""
  echo "✅ Build complete! (unsigned)"
  echo "📱 App: $APP_PATH"
  echo ""
  echo "Test with: open \"$APP_PATH\""
else
  # Step 8: Create DMG
  echo "📦 Creating DMG..."
  DMG_DIR="src-tauri/target/$RUST_TARGET/release/bundle/dmg"
  mkdir -p "$DMG_DIR"
  APP_NAME=$(basename "$APP_PATH" .app)
  DMG_PATH="$DMG_DIR/${APP_NAME}_${ARCH}.dmg"
  rm -f "$DMG_PATH"
  hdiutil create -volname "$APP_NAME" -srcfolder "$APP_PATH" -ov -format UDZO "$DMG_PATH"

  # Sign DMG
  codesign --force --sign "$APPLE_SIGNING_IDENTITY" "$DMG_PATH"

  # Step 9: Notarize
  echo "📤 Submitting for notarization..."
  xcrun notarytool submit "$DMG_PATH" \
    --apple-id "$APPLE_ID" \
    --password "$APPLE_APP_SPECIFIC_PASSWORD" \
    --team-id "$APPLE_TEAM_ID" \
    --wait

  # Check if notarization succeeded
  if [ $? -ne 0 ]; then
    echo "❌ Notarization failed! Check the log above."
    exit 1
  fi

  # Step 10: Staple
  echo "📎 Stapling notarization ticket..."
  xcrun stapler staple "$DMG_PATH"

  echo ""
  echo "✅ Build complete!"
  echo "📦 DMG: $DMG_PATH"
fi
