#!/bin/bash

# LabArchives MCP Server Installation Script
# This script automates the installation of the LabArchives MCP Server CLI
# and its dependencies for local development or deployment.
#
# Supported platforms: Linux, macOS
# Requires: Python 3.11+ 
# Usage: Run from project root: bash src/cli/scripts/install.sh

set -e  # Exit on any error

# ================================================================================
# GLOBAL CONFIGURATION
# ================================================================================

# Minimum required Python version
PYTHON_MIN_VERSION="3.11"

# Virtual environment directory
VENV_DIR=".venv"

# Requirements files
REQUIREMENTS_FILE="src/cli/requirements.txt"
DEV_REQUIREMENTS_FILE="src/cli/requirements-dev.txt"

# CLI entry point command
ENTRY_POINT="labarchives-mcp"

# Script version and metadata
SCRIPT_VERSION="1.0.0"
SCRIPT_NAME="LabArchives MCP Server Installer"

# Colors for output formatting
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ================================================================================
# UTILITY FUNCTIONS
# ================================================================================

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
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

# Print section headers
print_section() {
    echo
    echo "========================================="
    echo "$1"
    echo "========================================="
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Get Python version as comparable format (e.g., "3.11.0" -> "3110")
get_python_version() {
    local python_cmd="$1"
    $python_cmd -c "import sys; print(f'{sys.version_info.major}{sys.version_info.minor:02d}')" 2>/dev/null || echo "0"
}

# ================================================================================
# CORE INSTALLATION FUNCTIONS
# ================================================================================

# Check if the installed Python version meets minimum requirements
check_python_version() {
    print_section "Checking Python Version"
    
    local python_cmd=""
    local python_version=""
    local min_version_numeric=""
    local current_version_numeric=""
    
    # Try different Python commands
    for cmd in python3 python python3.11 python3.12 python3.13; do
        if command_exists "$cmd"; then
            python_cmd="$cmd"
            break
        fi
    done
    
    if [ -z "$python_cmd" ]; then
        print_error "Python not found. Please install Python $PYTHON_MIN_VERSION or later."
        print_error "Visit https://www.python.org/downloads/ for installation instructions."
        return 1
    fi
    
    # Get version information
    python_version=$($python_cmd --version 2>&1 | cut -d' ' -f2)
    current_version_numeric=$(get_python_version "$python_cmd")
    min_version_numeric=$(echo "$PYTHON_MIN_VERSION" | sed 's/\.//' | sed 's/$/00/' | head -c 4)
    
    print_status "Found Python: $python_cmd (version $python_version)"
    
    # Compare versions
    if [ "$current_version_numeric" -lt "$min_version_numeric" ]; then
        print_error "Python version $python_version is too old."
        print_error "Required: Python $PYTHON_MIN_VERSION or later"
        print_error "Please upgrade Python and try again."
        return 1
    fi
    
    print_success "Python version $python_version meets requirements (>= $PYTHON_MIN_VERSION)"
    
    # Set global Python command for other functions
    export PYTHON_CMD="$python_cmd"
    return 0
}

# Create Python virtual environment
create_virtualenv() {
    print_section "Creating Virtual Environment"
    
    if [ -d "$VENV_DIR" ]; then
        print_warning "Virtual environment already exists at $VENV_DIR"
        print_status "Skipping virtual environment creation"
        return 0
    fi
    
    print_status "Creating virtual environment in $VENV_DIR..."
    
    if ! $PYTHON_CMD -m venv "$VENV_DIR"; then
        print_error "Failed to create virtual environment"
        print_error "Please ensure you have the 'venv' module installed:"
        print_error "  On Ubuntu/Debian: apt install python3-venv"
        print_error "  On CentOS/RHEL: yum install python3-venv"
        return 1
    fi
    
    print_success "Virtual environment created successfully"
    return 0
}

# Activate the virtual environment
activate_virtualenv() {
    print_section "Activating Virtual Environment"
    
    local activation_script=""
    
    # Determine activation script based on OS
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
        activation_script="$VENV_DIR/Scripts/activate"
    else
        activation_script="$VENV_DIR/bin/activate"
    fi
    
    if [ ! -f "$activation_script" ]; then
        print_error "Virtual environment activation script not found: $activation_script"
        print_error "Please ensure the virtual environment was created successfully"
        return 1
    fi
    
    print_status "Activating virtual environment..."
    
    # Source the activation script
    if ! source "$activation_script"; then
        print_error "Failed to activate virtual environment"
        return 1
    fi
    
    print_success "Virtual environment activated"
    print_status "Python executable: $(which python)"
    print_status "Python version: $(python --version)"
    
    return 0
}

# Install Python dependencies
install_dependencies() {
    print_section "Installing Dependencies"
    
    print_status "Upgrading pip to latest version..."
    if ! python -m pip install --upgrade pip; then
        print_error "Failed to upgrade pip"
        return 1
    fi
    
    # Install main requirements
    if [ -f "$REQUIREMENTS_FILE" ]; then
        print_status "Installing main dependencies from $REQUIREMENTS_FILE..."
        if ! pip install -r "$REQUIREMENTS_FILE"; then
            print_error "Failed to install main dependencies"
            print_error "Please check the requirements file: $REQUIREMENTS_FILE"
            return 1
        fi
        print_success "Main dependencies installed successfully"
    else
        print_warning "Requirements file not found: $REQUIREMENTS_FILE"
        print_status "Installing core dependencies directly..."
        
        # Install core MCP dependencies
        local core_deps=(
            "mcp>=1.0.0"
            "fastmcp>=1.0.0"
            "pydantic>=2.11.7"
            "pydantic-settings>=2.10.1"
            "requests>=2.31.0"
        )
        
        for dep in "${core_deps[@]}"; do
            print_status "Installing $dep..."
            if ! pip install "$dep"; then
                print_error "Failed to install $dep"
                return 1
            fi
        done
    fi
    
    # Install development dependencies if in development mode
    if [ -f "$DEV_REQUIREMENTS_FILE" ]; then
        print_status "Installing development dependencies from $DEV_REQUIREMENTS_FILE..."
        if ! pip install -r "$DEV_REQUIREMENTS_FILE"; then
            print_warning "Failed to install development dependencies (non-critical)"
            print_status "Development dependencies are optional for basic usage"
        else
            print_success "Development dependencies installed successfully"
        fi
    fi
    
    return 0
}

# Install CLI package in editable mode
install_cli_editable() {
    print_section "Installing CLI Package"
    
    local cli_package_dir="src/cli"
    local install_mode="editable"
    
    # Check if we're in development mode or production
    if [ "$1" == "--production" ]; then
        install_mode="production"
    fi
    
    if [ ! -d "$cli_package_dir" ]; then
        print_error "CLI package directory not found: $cli_package_dir"
        print_error "Please run this script from the project root directory"
        return 1
    fi
    
    # Install the package
    if [ "$install_mode" == "editable" ]; then
        print_status "Installing CLI package in editable mode..."
        if ! pip install -e "$cli_package_dir"; then
            print_error "Failed to install CLI package in editable mode"
            return 1
        fi
        print_success "CLI package installed in editable mode"
    else
        print_status "Installing CLI package in production mode..."
        if ! pip install "$cli_package_dir"; then
            print_error "Failed to install CLI package"
            return 1
        fi
        print_success "CLI package installed in production mode"
    fi
    
    # Verify installation
    print_status "Verifying CLI installation..."
    
    if ! command_exists "$ENTRY_POINT"; then
        print_error "CLI command '$ENTRY_POINT' not found in PATH"
        print_error "Installation may have failed or PATH is not updated"
        return 1
    fi
    
    # Test CLI help command
    if ! $ENTRY_POINT --help >/dev/null 2>&1; then
        print_error "CLI command '$ENTRY_POINT' is not working correctly"
        return 1
    fi
    
    print_success "CLI installation verified successfully"
    return 0
}

# Print installation success message and usage instructions
print_success_message() {
    print_section "Installation Complete"
    
    cat << EOF
${GREEN}🎉 LabArchives MCP Server CLI installed successfully!${NC}

${BLUE}Next Steps:${NC}
1. Activate the virtual environment (if not already active):
   ${YELLOW}source $VENV_DIR/bin/activate${NC}

2. Set up your LabArchives API credentials:
   ${YELLOW}export LABARCHIVES_AKID="your_access_key_id"${NC}
   ${YELLOW}export LABARCHIVES_SECRET="your_secret_token"${NC}
   ${YELLOW}export LABARCHIVES_USER="your_email@institution.edu"${NC}

3. Test the CLI installation:
   ${YELLOW}$ENTRY_POINT --help${NC}

4. Start the MCP server:
   ${YELLOW}$ENTRY_POINT --verbose${NC}

${BLUE}Configuration for Claude Desktop:${NC}
Add to ~/.config/claude/claude_desktop_config.json:
{
  "mcpServers": {
    "labarchives": {
      "command": "$ENTRY_POINT",
      "env": {
        "LABARCHIVES_AKID": "your_access_key_id",
        "LABARCHIVES_SECRET": "your_secret_token"
      }
    }
  }
}

${BLUE}Documentation:${NC}
- README.md - Getting started guide
- src/cli/README.md - CLI documentation
- src/cli/examples/ - Example configurations

${BLUE}Support:${NC}
If you encounter issues:
1. Check the troubleshooting guide in README.md
2. Verify your Python version: ${YELLOW}python --version${NC}
3. Check virtual environment: ${YELLOW}which python${NC}
4. Validate CLI installation: ${YELLOW}$ENTRY_POINT --version${NC}

${BLUE}Docker Alternative:${NC}
For containerized deployment, see:
- src/cli/examples/docker_deployment.sh
- Dockerfile in the project root

EOF
}

# ================================================================================
# SYSTEM DETECTION AND VALIDATION
# ================================================================================

# Detect operating system and architecture
detect_system() {
    print_section "System Detection"
    
    local os_name=$(uname -s)
    local arch=$(uname -m)
    
    case "$os_name" in
        Linux*)
            print_status "Operating System: Linux"
            if command_exists lsb_release; then
                local distro=$(lsb_release -d | cut -f2)
                print_status "Distribution: $distro"
            fi
            ;;
        Darwin*)
            print_status "Operating System: macOS"
            local macos_version=$(sw_vers -productVersion)
            print_status "macOS Version: $macos_version"
            ;;
        CYGWIN*|MINGW32*|MSYS*|MINGW64*)
            print_warning "Windows detected"
            print_warning "This script has limited Windows support"
            print_warning "Consider using WSL2 or Docker for best experience"
            ;;
        *)
            print_warning "Unknown operating system: $os_name"
            print_warning "Script may not work correctly"
            ;;
    esac
    
    print_status "Architecture: $arch"
    
    # Check for required system tools
    local required_tools=("curl" "git")
    for tool in "${required_tools[@]}"; do
        if command_exists "$tool"; then
            print_status "$tool: available"
        else
            print_warning "$tool: not found (optional but recommended)"
        fi
    done
    
    return 0
}

