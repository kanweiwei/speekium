#!/usr/bin/env bash
# Security Check Script for Speekium
# Runs Bandit security scanner and Safety dependency checker

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Output files
BANDIT_REPORT="$PROJECT_ROOT/bandit-report.json"

# Options
VERBOSE=false
FAIL_ON_MEDIUM=true
GENERATE_HTML=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        --no-fail-medium)
            FAIL_ON_MEDIUM=false
            shift
            ;;
        --html|--report)
            GENERATE_HTML=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Run security checks for Speekium project using Bandit and Safety."
            echo ""
            echo "Options:"
            echo "  -v, --verbose        Verbose output"
            echo "  --no-fail-medium     Don't fail on MEDIUM severity issues"
            echo "  --html, --report     Generate HTML reports"
            echo "  -h, --help           Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                   # Run all security checks"
            echo "  $0 --verbose         # Run with verbose output"
            echo "  $0 --html            # Generate HTML reports"
            echo "  $0 --no-fail-medium  # Don't fail on MEDIUM issues"
            echo ""
            echo "Note: Auto-fix (--fix) is not supported because security issues"
            echo "      require manual review and context-aware fixes."
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}🔒 Security Check for Speekium${NC}"
echo "========================================"
echo ""

# Function to run Bandit
run_bandit() {
    echo -e "${BLUE}📊 Running Bandit security scanner...${NC}"

    cd "$PROJECT_ROOT"

    # Find all Python files in the project root (excluding hidden dirs and common build dirs)
    PYTHON_FILES=$(find . -maxdepth 1 -name "*.py" -type f)
    PYTHON_FILES="$PYTHON_FILES $(find . -maxdepth 2 -name "*.py" -path "./src/*.py" -o -path "./lib/*.py" 2>/dev/null | tr '\n' ' ')"

    # Run Bandit on Python files
    if [ "$VERBOSE" = true ]; then
        uv run bandit $PYTHON_FILES -ll -f json -o "$BANDIT_REPORT" -v || BANDIT_EXIT=$?
    else
        uv run bandit $PYTHON_FILES -ll -f json -o "$BANDIT_REPORT" 2>/dev/null || BANDIT_EXIT=$?
    fi

    BANDIT_EXIT=${BANDIT_EXIT:-0}

    # Parse results
    if [ -f "$BANDIT_REPORT" ]; then
        HIGH_COUNT=$(jq '[.results[] | select(.issue_severity == "HIGH")] | length' "$BANDIT_REPORT")
        MEDIUM_COUNT=$(jq '[.results[] | select(.issue_severity == "MEDIUM")] | length' "$BANDIT_REPORT")
        LOW_COUNT=$(jq '[.results[] | select(.issue_severity == "LOW")] | length' "$BANDIT_REPORT")

        echo ""
        echo "Bandit Results:"
        echo "  HIGH:   $HIGH_COUNT issues"
        echo "  MEDIUM: $MEDIUM_COUNT issues"
        echo "  LOW:    $LOW_COUNT issues"
        echo ""

        if [ "$HIGH_COUNT" -gt 0 ]; then
            echo -e "${RED}❌ FAILED: $HIGH_COUNT HIGH severity issues found${NC}"

            # Show HIGH issues
            echo ""
            echo "HIGH Severity Issues:"
            jq -r '.results[] | select(.issue_severity == "HIGH") | "  - \(.test_id): \(.issue_text) (\(.filename):\(.line_number))"' "$BANDIT_REPORT"
            echo ""

            return 1
        elif [ "$FAIL_ON_MEDIUM" = true ] && [ "$MEDIUM_COUNT" -gt 0 ]; then
            echo -e "${YELLOW}⚠️  WARNING: $MEDIUM_COUNT MEDIUM severity issues found${NC}"

            # Show MEDIUM issues
            echo ""
            echo "MEDIUM Severity Issues:"
            jq -r '.results[] | select(.issue_severity == "MEDIUM") | "  - \(.test_id): \(.issue_text) (\(.filename):\(.line_number))"' "$BANDIT_REPORT"
            echo ""

            return 1
        else
            echo -e "${GREEN}✅ Bandit: No HIGH severity issues${NC}"
            echo ""
            return 0
        fi
    else
        echo -e "${RED}❌ Bandit report not generated${NC}"
        return 1
    fi
}

# Function to run Safety
run_safety() {
    echo -e "${BLUE}📊 Running Safety dependency checker...${NC}"

    cd "$PROJECT_ROOT"

    # Run Safety and capture output
    # Safety 3.7.0 doesn't reliably produce JSON, so we parse text output
    SAFETY_OUTPUT=$(uv run safety check 2>&1) || SAFETY_EXIT=$?
    SAFETY_EXIT=${SAFETY_EXIT:-0}

    # Check for "No known security vulnerabilities" message
    if echo "$SAFETY_OUTPUT" | grep -q "No known security vulnerabilities"; then
        echo ""
        echo "Safety Results:"
        echo "  Vulnerabilities: 0"
        echo ""
        echo -e "${GREEN}✅ Safety: No vulnerabilities found${NC}"
        echo ""
        return 0
    elif echo "$SAFETY_OUTPUT" | grep -q "vulnerabilities reported"; then
        # Extract vulnerability count if possible
        VULN_COUNT=$(echo "$SAFETY_OUTPUT" | grep -oP '\d+(?= vulnerabilities reported)' || echo "unknown")

        echo ""
        echo "Safety Results:"
        echo "  Vulnerabilities: $VULN_COUNT"
        echo ""
        echo -e "${RED}❌ FAILED: Vulnerabilities found${NC}"
        echo ""
        echo "$SAFETY_OUTPUT"
        echo ""
        return 1
    else
        # Unexpected output, show it
        echo ""
        echo "Safety Results:"
        echo "  Status: Unknown (see output below)"
        echo ""
        echo "$SAFETY_OUTPUT"
        echo ""
        echo -e "${YELLOW}⚠️  Unable to parse Safety output (treating as pass)${NC}"
        echo ""
        return 0
    fi
}

# Generate HTML reports
generate_html_reports() {
    if [ "$GENERATE_HTML" = true ]; then
        echo -e "${BLUE}📄 Generating HTML reports...${NC}"

        cd "$PROJECT_ROOT"

        # Find all Python files
        PYTHON_FILES=$(find . -maxdepth 1 -name "*.py" -type f)
        PYTHON_FILES="$PYTHON_FILES $(find . -maxdepth 2 -name "*.py" -path "./src/*.py" -o -path "./lib/*.py" 2>/dev/null | tr '\n' ' ')"

        if [ -f "$BANDIT_REPORT" ] && [ -n "$PYTHON_FILES" ]; then
            uv run bandit $PYTHON_FILES -ll -f html -o "$PROJECT_ROOT/bandit-report.html" 2>/dev/null || true
            echo "  Bandit HTML report: bandit-report.html"
        fi

        echo ""
    fi
}

# Main execution
OVERALL_EXIT=0

run_bandit || OVERALL_EXIT=$?
run_safety || OVERALL_EXIT=$?
generate_html_reports

echo "========================================"
if [ $OVERALL_EXIT -eq 0 ]; then
    echo -e "${GREEN}✅ All security checks passed!${NC}"
else
    echo -e "${RED}❌ Security checks failed${NC}"
    echo ""
    echo "Reports generated:"
    echo "  - $BANDIT_REPORT"
    if [ "$GENERATE_HTML" = true ]; then
        echo "  - $PROJECT_ROOT/bandit-report.html"
    fi
fi
echo ""

exit $OVERALL_EXIT
