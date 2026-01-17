# CI/CD Security Integration

**Date**: 2025-01-10
**Version**: 1.0
**Status**: Active

## 📋 Overview

This document describes the security scanning and validation processes integrated into the Speekium project's development workflow. We use automated security tools to identify and prevent vulnerabilities before they reach production.

**Key Security Tools**:
- **Bandit**: Python code security scanner (SAST)
- **Safety**: Dependency vulnerability scanner (SCA)
- **GitHub Actions**: Automated CI/CD security checks

**Security Objectives**:
- ✅ Zero HIGH/MEDIUM severity vulnerabilities
- ✅ Automated security scanning on every commit
- ✅ Fast feedback loop for developers (< 30 seconds locally)
- ✅ Comprehensive audit trail with reports and artifacts

## 🔧 Tools Introduction

### Bandit (Python Security Linter)

**Version**: 1.9.2
**Purpose**: Static Application Security Testing (SAST) for Python code

**What it checks**:
- Hardcoded passwords and secrets
- SQL injection vulnerabilities
- Shell injection risks
- Insecure cryptographic functions
- Unsafe file operations
- Insecure deserialization
- Common security anti-patterns

**Configuration**: `.bandit` file in project root

**Severity Levels**:
- **HIGH**: Critical security vulnerabilities requiring immediate fix
- **MEDIUM**: Significant issues that should be addressed
- **LOW**: Minor issues or potential false positives

**Current Status**: ✅ 0 HIGH, 0 MEDIUM, 16 LOW (acceptable)

### Safety (Dependency Vulnerability Scanner)

**Version**: 3.7.0
**Purpose**: Software Composition Analysis (SCA) for Python dependencies

**What it checks**:
- Known vulnerabilities in installed packages (CVE database)
- Vulnerable package versions
- Security advisories from PyUp.io
- Open-source vulnerability databases

**Current Status**: ✅ 0 vulnerabilities in 143 scanned packages

**Note**: Safety 3.7.0 does not require configuration files. It runs directly against the installed environment.

### GitHub Actions Workflow

**File**: `.github/workflows/security.yml`
**Triggers**:
- Push to `main` or `security-*` branches
- Pull requests to `main`
- Manual workflow dispatch

**What it does**:
1. Sets up Python 3.11 environment
2. Installs dependencies with `uv`
3. Runs Bandit security scanner
4. Runs Safety dependency checker
5. Uploads security reports as artifacts (30-day retention)
6. Fails build on HIGH/MEDIUM severity issues

**Artifact Retention**: Security reports are stored for 30 days for audit purposes

## 💻 Local Usage

### Quick Start

Run all security checks locally:

```bash
./scripts/security-check.sh
```

This will:
- Scan all Python files with Bandit
- Check all dependencies with Safety
- Display results with colored output
- Generate JSON reports (bandit-report.json)

**Expected runtime**: < 30 seconds

### Command Options

```bash
# Run with verbose output
./scripts/security-check.sh --verbose

# Generate HTML reports
./scripts/security-check.sh --html
# or
./scripts/security-check.sh --report

# Don't fail on MEDIUM severity issues (for development)
./scripts/security-check.sh --no-fail-medium

# Show help and examples
./scripts/security-check.sh --help
```

### Running Individual Tools

#### Bandit

```bash
# Scan project files
uv run bandit -r . -ll

# Generate JSON report
uv run bandit -r . -ll -f json -o bandit-report.json

# Generate HTML report
uv run bandit -r . -ll -f html -o bandit-report.html
```

#### Safety

```bash
# Check all dependencies
uv run safety check

# Verbose output
uv run safety check --detailed-output
```

### Suppressing False Positives

If Bandit reports a false positive or intentional security exception:

```python
# Add nosec comment with explanation
def load_model(self):
    # Security note: trust_repo=True required for official Silero VAD model
    # This is a verified, official PyTorch Hub repository
    self.model = torch.hub.load(  # nosec B614
        repo_or_dir="snakers4/silero-vad",
        model="silero_vad",
        trust_repo=True,
    )
```

**IMPORTANT**: Always document WHY the exception is safe in a comment above the `# nosec` directive.

## 🔄 CI/CD Integration

### Automated Checks

Every push to protected branches automatically runs:

1. **Syntax & Type Checks** (via lint.yml workflow)
2. **Security Scans** (via security.yml workflow)
3. **Unit & Integration Tests** (via test.yml workflow)

### Workflow Details

**Security Workflow** (`.github/workflows/security.yml`):

```yaml
name: Security Checks

on:
  push:
    branches: [main, security-*]
  pull_request:
    branches: [main]
  workflow_dispatch:

jobs:
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - Checkout code
      - Set up Python 3.11
      - Install uv package manager
      - Install project dependencies
      - Run Bandit (fails on HIGH/MEDIUM)
      - Run Safety (fails on any vulnerabilities)
      - Upload security reports as artifacts
```