# Validate project structure
validate_project_structure() {
    print_section "Validating Project Structure"
    
    local required_files=(
        "src/cli/setup.py"
        "src/cli/pyproject.toml"
        "src/cli/requirements.txt"
    )
    
    local required_dirs=(
        "src/cli"
        "src/cli/scripts"
    )
    
    # Check required directories
    for dir in "${required_dirs[@]}"; do
        if [ -d "$dir" ]; then
            print_status "Directory found: $dir"
        else
            print_error "Required directory missing: $dir"
            return 1
        fi
    done
    
    # Check required files (some are optional)
    for file in "${required_files[@]}"; do
        if [ -f "$file" ]; then
            print_status "File found: $file"
        else
            print_warning "File not found: $file (may be optional)"
        fi
    done
    
    # Check if we're in the right directory
    if [ ! -f "src/cli/scripts/install.sh" ]; then
        print_error "Please run this script from the project root directory"
        print_error "Current directory: $(pwd)"
        return 1
    fi
    
    print_success "Project structure validation passed"
    return 0
}

# ================================================================================
# ERROR HANDLING AND CLEANUP
# ================================================================================

# Cleanup function for error handling
cleanup_on_error() {
    print_section "Cleaning Up After Error"
    
    # Deactivate virtual environment if active
    if [ -n "$VIRTUAL_ENV" ]; then
        print_status "Deactivating virtual environment..."
        deactivate 2>/dev/null || true
    fi
    
    # Optionally remove incomplete virtual environment
    if [ -d "$VENV_DIR" ] && [ "$1" == "--remove-venv" ]; then
        print_status "Removing incomplete virtual environment..."
        rm -rf "$VENV_DIR"
    fi
    
    print_error "Installation failed. Please check the error messages above."
    print_error "For help, refer to the troubleshooting guide in README.md"
    
    exit 1
}

