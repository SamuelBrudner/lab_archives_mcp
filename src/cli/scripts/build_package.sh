#!/bin/bash

# LabArchives MCP Server Build Script
# Automates building the LabArchives MCP Server Python package for distribution
# Handles cleaning, testing, formatting, type checking, and packaging for PyPI and Docker

# Exit on any error
set -e

# Configuration variables
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC_DIR="$PROJECT_ROOT/src/cli"
DIST_DIR="$SRC_DIR/dist"
BUILD_DIR="$SRC_DIR/build"
EGG_INFO_DIR="$SRC_DIR/src/labarchives_mcp.egg-info"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to get Python version
get_python_version() {
    python3 --version 2>/dev/null | cut -d' ' -f2 | cut -d'.' -f1,2
}

# Function to clean previous build artifacts
clean_build_artifacts() {
    log_info "Cleaning previous build artifacts..."
    
    # Remove distribution directory
    if [ -d "$DIST_DIR" ]; then
        rm -rf "$DIST_DIR"
        log_info "Removed $DIST_DIR"
    fi
    
    # Remove build directory
    if [ -d "$BUILD_DIR" ]; then
        rm -rf "$BUILD_DIR"
        log_info "Removed $BUILD_DIR"
    fi
    
    # Remove egg-info directory
    if [ -d "$EGG_INFO_DIR" ]; then
        rm -rf "$EGG_INFO_DIR"
        log_info "Removed $EGG_INFO_DIR"
    fi
    
    # Remove __pycache__ directories
    find "$PROJECT_ROOT" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    
    # Remove .pyc files
    find "$PROJECT_ROOT" -name "*.pyc" -delete 2>/dev/null || true
    
    log_success "Build artifacts cleaned successfully"
}

# Function to validate Python version
validate_python_version() {
    log_info "Validating Python version..."
    
    if ! command_exists python3; then
        log_error "Python 3 is not installed or not in PATH"
        exit 1
    fi
    
    local python_version=$(get_python_version)
    local major=$(echo "$python_version" | cut -d'.' -f1)
    local minor=$(echo "$python_version" | cut -d'.' -f2)
    
    if [ "$major" -lt 3 ] || ([ "$major" -eq 3 ] && [ "$minor" -lt 11 ]); then
        log_error "Python 3.11+ is required, but found Python $python_version"
        log_error "Please install Python 3.11 or later"
        exit 1
    fi
    
    log_success "Python $python_version detected - compatible with requirements"
}

# Function to install or upgrade dependencies
install_dependencies() {
    log_info "Installing and upgrading build dependencies..."
    
    # Upgrade pip to latest version
    log_info "Upgrading pip..."
    python3 -m pip install --upgrade pip
    
    # Install core build dependencies
    log_info "Installing build dependencies..."
    python3 -m pip install --upgrade setuptools wheel build
    
    # Install development dependencies for testing and quality assurance
    log_info "Installing development dependencies..."
    python3 -m pip install --upgrade \
        pytest>=7.0.0 \
        black>=23.0.0 \
        mypy>=1.0.0 \
        pytest-cov \
        pytest-asyncio \
        responses
    
    # Install project dependencies
    if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
        log_info "Installing project dependencies from requirements.txt..."
        python3 -m pip install -r "$PROJECT_ROOT/requirements.txt"
    fi
    
    # Install development dependencies if they exist
    if [ -f "$PROJECT_ROOT/requirements-dev.txt" ]; then
        log_info "Installing development dependencies from requirements-dev.txt..."
        python3 -m pip install -r "$PROJECT_ROOT/requirements-dev.txt"
    fi
    
    log_success "All dependencies installed successfully"
}

# Function to run code formatting check
run_code_formatting() {
    log_info "Running code formatting check with black..."
    
    # Check if black is installed
    if ! command_exists black; then
        log_error "black is not installed. Please install it with: pip install black>=23.0.0"
        exit 1
    fi
    
    # Run black check on source directory
    if black --check --diff "$SRC_DIR" 2>/dev/null; then
        log_success "Code formatting check passed"
    else
        log_error "Code formatting check failed"
        log_error "Please run: black $SRC_DIR"
        log_error "Or fix formatting issues manually"
        exit 1
    fi
    
    # Also check tests directory if it exists
    if [ -d "$PROJECT_ROOT/tests" ]; then
        if black --check --diff "$PROJECT_ROOT/tests" 2>/dev/null; then
            log_success "Test code formatting check passed"
        else
            log_error "Test code formatting check failed"
            log_error "Please run: black $PROJECT_ROOT/tests"
            exit 1
        fi
    fi
}

