# Dependency Version Lock Documentation

## Overview

All dependencies in Speekium are now locked to specific version ranges to prevent:
- Supply chain attacks from malicious package updates
- Breaking changes from incompatible version updates
- Reproducibility issues across different environments
- Known security vulnerabilities

## Version Locking Strategy

### Major Version Locking
For stable packages with semantic versioning, we lock to major versions:
```toml
"package>=X.Y.Z,<(X+1).0.0"
```
This allows:
- ✅ Patch updates (bug fixes)
- ✅ Minor updates (backward-compatible features)
- ❌ Major updates (breaking changes)

### Exact Version Locking
For critical or unstable packages, we use exact versions:
```toml
"package==X.Y.Z"
```

## Dependency Versions and Rationale

### Audio & TTS Dependencies

#### edge-tts (>=7.2.7,<8.0.0)
- **Current**: 7.2.7
- **Strategy**: Major version lock to v7.x
- **Rationale**: TTS API stability; v8.x may introduce breaking changes
- **Update policy**: Review v8.x changelog before upgrading

#### sounddevice (>=0.5.3,<0.6.0)
- **Current**: 0.5.3
- **Strategy**: Minor version lock to v0.5.x
- **Rationale**: Audio I/O is critical; conservative approach to updates
- **Update policy**: Test thoroughly on target platforms before minor upgrade

### Machine Learning Dependencies

#### numpy (>=2.2.0,<3.0.0)
- **Current**: 2.2.6
- **Strategy**: Major version lock to v2.x
- **Rationale**: NumPy 2.x introduced breaking changes from 1.x; lock to v2 for stability
- **Update policy**: NumPy 3.x will require extensive testing
- **Note**: Already using NumPy 2.x (upgraded from 1.x)

#### scipy (>=1.15.0,<2.0.0)
- **Current**: 1.15.3
- **Strategy**: Major version lock to v1.x
- **Rationale**: Scientific computing stability
- **Update policy**: Review v2.x API changes before upgrading

#### torch (>=2.9.0,<3.0.0)
- **Current**: 2.9.1
- **Strategy**: Major version lock to v2.x
- **Rationale**: PyTorch v3.x may introduce breaking API changes
- **Update policy**: Wait for v3.x stability and review migration guides
- **Note**: Already using latest v2.x

#### torchaudio (>=2.9.0,<3.0.0)
- **Current**: 2.9.1
- **Strategy**: Match torch major version
- **Rationale**: torchaudio must match torch version for compatibility
- **Update policy**: Upgrade together with torch

#### funasr (>=1.3.0,<2.0.0)
- **Current**: 1.3.0
- **Strategy**: Major version lock to v1.x
- **Rationale**: ASR model API stability
- **Update policy**: Test ASR accuracy before v2.x upgrade

### Network & HTTP Dependencies

#### httpx (>=0.28.0,<1.0.0)
- **Current**: 0.28.1
- **Strategy**: Pre-1.0 lock (major version lock)
- **Rationale**: Pre-1.0 packages may have frequent API changes; lock until 1.0 release
- **Update policy**: Review changelog for each minor version

#### urllib3 (>=2.6.3,<3.0.0)
- **Current**: 2.6.3
- **Strategy**: Major version lock to v2.x
- **Rationale**: **SECURITY FIX** - v2.6.3 fixes CVE-2026-21441 (decompression bomb vulnerability)
- **Security severity**: Medium (CWE-409 - Resource exhaustion)
- **Update policy**: Monitor security advisories; upgrade immediately for security patches
- **Required**: v2.6.3+ is mandatory to prevent decompression bomb attacks

### Low-level Dependencies

#### llvmlite (>=0.46.0,<1.0.0)
- **Current**: 0.46.0
- **Strategy**: Pre-1.0 lock (major version lock)
- **Rationale**: LLVM compiler bindings; critical for JIT compilation
- **Update policy**: Test numba compatibility before upgrading
- **Note**: Upgraded from 0.42.0 to 0.46.0 for latest LLVM support

### GUI Dependencies

#### pywebview (>=6.1,<7.0.0)
- **Current**: 6.1
- **Strategy**: Major version lock to v6.x
- **Rationale**: Web view API stability for GUI
- **Update policy**: Test GUI functionality before v7.x upgrade

#### pynput (>=1.8.1,<2.0.0)
- **Current**: 1.8.1
- **Strategy**: Major version lock to v1.x
- **Rationale**: Global hotkey API stability
- **Update policy**: Test hotkey functionality before v2.x upgrade
- **Note**: Upgraded from 1.7.6 to 1.8.1 for bug fixes

#### pystray (>=0.19.5,<0.20.0)
- **Current**: 0.19.5
- **Strategy**: Minor version lock to v0.19.x
- **Rationale**: System tray API; conservative approach to avoid platform-specific issues
- **Update policy**: Test on all platforms (macOS/Linux/Windows) before v0.20 upgrade

#### Pillow (>=12.1.0,<13.0.0)
- **Current**: 12.1.0
- **Strategy**: Major version lock to v12.x
- **Rationale**: Image library for tray icons; v13.x may introduce breaking changes
- **Update policy**: Review security advisories; Pillow has frequent security updates
- **Note**: Upgraded from 10.2.0 to 12.1.0 for security fixes

### Logging