# Set up error handling
trap 'cleanup_on_error' ERR

# ================================================================================
# MAIN INSTALLATION LOGIC
# ================================================================================

# Main installation function
main() {
    print_section "$SCRIPT_NAME v$SCRIPT_VERSION"
    
    # Parse command line arguments
    local production_mode=false
    local skip_deps=false
    local verbose=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --production)
                production_mode=true
                shift
                ;;
            --skip-deps)
                skip_deps=true
                shift
                ;;
            --verbose)
                verbose=true
                set -x  # Enable debug mode
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # Set installation mode
    local install_mode=""
    if [ "$production_mode" = true ]; then
        install_mode="--production"
    fi
    
    print_status "Starting installation process..."
    print_status "Installation mode: $([ "$production_mode" = true ] && echo "production" || echo "development")"
    
    # Execute installation steps
    detect_system
    validate_project_structure
    check_python_version
    create_virtualenv
    activate_virtualenv
    
    if [ "$skip_deps" = false ]; then
        install_dependencies
    else
        print_warning "Skipping dependency installation (--skip-deps)"
    fi
    
    install_cli_editable $install_mode
    
    # Final success message
    print_success_message
    
    # Security reminder
    print_section "Security Reminder"
    print_warning "Never commit credentials to version control"
    print_warning "Use environment variables for sensitive configuration"
    print_warning "Regularly rotate your LabArchives API keys"
    
    print_success "Installation completed successfully!"
    return 0
}

