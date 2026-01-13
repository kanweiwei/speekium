# Speekium CI/CD Architecture Analysis

## 📐 Overview

This document provides a comprehensive analysis of the Speekium CI/CD implementation using GitHub Actions for multi-platform desktop application builds.

## 🏗️ Architecture

### Build Pipeline Flow

```
┌─────────────────────────────────────────────────────────────┐
│                     GitHub Repository                         │
│                     (Push / Tag)                             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  GitHub Actions Trigger                        │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ workflow_dispatch: Manual trigger                       ││
│  │ push branches: [main]: Unsigned builds                 ││
│  │ push tags: ['v*']: Signed builds + Release             ││
│  └─────────────────────────────────────────────────────────┘│
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                 Matrix Build Strategy                         │
│  ┌────────────────────┐  ┌──────────────────────┐           │
│  │ macOS-latest       │  │ Windows-latest       │           │
│  │ (universal binary) │  │ (x86_64)             │           │
│  └────────────────────┘  └──────────────────────┘           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  Parallel Build Process                       │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Job 1: Build (Unsigned)                                 ││
│  │   - Runs on every push to main                          ││
│  │   - No code signing                                     ││
│  │   - Uploads artifacts                                   ││
│  └─────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Job 2: Build-Signed (Conditional)                       ││
│  │   - Runs only on tags/manual dispatch                   ││
│  │   - Code signing + notarization                         ││
│  │   - Uploads signed artifacts                            ││
│  └─────────────────────────────────────────────────────────┘│
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Job 3: Release (Conditional)                     │
│   - Creates GitHub release                                  │
│   - Uploads all artifacts as release assets                 │
│   - Generates release notes                                 │
└─────────────────────────────────────────────────────────────┘
```

## 🔧 Technical Stack

### Core Technologies

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **CI/CD Platform** | GitHub Actions | Latest | Workflow orchestration |
| **Build Tool** | Tauri Action | v0 | Tauri app building |
| **Frontend** | Node.js + npm | 20+ | Dependency management |
| **Backend** | Rust + Cargo | Stable | Native code compilation |
| **macOS Target** | Universal Binary | - | Intel + Apple Silicon |
| **Windows Target** | x86_64 | - | 64-bit Windows |

### GitHub Actions Components

```yaml
# Key Actions Used
- actions/checkout@v4           # Checkout repository
- actions/setup-node@v4         # Setup Node.js environment
- dtolnay/rust-toolchain@stable # Setup Rust toolchain
- swatinem/rust-cache@v2        # Cache Rust dependencies
- tauri-apps/tauri-action@v0    # Build Tauri apps
- actions/upload-artifact@v4    # Upload build artifacts
- softprops/action-gh-release@v2 # Create GitHub releases
```

## 📦 Build Targets

### macOS Universal Binary

**Target**: `universal-apple-darwin`

**Architecture**: Fat binary containing both:
- **x86_64**: Intel Macs (2006-2020)
- **arm64**: Apple Silicon Macs (M1/M2/M3, 2020-present)

**Output Formats**:
- `.dmg`: Disk image installer (recommended for distribution)
- `.app`: Application bundle (inside .dmg)

**Minimum System Version**: macOS 10.13 (High Sierra)

**Signing Process**:
```
Developer ID Application Certificate
         ↓
    Code Signing
         ↓
   Building .app
         ↓
   Creating .dmg
         ↓
    Stapling .dmg
         ↓
  Notarization
         ↓
   Final Release
```

### Windows x86_64

**Target**: `x86_64-pc-windows-msvc`

**Architecture**: 64-bit Windows only

**Output Formats**:
- `.msi`: Windows Installer (recommended)
- `.exe`: NSIS installer (alternative)

**Digest Algorithm**: SHA-256

**Signing Process**:
```
Authenticode Certificate
         ↓
    Code Signing
         ↓
   Building .exe/.msi
         ↓
    Timestamping
         ↓
   Final Release
```

## 🔐 Security & Signing

### macOS Security Chain

```
┌─────────────────────────────────────────────────────────────┐
│                    Apple Developer Account                     │
│                        ↓                                      │
│              Developer ID Certificate                          │
│                        ↓                                      │
│                 Code Signing                                  │
│                        ↓                                      │
│                  Notarization                                 │
│                        ↓                                      │
│              Gatekeeper Compliance                            │
└─────────────────────────────────────────────────────────────┘
```

**Key Components**:

1. **Developer ID Certificate**
   - Issued by Apple
   - Valid for 1 year
   - Identifies the developer
   - Required for Gatekeeper

2. **Code Signing**
   - Cryptographic signature
   - Tamper detection
   - Publisher verification
   - Executable validation

3. **Notarization**
   - Apple scans for malware
   - Issues notarization ticket
   - Required for macOS 10.15+
   - Process takes 1-5 minutes

4. **Stapling**
   - Attaches ticket to .dmg
   - Offline verification
   - Faster user experience

### Windows Security Chain

```
┌─────────────────────────────────────────────────────────────┐
│                   Certificate Authority                        │
│                        ↓                                      │
│              Code Signing Certificate                          │
│                        ↓                                      │
│                 Authenticode Signing                          │
│                        ↓                                      │
│                   Timestamping                                 │
│                        ↓                                      │
│              SmartScreen Reputation                            │
└─────────────────────────────────────────────────────────────┘
```

**Key Components**:

1. **Code Signing Certificate**
   - Issued by trusted CA (DigiCert, Sectigo, etc.)
   - Valid for 1-3 years
   - Identifies the publisher
   - Required for SmartScreen

2. **Authenticode Signing**
   - Microsoft's code signing format
   - Publisher identity
   - Integrity verification

