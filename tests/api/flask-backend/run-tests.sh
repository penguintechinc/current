#!/bin/bash
# Flask Backend API Test Runner
# Runs build, unit tests, API tests, and optionally load tests
#
# Usage:
#   ./run-tests.sh              # Run all tests (build, unit, api)
#   ./run-tests.sh --unit       # Run only unit tests
#   ./run-tests.sh --api        # Run only API tests
#   ./run-tests.sh --load       # Run load tests (requires running server)
#   ./run-tests.sh --all        # Run everything including load tests

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
SERVICE_DIR="$PROJECT_ROOT/services/flask-backend"
VENV_DIR="$SERVICE_DIR/.venv"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Test results tracking
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[PASS]${NC} $1"; ((TESTS_PASSED++)); }
log_fail() { echo -e "${RED}[FAIL]${NC} $1"; ((TESTS_FAILED++)); }
log_skip() { echo -e "${YELLOW}[SKIP]${NC} $1"; ((TESTS_SKIPPED++)); }
log_header() { echo -e "\n${BLUE}=== $1 ===${NC}"; }

# Check if virtual environment exists and activate
activate_venv() {
    if [ -d "$VENV_DIR" ]; then
        source "$VENV_DIR/bin/activate"
        return 0
    else
        log_info "Creating virtual environment..."
        python3 -m venv "$VENV_DIR"
        source "$VENV_DIR/bin/activate"
        pip install --upgrade pip -q
        pip install -r "$SERVICE_DIR/requirements.txt" -q
        return 0
    fi
}

# Build check - verify the app can be imported
run_build_check() {
    log_header "Build Check"

    cd "$SERVICE_DIR"
    activate_venv

    # Set testing environment
    export FLASK_ENV=testing
    export DB_TYPE=sqlite
    export DB_NAME=:memory:

    log_info "Checking Python syntax..."
    if python3 -m py_compile app/__init__.py app/auth.py app/models.py app/config.py 2>&1; then
        log_success "Python syntax check passed"
    else
        log_fail "Python syntax check failed"
        return 1
    fi

    log_info "Checking imports..."
    if python3 -c "from app import create_app; from app.config import TestingConfig; app = create_app(TestingConfig)" 2>&1; then
        log_success "Application imports successfully"
    else
        log_fail "Application import failed"
        return 1
    fi
}

# Run pytest unit tests
run_unit_tests() {
    log_header "Unit Tests (pytest)"

    cd "$SERVICE_DIR"
    activate_venv

    if [ -d "$SERVICE_DIR/tests" ]; then
        log_info "Running pytest..."
        if pytest tests/ -v --tb=short 2>&1; then
            log_success "Unit tests passed"
        else
            log_fail "Unit tests failed"
            return 1
        fi
    else
        log_skip "No tests directory found"
    fi
}

# Run API endpoint tests (requires server or uses test client)
run_api_tests() {
    log_header "API Endpoint Tests"

    cd "$SERVICE_DIR"
    activate_venv

    # Set testing environment
    export FLASK_ENV=testing
    export DB_TYPE=sqlite
    export DB_NAME=:memory:

    # Run API tests using the test scripts in this directory
    if [ -f "$SCRIPT_DIR/test_endpoints.py" ]; then
        log_info "Running API endpoint tests..."
        if python3 "$SCRIPT_DIR/test_endpoints.py" 2>&1; then
            log_success "API endpoint tests passed"
        else
            log_fail "API endpoint tests failed"
            return 1
        fi
    else
        log_skip "No API endpoint tests found"
    fi
}

# Run load/performance tests
run_load_tests() {
    log_header "Load Tests"

    cd "$SERVICE_DIR"
    activate_venv

    if [ -f "$SCRIPT_DIR/test_load.py" ]; then
        log_info "Running load tests..."
        if python3 "$SCRIPT_DIR/test_load.py" 2>&1; then
            log_success "Load tests passed"
        else
            log_fail "Load tests failed"
            return 1
        fi
    else
        log_skip "No load tests found"
    fi
}

# Print summary
print_summary() {
    log_header "Test Summary"
    echo -e "Passed:  ${GREEN}${TESTS_PASSED}${NC}"
    echo -e "Failed:  ${RED}${TESTS_FAILED}${NC}"
    echo -e "Skipped: ${YELLOW}${TESTS_SKIPPED}${NC}"
    echo ""

    if [ "$TESTS_FAILED" -eq 0 ]; then
        echo -e "${GREEN}All tests passed!${NC}"
        return 0
    else
        echo -e "${RED}Some tests failed!${NC}"
        return 1
    fi
}

# Main execution
main() {
    local run_build=true
    local run_unit=true
    local run_api=true
    local run_load=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --unit)
                run_build=false
                run_unit=true
                run_api=false
                run_load=false
                shift
                ;;
            --api)
                run_build=false
                run_unit=false
                run_api=true
                run_load=false
                shift
                ;;
            --load)
                run_build=false
                run_unit=false
                run_api=false
                run_load=true
                shift
                ;;
            --all)
                run_build=true
                run_unit=true
                run_api=true
                run_load=true
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --unit    Run only unit tests"
                echo "  --api     Run only API tests"
                echo "  --load    Run only load tests"
                echo "  --all     Run all tests including load tests"
                echo "  --help    Show this help message"
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                exit 1
                ;;
        esac
    done

    echo "=============================================="
    echo "Flask Backend Test Runner"
    echo "=============================================="
    echo "Service: $SERVICE_DIR"
    echo "=============================================="

    # Run selected tests
    if [ "$run_build" = true ]; then
        run_build_check || true
    fi

    if [ "$run_unit" = true ]; then
        run_unit_tests || true
    fi

    if [ "$run_api" = true ]; then
        run_api_tests || true
    fi

    if [ "$run_load" = true ]; then
        run_load_tests || true
    fi

    print_summary
}

main "$@"
