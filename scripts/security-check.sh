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
SAFETY_REPORT="$PROJECT_ROOT/safety-report.json"

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
        --html)
            GENERATE_HTML=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -v, --verbose        Verbose output"
            echo "  --no-fail-medium     Don't fail on MEDIUM severity issues"
            echo "  --html               Generate HTML reports"
            echo "  -h, --help           Show this help message"
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

    # Run Bandit
    if [ "$VERBOSE" = true ]; then
        uv run bandit -r . -ll -f json -o "$BANDIT_REPORT" -v || BANDIT_EXIT=$?
    else
        uv run bandit -r . -ll -f json -o "$BANDIT_REPORT" || BANDIT_EXIT=$?
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

    # Run Safety
    uv run safety check --json -o "$SAFETY_REPORT" || SAFETY_EXIT=$?
    SAFETY_EXIT=${SAFETY_EXIT:-0}

    # Parse results
    if [ -f "$SAFETY_REPORT" ]; then
        VULN_COUNT=$(jq '[.vulnerabilities // []] | length' "$SAFETY_REPORT" 2>/dev/null || echo "0")

        echo ""
        echo "Safety Results:"
        echo "  Vulnerabilities: $VULN_COUNT"
        echo ""

        if [ "$VULN_COUNT" -gt 0 ]; then
            echo -e "${RED}❌ FAILED: $VULN_COUNT vulnerabilities found${NC}"

            # Show vulnerabilities
            echo ""
            echo "Vulnerabilities:"
            jq -r '.vulnerabilities[] | "  - \(.package_name) \(.vulnerable_version): \(.vulnerability_id) - \(.advisory)"' "$SAFETY_REPORT" 2>/dev/null || echo "  (See $SAFETY_REPORT for details)"
            echo ""

            return 1
        else
            echo -e "${GREEN}✅ Safety: No vulnerabilities found${NC}"
            echo ""
            return 0
        fi
    else
        echo -e "${YELLOW}⚠️  Safety report not generated (may not be a critical error)${NC}"
        echo ""
        return 0
    fi
}

# Generate HTML reports
generate_html_reports() {
    if [ "$GENERATE_HTML" = true ]; then
        echo -e "${BLUE}📄 Generating HTML reports...${NC}"

        if [ -f "$BANDIT_REPORT" ]; then
            uv run bandit -r . -ll -f html -o "$PROJECT_ROOT/bandit-report.html" || true
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
    echo "  - $SAFETY_REPORT"
fi
echo ""

exit $OVERALL_EXIT
