# CI/CD Setup Guide for Speekium

This guide explains how to set up GitHub Actions for building and releasing Speekium desktop applications on macOS and Windows.

## Overview

The CI/CD pipeline uses GitHub Actions to:
- Build unsigned apps on every push to `main` branch
- Build signed and notarized apps on git tags (releases)
- Create GitHub releases with artifacts

## Required GitHub Secrets

Navigate to: **Repository Settings → Secrets and variables → Actions → New repository secret**

### 1. `GH_TOKEN` (Required)
**Purpose**: GitHub token for creating releases

**Value**: Automatically provided by GitHub Actions, no need to configure manually.

**Usage**: Used by `tauri-action` to upload release assets.

---

### 2. `CSC_LINK` (Required for code signing)
**Purpose**: Base64-encoded code signing certificate

**How to obtain**:

#### For macOS:
1. Go to [Apple Developer → Certificates](https://developer.apple.com/account/resources/certificates/list)
2. Create a **Developer ID Application** certificate
3. Download the certificate (.cer file)
4. Double-click to install it in Keychain Access
5. Export the certificate as .p12 file:
   - Open Keychain Access
   - Find "Developer ID Application" certificate
   - Right-click → Export
   - Save as `.p12` file
   - Set a password (you'll need this for `CSC_KEY_PASSWORD`)
6. Convert to base64:
   ```bash
   base64 -i certificate.p12 | pbcopy  # macOS
   base64 -w 0 certificate.p12          # Linux
   ```
7. Paste the base64 string as the secret value

#### For Windows:
1. Purchase a code signing certificate from:
   - DigiCert
   - Sectigo
   - GlobalSign
   - Or any trusted CA
2. Download the certificate in `.pfx` format
3. Convert to base64:
   ```powershell
   [Convert]::ToBase64String([IO.File]::ReadAllBytes("certificate.pfx"))
   ```
4. Paste the base64 string as the secret value

---

### 3. `CSC_KEY_PASSWORD` (Required)
**Purpose**: Password for the code signing certificate

**Value**: The password you set when exporting the `.p12` (macOS) or `.pfx` (Windows) file

---

### 4. `APPLE_ID` (Required for macOS notarization)
**Purpose**: Your Apple ID email address for app notarization

**How to obtain**:
1. Use your existing Apple ID associated with Apple Developer account
2. Or create a new Apple ID (must be enrolled in Apple Developer Program)

**Example**: `your-email@example.com`

---

### 5. `APPLE_APP_SPECIFIC_PASSWORD` (Required for macOS notarization)
**Purpose**: App-specific password for Apple ID

**How to generate**:
1. Go to [appleid.apple.com](https://appleid.apple.com)
2. Sign in with your Apple ID
3. Go to **Security** section
4. Click **Generate Password** (under App-Specific Passwords)
5. Label it: "Speekium CI/CD"
6. Copy the generated password (format: `abcd-efgh-ijkl-mnop`)

**Note**: You'll need Two-Factor Authentication enabled on your Apple ID

---

### 6. `APPLE_TEAM_ID` (Required for macOS notarization)
**Purpose**: Your Apple Developer Team ID

**How to find**:
1. Go to [Apple Developer → Account](https://developer.apple.com/account)
2. Look for **Team ID** in the membership details section
3. Usually a 10-character alphanumeric string (e.g., `ABCD123456`)

**Alternative method**:
```bash
# Run on macOS with Xcode installed
xcrun altool --list-providers -u "your-apple-id@example.com" -p "your-app-specific-password"
```

---

## Secrets Summary

| Secret Name | Required For | Format | Example |
|------------|--------------|--------|---------|
| `GH_TOKEN` | All platforms | Auto-provided | *(auto)* |
| `CSC_LINK` | macOS & Windows | Base64 string | `MIIEx... (very long)` |
| `CSC_KEY_PASSWORD` | macOS & Windows | Plain text | `MyP@ssw0rd!` |
| `APPLE_ID` | macOS only | Email address | `user@example.com` |
| `APPLE_APP_SPECIFIC_PASSWORD` | macOS only | `xxxx-xxxx-xxxx-xxxx` | `abcd-efgh-ijkl-mnop` |
| `APPLE_TEAM_ID` | macOS only | 10-character string | `ABCD123456` |

---

## Workflow Triggers

The CI/CD workflow runs in the following scenarios:

### 1. **Unsigned Builds** (Every push to main)
```bash
git push origin main
```
**Builds**: macOS universal, Windows x86_64
**Artifacts**: Unsigned apps uploaded as GitHub Actions artifacts
**No signing**: Apps can be installed but may show security warnings

### 2. **Signed Builds** (Git tags/releases)
```bash
git tag v1.0.0
git push origin v1.0.0
```
**Builds**: Signed and notarized apps
**Creates**: GitHub release with downloadable assets
**Requirements**: All secrets must be configured

### 3. **Manual Trigger**
Go to **Actions → Build and Release → Run workflow**

---

## Testing the Setup

### 1. Test Unsigned Build
Push any commit to `main` branch:
```bash
echo "test" >> test.txt
git add test.txt
git commit -m "Test CI/CD"
git push origin main
```

Check the Actions tab to see if the build succeeds.

### 2. Test Signed Build (with dummy certificate)
**Note**: This requires real certificates. For testing, you can:
1. Create a self-signed certificate for testing (macOS only)
2. Skip signing and just test the build process

### 3. Test Release Process
```bash
# Create a test release tag
git tag v0.0.1-test
git push origin v0.0.1-test
```

This will trigger:
- Unsigned builds
- Signed builds (if secrets are configured)
- GitHub release creation

---

## Troubleshooting

### Common Issues

#### 1. **"Certificate not found" error**
**Solution**:
- Verify `CSC_LINK` is correctly base64-encoded
- Check `CSC_KEY_PASSWORD` matches the certificate password
- Ensure certificate hasn't expired

#### 2. **"Notarization failed" error**
**Solution**:
- Verify `APPLE_ID` is correct
- Regenerate `APPLE_APP_SPECIFIC_PASSWORD`
- Check `APPLE_TEAM_ID` matches your developer account
- Ensure your Apple Developer account is active

#### 3. **"Team ID not found" error**
**Solution**:
```bash
# Verify your Team ID
xcrun altool --list-providers \
  -u "your-apple-id@example.com" \
  -p "your-app-specific-password"
```

#### 4. **Windows signing fails**
**Solution**:
- Ensure certificate is in `.pfx` format
- Verify certificate includes private key
- Check certificate hasn't expired
- Confirm certificate is from a trusted CA

---

## Security Best Practices

1. **Never commit certificates** to the repository
2. **Use strong passwords** for certificate exports
3. **Rotate certificates** before they expire (usually 1 year)
4. **Restrict secret access** in GitHub repository settings
5. **Use separate certificates** for development and production
6. **Monitor certificate usage** and expiration dates

---

## Advanced Configuration

### Parallel Builds
The workflow builds both macOS and Windows in parallel for faster completion.

### Universal macOS Build
The `universal-apple-darwin` target creates a single app that runs on both Intel and Apple Silicon Macs.

### Artifact Retention
Artifacts are retained for 90 days by default. Change this in workflow:
```yaml
- name: Upload macOS artifacts
  uses: actions/upload-artifact@v4
  with:
    retention-days: 30  # Customize retention period
```

---

## Additional Resources

- [Tauri GitHub Action](https://github.com/tauri-apps/tauri-action)
- [Apple Code Signing Guide](https://developer.apple.com/support/code-signing/)
- [Apple Notarization Guide](https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution)
- [Windows Code Signing](https://docs.microsoft.com/en-us/windows/win32/seccrypto/cryptography-tools)
- [GitHub Actions Secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets)

---

## Need Help?

If you encounter issues:
1. Check the Actions tab for detailed error logs
2. Review the troubleshooting section above
3. Open an issue on GitHub with:
   - Error messages
   - Workflow run link
   - Platform and tool versions
