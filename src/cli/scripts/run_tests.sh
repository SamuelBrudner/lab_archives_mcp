#!/usr/bin/env bash

# LabArchives MCP Server Test Runner Script
# Automates execution of all test suites including unit, integration, and coverage tests
# Provides consistent, reproducible, and developer-friendly workflow for code validation

set -e  # Exit on any error

# =============================================================================
# GLOBAL CONFIGURATION
# =============================================================================

# Test directory relative to script location
TEST_DIR="$(dirname "$0")/../tests"

# Coverage report output file
COVERAGE_REPORT="coverage.xml"

# Colors for output formatting
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

# Print colored status messages
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Print section headers
print_section() {
    echo ""
    echo -e "${BLUE}=====================================${NC}"
    echo -e "${BLUE} $1${NC}"
    echo -e "${BLUE}=====================================${NC}"
}

# =============================================================================
# MAIN FUNCTION
# =============================================================================

main() {
    local exit_code=0
    local start_time=$(date +%s)
    
    print_section "LabArchives MCP Server Test Suite"
    print_status "Starting comprehensive test execution..."
    
    # Step 1: Determine root directory and setup environment
    setup_environment
    
    # Step 2: Activate virtual environment if present
    activate_virtual_environment
    
    # Step 3: Validate dependencies
    validate_dependencies
    
    # Step 4: Run static type checking with mypy
    print_section "Static Type Checking"
    if ! run_mypy_checks; then
        print_error "Type checking failed"
        exit_code=1
    fi
    
    # Step 5: Run pytest with coverage
    print_section "Unit and Integration Tests"
    if ! run_pytest_with_coverage; then
        print_error "Test execution failed"
        exit_code=1
    fi
    
    # Step 6: Run code formatting check (optional)
    print_section "Code Formatting Check"
    if ! run_black_check; then
        print_warning "Code formatting check failed (non-blocking)"
        # Note: Black formatting is optional and non-blocking
    fi
    
    # Step 7: Generate test summary
    print_section "Test Results Summary"
    generate_test_summary $exit_code
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    if [ $exit_code -eq 0 ]; then
        print_success "All tests completed successfully in ${duration} seconds!"
        print_status "Coverage report generated: ${COVERAGE_REPORT}"
    else
        print_error "Test suite failed with exit code ${exit_code}"
        print_status "Please review the output above for details"
    fi
    
    return $exit_code
}

# =============================================================================
# ENVIRONMENT SETUP
# =============================================================================

setup_environment() {
    print_status "Setting up test environment..."
    
    # Determine the root directory of the CLI package
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local cli_root="$(cd "${script_dir}/.." && pwd)"
    
    # Export environment variables for test execution
    export CLI_ROOT="${cli_root}"
    export TEST_DIR="${script_dir}/../tests"
    export PYTHONPATH="${cli_root}:${PYTHONPATH:-}"
    
    print_status "CLI root directory: ${CLI_ROOT}"
    print_status "Test directory: ${TEST_DIR}"
    
    # Verify test directory exists
    if [ ! -d "${TEST_DIR}" ]; then
        print_error "Test directory not found: ${TEST_DIR}"
        exit 1
    fi
    
    # Create coverage report directory if it doesn't exist
    mkdir -p "$(dirname "${COVERAGE_REPORT}")"
}

activate_virtual_environment() {
    print_status "Checking for Python virtual environment..."
    
    # Check for common virtual environment locations
    local venv_paths=(
        "${CLI_ROOT}/venv"
        "${CLI_ROOT}/.venv"
        "${CLI_ROOT}/env"
        "${CLI_ROOT}/.env"
        "${VIRTUAL_ENV}"
    )
    
    for venv_path in "${venv_paths[@]}"; do
        if [ -n "${venv_path}" ] && [ -f "${venv_path}/bin/activate" ]; then
            print_status "Activating virtual environment: ${venv_path}"
            source "${venv_path}/bin/activate"
            return 0
        fi
    done
    
    # Check if we're already in a virtual environment
    if [ -n "${VIRTUAL_ENV}" ]; then
        print_status "Already in virtual environment: ${VIRTUAL_ENV}"
        return 0
    fi
    
    print_warning "No virtual environment found. Using system Python."
    print_status "Consider creating a virtual environment for better dependency isolation."
}

# =============================================================================
# DEPENDENCY VALIDATION
# =============================================================================

validate_dependencies() {
    print_status "Validating test dependencies..."
    
    local required_packages=(
        "pytest>=7.0.0"
        "pytest-cov"
        "mypy>=1.0.0"
        "black>=23.0.0"
    )
    
    for package in "${required_packages[@]}"; do
        local package_name=$(echo "$package" | cut -d'>' -f1 | cut -d'=' -f1)
        # Handle package names that differ between pip and import
        local import_name="$package_name"
        case "$package_name" in
            "pytest-cov")
                import_name="pytest_cov"
                ;;
        esac
        
        if ! python -c "import ${import_name}" 2>/dev/null; then
            print_error "Required package not found: ${package}"
            print_status "Please install with: pip install ${package}"
            exit 1
        fi
    done
    
    print_success "All required dependencies are available"
}

# =============================================================================
# TEST EXECUTION FUNCTIONS
# =============================================================================