### Viewing Security Reports

1. Go to GitHub Actions tab
2. Click on a workflow run
3. Scroll to "Artifacts" section
4. Download security reports:
   - `bandit-security-report` (JSON format)
   - `safety-security-report` (if generated)

Reports are retained for 30 days.

### Branch Protection

Recommended branch protection rules for `main`:

- ✅ Require status checks to pass before merging
- ✅ Require "Security Scanning" check
- ✅ Require "Tests" check
- ✅ Require branches to be up to date

## 🐛 Troubleshooting

### Common Issues

#### Issue: Bandit scan is slow

**Cause**: Scanning entire project including `node_modules`, `.venv`, etc.

**Solution**: Use the provided security-check.sh script which only scans Python files in the project root.

```bash
./scripts/security-check.sh  # Fast (< 30s)
bandit -r .                   # Slow (can timeout)
```

#### Issue: Safety JSON output errors

**Cause**: Safety 3.7.0 has inconsistent JSON output format.

**Solution**: The security-check.sh script parses text output instead. Use it for reliable results.

```bash
./scripts/security-check.sh  # Reliable
safety check --json          # May fail
```

#### Issue: False positive from Bandit

**Solution**: Add `# nosec B[code]` comment with explanation

```python
# Test file uses /tmp for simplicity - not a security risk
temp_file = "/tmp/test.mp3"  # nosec B108
```

**Documentation Required**: Always document WHY the exception is safe.

#### Issue: GitHub Actions workflow fails but local check passes

**Possible Causes**:
1. Different Python versions (CI uses 3.11)
2. Different dependency versions
3. Environment-specific issues

**Solution**:
```bash
# Test with exact CI environment locally
docker run -it python:3.11 bash
# Then run security checks
```

### Getting Help

1. Check this documentation first
2. Review security reports in `bandit-report.json`
3. Check GitHub Actions logs for detailed error messages
4. Review OWASP Top 10 guidelines
5. Consult security team for critical issues

## 🔒 Security Best Practices

### Code Security

1. **Never commit secrets or credentials**
   - Use environment variables
   - Use `.env` files (gitignored)
   - Use secret management tools (e.g., GitHub Secrets)

2. **Validate all user input**
   - Sanitize file paths
   - Validate API parameters
   - Escape SQL queries (use parameterized queries)

3. **Use secure defaults**
   - Enable HTTPS by default
   - Use secure random generators (`secrets` module)
   - Set restrictive file permissions

4. **Keep dependencies updated**
   - Run `uv sync` regularly
   - Monitor `safety check` results
   - Review security advisories

### Dependency Security

1. **Pin dependency versions**
   - Use version constraints in `pyproject.toml`
   - Lock dependencies with `uv.lock`
   - Review updates before upgrading

2. **Minimize dependencies**
   - Only add necessary packages
   - Audit new dependencies
   - Remove unused dependencies

3. **Monitor for vulnerabilities**
   - Run Safety checks regularly
   - Subscribe to security advisories
   - Enable Dependabot alerts

### CI/CD Security

1. **Fail fast on security issues**
   - Block merges with HIGH/MEDIUM issues
   - Run security checks early in pipeline
   - Provide clear failure messages

2. **Maintain audit trail**
   - Keep security reports for 30 days
   - Log all security scan results
   - Track issue resolution

3. **Regular security reviews**
   - Weekly dependency scans
   - Monthly code security audits
   - Quarterly penetration testing (if applicable)

## 📚 References

### Official Documentation

- [Bandit Documentation](https://bandit.readthedocs.io/)
- [Safety Documentation](https://pyup.io/safety/)
- [GitHub Actions Security](https://docs.github.com/en/actions/security-guides)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)

### Security Standards

- [CWE (Common Weakness Enumeration)](https://cwe.mitre.org/)
- [CVE (Common Vulnerabilities and Exposures)](https://cve.mitre.org/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)

### Python Security

- [Python Security Guide](https://python.readthedocs.io/en/stable/library/security_warnings.html)
- [PyPI Security](https://warehouse.pypa.io/security.html)
- [Python Package Index Advisories](https://github.com/pypa/advisory-database)

## 📝 Changelog

### Version 1.0 (2025-01-10)

**Initial Release**:
- Integrated Bandit 1.9.2 for Python code scanning
- Integrated Safety 3.7.0 for dependency scanning
- Created GitHub Actions security workflow
- Created local security-check.sh script
- Fixed 3 MEDIUM severity issues with documented exceptions
- Achieved 0 HIGH/MEDIUM vulnerabilities status
- Comprehensive documentation and troubleshooting guide

**Security Scan Results**:
- Bandit: 0 HIGH, 0 MEDIUM, 16 LOW (acceptable)
- Safety: 0 vulnerabilities in 143 packages
- All tests passing: 150 passed, 4 skipped

---

**Maintainers**: Security Team
**Last Updated**: 2025-01-10
**Next Review**: 2025-02-10