# Function to run static type checking
run_type_checking() {
    log_info "Running static type checking with mypy..."
    
    # Check if mypy is installed
    if ! command_exists mypy; then
        log_error "mypy is not installed. Please install it with: pip install mypy>=1.0.0"
        exit 1
    fi
    
    # Run mypy on source directory
    if mypy "$SRC_DIR" --ignore-missing-imports --python-version 3.11; then
        log_success "Static type checking passed"
    else
        log_error "Static type checking failed"
        log_error "Please fix type errors before proceeding"
        exit 1
    fi
}

# Function to run test suite
run_tests() {
    log_info "Running test suite with pytest..."
    
    # Check if pytest is installed
    if ! command_exists pytest; then
        log_error "pytest is not installed. Please install it with: pip install pytest>=7.0.0"
        exit 1
    fi
    
    # Change to project root for test execution
    cd "$PROJECT_ROOT"
    
    # Run tests with coverage if tests directory exists
    if [ -d "$PROJECT_ROOT/tests" ]; then
        if pytest tests/ -v --cov="$SRC_DIR" --cov-report=term-missing --cov-report=html; then
            log_success "All tests passed"
        else
            log_error "Test execution failed"
            log_error "Please fix failing tests before proceeding"
            exit 1
        fi
    else
        log_warning "No tests directory found, skipping test execution"
    fi
}

# Function to build the package
build_package() {
    log_info "Building Python package..."
    
    # Change to source directory
    cd "$SRC_DIR"
    
    # Check if build module is available
    if ! python3 -c "import build" 2>/dev/null; then
        log_error "build module is not available. Please install it with: pip install build"
        exit 1
    fi
    
    # Build the package (creates both sdist and wheel)
    if python3 -m build; then
        log_success "Package built successfully"
        
        # List the built artifacts
        if [ -d "$DIST_DIR" ]; then
            log_info "Built artifacts:"
            ls -la "$DIST_DIR"
        fi
    else
        log_error "Package build failed"
        exit 1
    fi
}

# Function to validate built package
validate_package() {
    log_info "Validating built package..."
    
    if [ ! -d "$DIST_DIR" ]; then
        log_error "Distribution directory not found"
        exit 1
    fi
    
    # Check for wheel file
    if ls "$DIST_DIR"/*.whl 1> /dev/null 2>&1; then
        log_success "Wheel package found"
    else
        log_error "Wheel package not found"
        exit 1
    fi
    
    # Check for source distribution
    if ls "$DIST_DIR"/*.tar.gz 1> /dev/null 2>&1; then
        log_success "Source distribution found"
    else
        log_error "Source distribution not found"
        exit 1
    fi
    
    # Install and test the wheel package in a temporary environment
    log_info "Testing wheel package installation..."
    
    # Create a temporary directory for testing
    local temp_dir=$(mktemp -d)
    cd "$temp_dir"
    
    # Install the wheel package
    if python3 -m pip install "$DIST_DIR"/*.whl --quiet; then
        log_success "Wheel package installs successfully"
        
        # Test basic import
        if python3 -c "import labarchives_mcp" 2>/dev/null; then
            log_success "Package imports successfully"
        else
            log_warning "Package installation succeeded but import failed"
        fi
    else
        log_error "Wheel package installation failed"
        exit 1
    fi
    
    # Clean up
    cd "$PROJECT_ROOT"
    rm -rf "$temp_dir"
}

# Function to display deployment instructions
display_deployment_instructions() {
    log_info "=== DEPLOYMENT INSTRUCTIONS ==="
    echo ""
    echo "📦 Package built successfully!"
    echo "📍 Artifacts location: $DIST_DIR"
    echo ""
    echo "🚀 To upload to PyPI:"
    echo "   1. Install twine: pip install twine"
    echo "   2. Upload to TestPyPI: twine upload --repository testpypi dist/*"
    echo "   3. Upload to PyPI: twine upload dist/*"
    echo ""
    echo "🐳 To build Docker image:"
    echo "   1. Ensure Dockerfile exists in project root"
    echo "   2. Build: docker build -t labarchives-mcp:latest ."
    echo "   3. Run: docker run -it labarchives-mcp:latest"
    echo ""
    echo "📋 To install locally:"
    echo "   pip install $DIST_DIR/*.whl"
    echo ""
    echo "✅ Build completed successfully!"
}

# Main function to orchestrate the build process
main() {
    log_info "Starting LabArchives MCP Server build process..."
    log_info "Project root: $PROJECT_ROOT"
    log_info "Source directory: $SRC_DIR"
    log_info "Distribution directory: $DIST_DIR"
    echo ""
    
    # Change to project root
    cd "$PROJECT_ROOT"
    
    # Execute build steps
    validate_python_version
    clean_build_artifacts
    install_dependencies
    run_code_formatting
    run_type_checking
    run_tests
    build_package
    validate_package
    
    # Display deployment instructions
    display_deployment_instructions
    
    log_success "Build process completed successfully!"
    exit 0
}

# Handle script interruption
trap 'log_error "Build process interrupted"; exit 1' INT TERM

# Execute main function
main "$@"