# Show help message
show_help() {
    cat << EOF
$SCRIPT_NAME v$SCRIPT_VERSION

USAGE:
    bash src/cli/scripts/install.sh [OPTIONS]

OPTIONS:
    --production    Install in production mode (non-editable)
    --skip-deps     Skip dependency installation
    --verbose       Enable verbose output
    --help, -h      Show this help message

DESCRIPTION:
    This script automates the installation of the LabArchives MCP Server CLI
    and its dependencies. It creates a Python virtual environment, installs
    required packages, and sets up the CLI entry point.

REQUIREMENTS:
    - Python 3.11 or later
    - pip package manager
    - Unix-like system (Linux, macOS)

EXAMPLES:
    # Standard installation
    bash src/cli/scripts/install.sh

    # Production installation with verbose output
    bash src/cli/scripts/install.sh --production --verbose

    # Skip dependency installation (for development)
    bash src/cli/scripts/install.sh --skip-deps

ENVIRONMENT VARIABLES:
    LABARCHIVES_AKID      - API Access Key ID
    LABARCHIVES_SECRET    - API Secret/Token
    LABARCHIVES_USER      - Username for token authentication

For more information, see README.md and src/cli/README.md
EOF
}

# ================================================================================
# SCRIPT EXECUTION
# ================================================================================

# Ensure script is run from correct directory
if [ ! -f "src/cli/scripts/install.sh" ]; then
    print_error "Please run this script from the project root directory"
    print_error "Expected: bash src/cli/scripts/install.sh"
    print_error "Current directory: $(pwd)"
    exit 1
fi

# Check if running as root (security measure)
if [ "$EUID" -eq 0 ]; then
    print_error "Do not run this script as root"
    print_error "It should be run as a regular user"
    exit 1
fi

# Run main installation
main "$@"