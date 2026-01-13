# CI/CD Quick Start Guide

Quick reference for setting up Speekium CI/CD with GitHub Actions.

## 📋 Prerequisites Checklist

- [ ] GitHub repository with admin access
- [ ] Apple Developer Account ($99/year) - for macOS signing
- [ ] Code Signing Certificate - for Windows (optional, ~$100-500/year)
- [ ] Node.js 20+ installed locally
- [ ] Rust toolchain installed locally

## 🔐 Required GitHub Secrets

### For macOS builds (Required)

| Secret | Description | How to Get |
|--------|-------------|------------|
| `CSC_LINK` | Base64-encoded .p12 certificate | Export from Keychain Access → `base64 -i cert.p12 \| pbcopy` |
| `CSC_KEY_PASSWORD` | Certificate export password | Set when exporting .p12 file |
| `APPLE_ID` | Your Apple ID email | Your existing Apple ID email |
| `APPLE_APP_SPECIFIC_PASSWORD` | App-specific password | appleid.apple.com → Security → Generate Password |
| `APPLE_TEAM_ID` | Your 10-character Team ID | developer.apple.com → Membership Details |

### For Windows builds (Optional)

| Secret | Description | How to Get |
|--------|-------------|------------|
| `CSC_LINK` | Base64-encoded .pfx certificate | Purchase from CA → `base64 -w 0 cert.pfx` |
| `CSC_KEY_PASSWORD` | Certificate password | Set when exporting .pfx file |

## 🚀 Quick Setup

### Step 1: Add Secrets to GitHub

1. Go to your repository on GitHub
2. Navigate to **Settings → Secrets and variables → Actions**
3. Click **New repository secret**
4. Add secrets listed above (one at a time)

### Step 2: Test Unsigned Build

```bash
# Push to main branch (triggers unsigned build)
git commit --allow-empty -m "Test CI/CD"
git push origin main
```

Check the **Actions** tab to see the build progress.

### Step 3: Create a Release

```bash
# Tag a release (triggers signed build + GitHub release)
git tag v1.0.0
git push origin v1.0.0
```

This will:
- Build signed apps for macOS and Windows
- Notarize macOS app
- Create GitHub release with downloads

## 📦 Build Artifacts

### Unsigned Builds (on push to main)
- **macOS**: Universal binary (Intel + Apple Silicon)
  - `Speerium_<version>_universal.dmg`
  - `Speerium.app` (inside .dmg)
- **Windows**: x86_64 installer
  - `Speerium_<version>_x64-setup.msi`
  - `Speerium_<version>_x64-setup.exe`

### Signed Builds (on git tags)
- All artifacts from unsigned build, plus:
- Code signed with your certificate
- macOS: Notarized by Apple
- Windows: Authenticode signature

## 🔧 macOS Certificate Setup

### 1. Create Certificate

```bash
# Open Keychain Access
open /Applications/Utilities/Keychain\ Access.app

# Or create via command line (requires Xcode)
# This opens the certificate assistant
open -a Xcode
```

1. In Xcode: **Xcode → Settings → Accounts**
2. Select your Apple ID → **Manage Certificates**
3. Click **+** → **Developer ID Application**
4. Follow the prompts

### 2. Export Certificate

```bash
# Find the certificate in Keychain Access
# Right-click → Export → Save as .p12
# Set a password (remember it for CSC_KEY_PASSWORD)

# Convert to base64
base64 -i certificate.p12 | pbcopy

# Paste the output into GitHub secret: CSC_LINK
```

## 🪟 Windows Certificate Setup

### 1. Purchase Certificate

Buy from a trusted Certificate Authority:
- [DigiCert](https://www.digicert.com/signing/code-signing-certificates)
- [Sectigo](https://sectigo.com/ssl-certificates-tls/code-signing)
- [GlobalSign](https://www.globalsign.com/en/code-signing-certificate)

### 2. Download and Convert

```powershell
# Download certificate in .pfx format
# Convert to base64
[Convert]::ToBase64String([IO.File]::ReadAllBytes("certificate.pfx")) | Set-Clipboard

# Paste the output into GitHub secret: CSC_LINK
```

## 📝 Environment Variables Reference

```yaml
env:
  # Required for all builds
  GH_TOKEN: ${{ secrets.GH_TOKEN }}

  # macOS signing
  CSC_LINK: ${{ secrets.CSC_LINK }}
  CSC_KEY_PASSWORD: ${{ secrets.CSC_KEY_PASSWORD }}

  # macOS notarization
  APPLE_ID: ${{ secrets.APPLE_ID }}
  APPLE_PASSWORD: ${{ secrets.APPLE_APP_SPECIFIC_PASSWORD }}
  APPLE_TEAM_ID: ${{ secrets.APPLE_TEAM_ID }}
```

## 🔄 Workflow Triggers

| Trigger | What Happens | When |
|---------|--------------|------|
| Push to `main` | Unsigned builds | Every push |
| Git tag `v*` | Signed builds + Release | When tagging |
| Manual | Either (selectable) | Via Actions UI |

## 🧪 Testing Checklist

- [ ] Unsigned build works on push to main
- [ ] macOS universal app runs on Intel Mac
- [ ] macOS universal app runs on Apple Silicon Mac
- [ ] Windows installer creates desktop shortcut
- [ ] Signed macOS app doesn't show security warning
- [ ] Signed Windows app shows verified publisher
- [ ] GitHub release created on tag push
- [ ] Downloadable artifacts are correct

## ⚠️ Common Issues

### Issue: "Certificate not found"
**Fix**: Check `CSC_LINK` is base64-encoded correctly

### Issue: "Notarization failed"
**Fix**:
- Verify `APPLE_ID` and `APPLE_APP_SPECIFIC_PASSWORD`
- Check `APPLE_TEAM_ID` is correct
- Ensure 2FA is enabled on Apple ID

### Issue: "Team ID not found"
**Fix**: Run this to verify:
```bash
xcrun altool --list-providers \
  -u "your-apple-id@example.com" \
  -p "your-app-specific-password"
```

## 📚 Additional Resources

- [Full Setup Guide](./CICD_SETUP.md)
- [Tauri Documentation](https://tauri.app/v1/guides/building/)
- [GitHub Actions Docs](https://docs.github.com/en/actions)

## 💡 Pro Tips

1. **Test without signing first**: Push to main before creating a tag
2. **Use draft releases**: Set `draft: true` in workflow for testing
3. **Monitor Actions tab**: Check logs for detailed error messages
4. **Keep certificates safe**: Never commit them to git
5. **Set reminders**: Certificates expire in 1 year

## 🆘 Need Help?

1. Check the [troubleshooting section](./CICD_SETUP.md#troubleshooting)
2. Review GitHub Actions logs
3. Open an issue with error details

---

**Ready to build?** Push a commit to `main` and watch the magic happen! ✨