#### structlog (>=25.5.0,<26.0.0)
- **Current**: 25.5.0
- **Strategy**: Major version lock to v25.x
- **Rationale**: Structured logging API stability
- **Update policy**: Review API changes before v26.x upgrade
- **Note**: Upgraded from 24.1.0 to 25.5.0 for latest features

## Development Dependencies

### Testing & Quality Tools

#### pytest (>=7.0.0,<8.0.0)
- **Current**: 7.4.4
- **Strategy**: Major version lock to v7.x
- **Rationale**: Testing framework stability
- **Update policy**: Review v8.x plugin compatibility before upgrading

#### pytest-asyncio (>=0.23.0,<1.0.0)
- **Current**: 0.23.8
- **Strategy**: Pre-1.0 lock
- **Rationale**: Async testing support; pre-1.0 API may change
- **Update policy**: Wait for v1.0 release for stable API

#### pytest-cov (>=4.1.0,<5.0.0)
- **Current**: 4.1.0
- **Strategy**: Major version lock to v4.x
- **Rationale**: Coverage reporting stability

#### pytest-mock (>=3.12.0,<4.0.0)
- **Current**: 3.15.1
- **Strategy**: Major version lock to v3.x
- **Rationale**: Mocking utilities stability

#### pytest-timeout (>=2.2.0,<3.0.0)
- **Current**: 2.4.0
- **Strategy**: Major version lock to v2.x
- **Rationale**: Timeout control for hanging tests

#### ruff (>=0.1.0,<1.0.0)
- **Current**: 0.9.11
- **Strategy**: Pre-1.0 lock
- **Rationale**: Linter/formatter; pre-1.0 may have breaking changes
- **Update policy**: Monitor changelog for rule changes

#### pip-audit (>=2.10.0,<3.0.0)
- **Current**: 2.10.0
- **Strategy**: Major version lock to v2.x
- **Rationale**: Security vulnerability scanner
- **Update policy**: Upgrade for new vulnerability detection features
- **Note**: Added as dev dependency for continuous security scanning

## Security Audit Results

### Initial Scan (Before Lock)
```
Found 1 known vulnerability in 1 package
Name    Version ID             Fix Versions
urllib3 2.6.2   CVE-2026-21441 2.6.3
```

### Current Status (After Lock)
```
No known vulnerabilities found
```

**Security fix applied**: urllib3 upgraded to 2.6.3 to fix decompression bomb vulnerability (CVE-2026-21441).

## Maintenance Procedures

### Regular Security Scans
Run security scans weekly:
```bash
uv run pip-audit --desc
```

### Updating Dependencies

#### Minor/Patch Updates
For security patches or bug fixes:
```bash
# Update specific package
uv lock --upgrade-package package-name

# Sync environment
uv sync

# Run tests
uv run pytest
```

#### Major Version Updates
For major version upgrades (e.g., numpy 2.x → 3.x):
1. Create feature branch
2. Update version constraint in pyproject.toml
3. Run `uv lock`
4. Run full test suite
5. Test on all supported platforms
6. Review CHANGELOG for breaking changes
7. Update documentation
8. Merge after thorough testing

### CI/CD Integration
The CI pipeline automatically runs:
1. `uv lock --check` - Verify lock file is up-to-date
2. `uv run pip-audit` - Security vulnerability scan
3. `uv run pytest` - Full test suite

### Lock File Verification
Ensure lock file is synchronized:
```bash
uv lock --check
```

If out of sync:
```bash
uv lock
uv sync
```

## Version Update Calendar

### Weekly
- Run `uv run pip-audit` for security vulnerabilities
- Review security advisories for critical dependencies

### Monthly
- Review dependency updates from GitHub Dependabot
- Update patch versions for security fixes
- Run full test suite

### Quarterly
- Review minor version updates
- Evaluate new major versions for planning
- Update this documentation

## Breaking Change Migration Guide

When major updates are released:

1. **Evaluation Phase** (Week 1)
   - Read CHANGELOG and migration guides
   - Identify breaking changes
   - Assess impact on codebase

2. **Testing Phase** (Week 2-3)
   - Create migration branch
   - Update version constraints
   - Fix breaking changes
   - Run full test suite

3. **Validation Phase** (Week 4)
   - Test on all platforms
   - Performance benchmarking
   - User acceptance testing

4. **Deployment Phase** (Week 5)
   - Merge to main
   - Deploy to production
   - Monitor for issues

## Rollback Procedure

If an update causes issues:

```bash
# Revert pyproject.toml
git checkout HEAD~1 pyproject.toml

# Restore lock file
git checkout HEAD~1 uv.lock

# Sync environment
uv sync

# Verify
uv run pytest
```

## References

- [uv documentation](https://github.com/astral-sh/uv)
- [pip-audit documentation](https://github.com/pypa/pip-audit)
- [Semantic Versioning](https://semver.org/)
- [Python Package Security Best Practices](https://pypi.org/security/)

## Version History

- **2025-01-10**: Initial dependency lock implementation
  - All dependencies locked to version ranges
  - Security fix: urllib3 2.6.2 → 2.6.3 (CVE-2026-21441)
  - Upgraded: numpy 1.x → 2.x, Pillow 10.x → 12.x, structlog 24.x → 25.x
  - Added pip-audit for continuous security scanning