run_mypy_checks() {
    print_status "Running mypy static type checking on src/cli/..."
    
    local mypy_args=(
        "--config-file=${CLI_ROOT}/mypy.ini"
        "--show-error-codes"
        "--show-error-context"
        "--pretty"
        "${CLI_ROOT}/src/cli/"
    )
    
    # Check if mypy config exists, create basic one if not
    if [ ! -f "${CLI_ROOT}/mypy.ini" ]; then
        print_status "Creating basic mypy configuration..."
        cat > "${CLI_ROOT}/mypy.ini" << EOF
[mypy]
python_version = 3.11
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = True
disallow_incomplete_defs = True
check_untyped_defs = True
disallow_untyped_decorators = True
no_implicit_optional = True
warn_redundant_casts = True
warn_unused_ignores = True
warn_no_return = True
warn_unreachable = True
strict_equality = True
EOF
    fi
    
    if mypy "${mypy_args[@]}"; then
        print_success "Type checking passed"
        return 0
    else
        print_error "Type checking failed"
        return 1
    fi
}

run_pytest_with_coverage() {
    print_status "Running pytest with coverage on src/cli/tests/..."
    
    local pytest_args=(
        "${TEST_DIR}"
        "--verbose"
        "--tb=short"
        "--cov=${CLI_ROOT}/src/cli"
        "--cov-report=xml:${COVERAGE_REPORT}"
        "--cov-report=term-missing"
        "--cov-report=html:htmlcov"
        "--cov-branch"
        "--cov-fail-under=80"
        "--junit-xml=test-results.xml"
    )
    
    # Add parallel execution if pytest-xdist is available
    if python -c "import xdist" 2>/dev/null; then
        pytest_args+=("--numprocesses=auto")
        print_status "Using parallel test execution"
    fi
    
    # Run pytest with coverage
    if pytest "${pytest_args[@]}"; then
        print_success "All tests passed with adequate coverage"
        return 0
    else
        print_error "Tests failed or coverage below threshold"
        return 1
    fi
}

run_black_check() {
    print_status "Running black code formatting check..."
    
    local black_args=(
        "--check"
        "--diff"
        "--color"
        "--line-length=88"
        "${CLI_ROOT}/src/cli/"
        "${TEST_DIR}"
    )
    
    if black "${black_args[@]}"; then
        print_success "Code formatting check passed"
        return 0
    else
        print_warning "Code formatting issues found"
        print_status "Run 'black src/cli/ ${TEST_DIR}' to fix formatting"
        return 1
    fi
}

# =============================================================================
# REPORTING AND SUMMARY
# =============================================================================

generate_test_summary() {
    local exit_code=$1
    
    print_status "Generating test execution summary..."
    
    # Coverage summary
    if [ -f "${COVERAGE_REPORT}" ]; then
        print_status "Coverage report: ${COVERAGE_REPORT}"
        
        # Extract coverage percentage if available
        if command -v coverage >/dev/null 2>&1; then
            local coverage_percent=$(coverage report --show-missing | grep "TOTAL" | awk '{print $4}')
            if [ -n "$coverage_percent" ]; then
                print_status "Total coverage: ${coverage_percent}"
            fi
        fi
    fi
    
    # HTML coverage report
    if [ -d "htmlcov" ]; then
        print_status "HTML coverage report: htmlcov/index.html"
    fi
    
    # JUnit XML report
    if [ -f "test-results.xml" ]; then
        print_status "JUnit XML report: test-results.xml"
    fi
    
    # Test execution summary
    echo ""
    echo -e "${BLUE}Test Execution Summary:${NC}"
    echo "=========================="
    
    if [ $exit_code -eq 0 ]; then
        echo -e "✅ Type checking: ${GREEN}PASSED${NC}"
        echo -e "✅ Unit tests: ${GREEN}PASSED${NC}"
        echo -e "✅ Integration tests: ${GREEN}PASSED${NC}"
        echo -e "✅ Coverage requirements: ${GREEN}MET${NC}"
        echo -e "⚠️  Code formatting: ${YELLOW}CHECKED${NC}"
    else
        echo -e "❌ Overall result: ${RED}FAILED${NC}"
        echo -e "   Please review the output above for specific failure details"
    fi
    
    echo ""
    echo -e "${BLUE}Generated Reports:${NC}"
    echo "=================="
    echo "• Coverage XML: ${COVERAGE_REPORT}"
    echo "• Coverage HTML: htmlcov/index.html"
    echo "• Test Results: test-results.xml"
    echo ""
    
    # CI/CD integration hints
    if [ -n "${CI}" ]; then
        echo -e "${BLUE}CI/CD Integration:${NC}"
        echo "=================="
        echo "• Upload ${COVERAGE_REPORT} to your coverage service"
        echo "• Upload test-results.xml for test reporting"
        echo "• Use exit code ${exit_code} for pipeline status"
    fi
}

# =============================================================================
# SIGNAL HANDLING
# =============================================================================

cleanup() {
    print_status "Cleaning up test environment..."
    
    # Remove temporary files if they exist
    [ -f "test-results.xml" ] && rm -f "test-results.xml"
    
    # Deactivate virtual environment if it was activated by this script
    if [ -n "${VIRTUAL_ENV}" ]; then
        deactivate 2>/dev/null || true
    fi
}

# Set up signal handlers for cleanup
trap cleanup EXIT
trap 'print_error "Test execution interrupted"; exit 130' INT TERM

# =============================================================================
# SCRIPT EXECUTION
# =============================================================================

# Only execute main function if script is run directly (not sourced)
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    main "$@"
    exit $?
fi