3. **Timestamping**
   - Proves when code was signed
   - Valid after certificate expires
   - Uses timestamp server

## 🔑 Environment Variables Deep Dive

### Required Variables Matrix

| Variable | Platform | Required For | Format | Source |
|----------|----------|--------------|--------|--------|
| `GH_TOKEN` | All | Release creation | Auto-generated | GitHub |
| `CSC_LINK` | macOS | Code signing | Base64 string | Certificate export |
| `CSC_LINK` | Windows | Code signing | Base64 string | Certificate export |
| `CSC_KEY_PASSWORD` | All | Certificate unlock | Plain text | Export password |
| `APPLE_ID` | macOS | Notarization | Email address | Apple account |
| `APPLE_PASSWORD` | macOS | Notarization | `xxxx-xxxx-xxxx-xxxx` | App-specific password |
| `APPLE_TEAM_ID` | macOS | Notarization | 10-char string | Developer account |

### Variable Injection Flow

```
GitHub Secrets (Encrypted)
         ↓
GitHub Actions Runtime
         ↓
Environment Variables
         ↓
Tauri Action
         ↓
Build Process
```

### Security Considerations

1. **Secret Storage**
   - Encrypted at rest by GitHub
   - Only accessible in workflows
   - Never logged in plain text

2. **Secret Access Scope**
   - Repository-level secrets
   - Environment-specific secrets (optional)
   - Organization-level secrets (optional)

3. **Secret Rotation**
   - Certificates expire annually
   - Passwords should rotate periodically
   - App-specific passwords can be revoked

## 📊 Performance Metrics

### Build Times (Estimated)

| Platform | Unsigned | Signed | Notarized |
|----------|----------|--------|-----------|
| macOS | ~8 min | ~10 min | ~15 min |
| Windows | ~6 min | ~8 min | N/A |

### Resource Usage

| Runner | CPU | Memory | Disk |
|--------|-----|--------|------|
| macOS-latest | 3-core (Xeon) | 14 GB | 14 GB SSD |
| Windows-latest | 2-core | 7 GB | 14 GB SSD |

### Artifact Sizes (Estimated)

| Platform | Artifact | Size |
|----------|----------|------|
| macOS | .dmg (universal) | ~150 MB |
| macOS | .app | ~140 MB |
| Windows | .msi | ~120 MB |
| Windows | .exe | ~130 MB |

## 🔄 Workflow States

### State Diagram

```
┌─────────┐
│  Idle   │
└────┬────┘
     │
     ├─→ Push to main
     │   ↓
     │  ┌─────────────┐
     │  │ Build (All) │
     │  │ Unsigned    │
     │  └──────┬──────┘
     │         │
     │         ├─→ Upload Artifacts
     │         │   ↓
     │         │  ┌──────────────┐
     │         │  │   Success    │
     │         │  └──────────────┘
     │
     ├─→ Tag Release
     │   ↓
     │  ┌──────────────┐
     │  │ Build Signed │
     │  └──────┬───────┘
     │         │
     │         ├─→ Upload Artifacts
     │         │   ↓
     │         │  ┌─────────────────┐
     │         │  │ Create Release  │
     │         │  └──────┬──────────┘
     │         │         │
     │         │         └─→ Complete
     │
     └─→ Manual Dispatch
         ↓
        User selects build type
```

## 🛠️ Customization Options

### Build Configuration

In `src-tauri/tauri.conf.json`:

```json
{
  "bundle": {
    "targets": "all",  // or "dmg", "msi", "app", "exe"
    "macOS": {
      "minimumSystemVersion": "10.13",
      "signingIdentity": null  // Auto-detected from CSC_LINK
    },
    "windows": {
      "digestAlgorithm": "sha256",
      "timestampUrl": ""  // Optional: custom timestamp server
    }
  }
}
```

### Workflow Triggers

```yaml
on:
  push:
    branches: [main]      # Adjust branch names
    tags:
      - 'v*'             # Version tags
  pull_request:
    branches: [main]     # PR builds (optional)
  workflow_dispatch:     # Manual trigger
    inputs:
      build-signed:
        description: 'Build signed artifacts'
        required: false
        type: boolean
        default: false
```

## 📈 Monitoring & Observability

### Logs Access

1. **GitHub Actions UI**
   - Repository → Actions → Select workflow run
   - View logs for each job/step
   - Download logs archive

2. **Build Artifacts**
   - Actions → Workflow run → Artifacts section
   - Download for 90 days (default)

3. **Release Assets**
   - Repository → Releases → Select version
   - Downloadable forever

### Failure Notifications

```yaml
# Optional: Add to workflow
- name: Notify on failure
  if: failure()
  uses: actions/github-script@v7
  with:
    script: |
      github.rest.issues.create({
        owner: context.repo.owner,
        repo: context.repo.repo,
        title: 'Build failed: ${{ github.run_number }}',
        body: 'Workflow ${{ github.workflow }} failed in run ${{ github.run_number }}'
      })
```

## 🚀 Next Steps

1. **Set up secrets**: Follow [Quick Start Guide](./CICD_QUICKSTART.md)
2. **Test unsigned build**: Push to `main` branch
3. **Test signed build**: Create a test tag
4. **Monitor first release**: Check all artifacts
5. **Configure automation**: Set up scheduled builds (optional)

## 📚 References

- [Tauri GitHub Action Documentation](https://github.com/tauri-apps/tauri-action)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [macOS Code Signing Guide](https://developer.apple.com/support/code-signing/)
- [Windows Code Signing](https://docs.microsoft.com/en-us/windows/win32/seccrypto/cryptography-tools)

---

**Last Updated**: 2025-01-13
**Maintainer**: Speekium Team
