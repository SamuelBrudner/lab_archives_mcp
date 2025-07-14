#!/bin/bash

# LabArchives MCP Server Docker Build Script
# This script automates the process of building the Docker image for the LabArchives MCP Server CLI.
# It ensures that the Docker build process is reproducible, uses the correct dependencies, 
# and produces a container image ready for deployment or local testing.

# Exit on any error to ensure build failures are caught early
set -e

# Enable pipefail to catch errors in pipeline commands
set -o pipefail

# Default configuration values (can be overridden by environment variables)
IMAGE_NAME="${IMAGE_NAME:-labarchives-mcp}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
DOCKERFILE_PATH="${DOCKERFILE_PATH:-src/cli/Dockerfile}"
CONTEXT_PATH="${CONTEXT_PATH:-src/cli}"

# Build configuration
BUILD_ARGS=""
VERBOSE=false
HELP=false
NO_CACHE=false
QUIET=false

# Color codes for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_colored() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to print usage instructions
print_usage() {
    cat << EOF
LabArchives MCP Server Docker Build Script

DESCRIPTION:
    Automates the Docker build process for the LabArchives MCP Server CLI.
    Ensures reproducible builds with proper dependency management and security.

USAGE:
    bash $(basename "$0") [OPTIONS]

OPTIONS:
    -h, --help              Show this help message and exit
    -n, --image-name NAME   Set custom Docker image name (default: labarchives-mcp)
    -t, --tag TAG           Set custom Docker image tag (default: latest)
    -d, --dockerfile PATH   Path to Dockerfile (default: src/cli/Dockerfile)
    -c, --context PATH      Build context path (default: src/cli)
    -v, --verbose           Enable verbose output during build
    -q, --quiet             Suppress non-error output
    --no-cache              Build without using Docker cache
    --build-arg ARG=VALUE   Pass build arguments to Docker build

ENVIRONMENT VARIABLES:
    IMAGE_NAME              Override default image name
    IMAGE_TAG               Override default image tag
    DOCKERFILE_PATH         Override default Dockerfile path
    CONTEXT_PATH            Override default build context path

EXAMPLES:
    # Basic build with defaults
    bash $(basename "$0")

    # Build with custom image name and tag
    bash $(basename "$0") --image-name my-mcp-server --tag v1.0.0

    # Build with environment variables
    IMAGE_NAME=labarchives-mcp IMAGE_TAG=0.1.0 bash $(basename "$0")

    # Build with no cache for clean rebuild
    bash $(basename "$0") --no-cache

    # Build with verbose output
    bash $(basename "$0") --verbose

    # Build with build arguments
    bash $(basename "$0") --build-arg VERSION=1.0.0 --build-arg ENV=production

SECURITY:
    - No credentials or secrets are included in the image
    - All sensitive data must be provided at runtime via environment variables
    - Uses official Python 3.11 slim base image with security updates
    - Container runs as non-root user for enhanced security

REQUIREMENTS:
    - Docker CLI (version 20.10 or higher)
    - Access to src/cli/Dockerfile and src/cli/requirements.txt
    - Sufficient disk space for image build

EOF
}

# Function to check if Docker is installed and available
check_docker_installed() {
    if ! command -v docker &> /dev/null; then
        print_colored "$RED" "ERROR: Docker CLI is not installed or not found in PATH."
        print_colored "$YELLOW" "Please install Docker Desktop or Docker Engine to continue."
        print_colored "$BLUE" "Visit https://docs.docker.com/get-docker/ for installation instructions."
        exit 1
    fi

    # Check Docker daemon is running
    if ! docker info &> /dev/null; then
        print_colored "$RED" "ERROR: Docker daemon is not running."
        print_colored "$YELLOW" "Please start Docker Desktop or Docker daemon to continue."
        exit 1
    fi

    # Check Docker version
    local docker_version
    docker_version=$(docker version --format '{{.Server.Version}}' 2>/dev/null || echo "unknown")
    
    if [[ "$VERBOSE" == true ]]; then
        print_colored "$GREEN" "Docker CLI found: $(docker --version)"
        print_colored "$GREEN" "Docker daemon version: $docker_version"
    fi

    # Check minimum Docker version (20.10)
    if [[ "$docker_version" != "unknown" ]]; then
        local major_version
        major_version=$(echo "$docker_version" | cut -d'.' -f1)
        local minor_version
        minor_version=$(echo "$docker_version" | cut -d'.' -f2)
        
        if [[ "$major_version" -lt 20 ]] || [[ "$major_version" -eq 20 && "$minor_version" -lt 10 ]]; then
            print_colored "$YELLOW" "WARNING: Docker version $docker_version is below recommended minimum 20.10"
            print_colored "$YELLOW" "Build may work but consider upgrading for optimal compatibility"
        fi
    fi

    return 0
}

# Function to validate build prerequisites
validate_build_prerequisites() {
    local errors=0

    # Check if Dockerfile exists
    if [[ ! -f "$DOCKERFILE_PATH" ]]; then
        print_colored "$RED" "ERROR: Dockerfile not found at: $DOCKERFILE_PATH"
        errors=$((errors + 1))
    fi

    # Check if context directory exists
    if [[ ! -d "$CONTEXT_PATH" ]]; then
        print_colored "$RED" "ERROR: Build context directory not found at: $CONTEXT_PATH"
        errors=$((errors + 1))
    fi

    # Check if requirements.txt exists in context
    if [[ ! -f "$CONTEXT_PATH/requirements.txt" ]]; then
        print_colored "$RED" "ERROR: requirements.txt not found at: $CONTEXT_PATH/requirements.txt"
        errors=$((errors + 1))
    fi

    # Check available disk space (minimum 2GB recommended)
    local available_space
    available_space=$(df -BG "$CONTEXT_PATH" | tail -1 | awk '{print $4}' | sed 's/G//')
    if [[ "$available_space" -lt 2 ]]; then
        print_colored "$YELLOW" "WARNING: Low disk space available (${available_space}GB). Docker build may fail."
    fi

    if [[ $errors -gt 0 ]]; then
        print_colored "$RED" "Found $errors validation error(s). Cannot proceed with build."
        exit 1
    fi

    return 0
}

# Function to build the Docker image
build_docker_image() {
    local image_name="$1"
    local image_tag="$2"
    local dockerfile_path="$3"
    local context_path="$4"
    
    local full_image_name="${image_name}:${image_tag}"
    
    print_colored "$BLUE" "Starting Docker build for LabArchives MCP Server..."
    print_colored "$BLUE" "Image: $full_image_name"
    print_colored "$BLUE" "Dockerfile: $dockerfile_path"
    print_colored "$BLUE" "Context: $context_path"
    
    # Prepare Docker build command
    local docker_build_cmd="docker build"
    
    # Add build options
    if [[ "$NO_CACHE" == true ]]; then
        docker_build_cmd="$docker_build_cmd --no-cache"
    fi
    
    if [[ "$QUIET" == true ]]; then
        docker_build_cmd="$docker_build_cmd --quiet"
    fi
    
    # Add progress output for verbose mode
    if [[ "$VERBOSE" == true ]]; then
        docker_build_cmd="$docker_build_cmd --progress=plain"
    fi
    
    # Add build arguments if provided
    if [[ -n "$BUILD_ARGS" ]]; then
        docker_build_cmd="$docker_build_cmd $BUILD_ARGS"
    fi
    
    # Add tag, dockerfile, and context
    docker_build_cmd="$docker_build_cmd -t $full_image_name -f $dockerfile_path $context_path"
    
    # Display build command in verbose mode
    if [[ "$VERBOSE" == true ]]; then
        print_colored "$BLUE" "Build command: $docker_build_cmd"
    fi
    
    # Execute Docker build
    print_colored "$YELLOW" "Building Docker image..."
    
    local build_start_time
    build_start_time=$(date +%s)
    
    if eval "$docker_build_cmd"; then
        local build_end_time
        build_end_time=$(date +%s)
        local build_duration=$((build_end_time - build_start_time))
        
        print_colored "$GREEN" "✓ Docker build completed successfully!"
        print_colored "$GREEN" "Image: $full_image_name"
        print_colored "$GREEN" "Build time: ${build_duration}s"
        
        # Display image information
        if [[ "$VERBOSE" == true ]]; then
            print_colored "$BLUE" "Image details:"
            docker images "$image_name" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
        fi
        
        # Display basic usage information
        print_colored "$BLUE" "Usage examples:"
        print_colored "$BLUE" "  docker run --rm $full_image_name --help"
        print_colored "$BLUE" "  docker run --rm -e LABARCHIVES_AKID=your_key -e LABARCHIVES_SECRET=your_secret $full_image_name --notebook-name \"My Notebook\""
        
        return 0
    else
        local build_exit_code=$?
        print_colored "$RED" "✗ Docker build failed with exit code: $build_exit_code"
        print_colored "$RED" "Check the build output above for error details."
        
        # Provide helpful debugging tips
        print_colored "$YELLOW" "Debugging tips:"
        print_colored "$YELLOW" "  - Verify Dockerfile syntax and dependencies"
        print_colored "$YELLOW" "  - Check available disk space"
        print_colored "$YELLOW" "  - Try building with --no-cache flag"
        print_colored "$YELLOW" "  - Ensure Docker daemon has sufficient resources"
        
        return $build_exit_code
    fi
}

# Function to parse command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                HELP=true
                shift
                ;;
            -n|--image-name)
                IMAGE_NAME="$2"
                shift 2
                ;;
            -t|--tag)
                IMAGE_TAG="$2"
                shift 2
                ;;
            -d|--dockerfile)
                DOCKERFILE_PATH="$2"
                shift 2
                ;;
            -c|--context)
                CONTEXT_PATH="$2"
                shift 2
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -q|--quiet)
                QUIET=true
                shift
                ;;
            --no-cache)
                NO_CACHE=true
                shift
                ;;
            --build-arg)
                BUILD_ARGS="$BUILD_ARGS --build-arg $2"
                shift 2
                ;;
            *)
                print_colored "$RED" "ERROR: Unknown option: $1"
                print_colored "$YELLOW" "Use --help to see available options."
                exit 1
                ;;
        esac
    done
    
    # Validate that quiet and verbose are not both set
    if [[ "$QUIET" == true && "$VERBOSE" == true ]]; then
        print_colored "$RED" "ERROR: Cannot use both --quiet and --verbose options."
        exit 1
    fi
}

# Function to print build configuration
print_build_configuration() {
    if [[ "$QUIET" != true ]]; then
        print_colored "$BLUE" "Build Configuration:"
        print_colored "$BLUE" "  Image Name: $IMAGE_NAME"
        print_colored "$BLUE" "  Image Tag: $IMAGE_TAG"
        print_colored "$BLUE" "  Dockerfile: $DOCKERFILE_PATH"
        print_colored "$BLUE" "  Context: $CONTEXT_PATH"
        print_colored "$BLUE" "  No Cache: $NO_CACHE"
        print_colored "$BLUE" "  Verbose: $VERBOSE"
        if [[ -n "$BUILD_ARGS" ]]; then
            print_colored "$BLUE" "  Build Args: $BUILD_ARGS"
        fi
        echo ""
    fi
}

# Function to cleanup on script exit
cleanup() {
    # Remove any temporary files if created
    # Currently no cleanup needed, but placeholder for future enhancements
    :
}

# Set up signal handlers for graceful cleanup
trap cleanup EXIT

# Main script execution
main() {
    # Parse command line arguments
    parse_arguments "$@"
    
    # Show help if requested
    if [[ "$HELP" == true ]]; then
        print_usage
        exit 0
    fi
    
    # Print build configuration
    print_build_configuration
    
    # Check Docker installation
    check_docker_installed
    
    # Validate build prerequisites
    validate_build_prerequisites
    
    # Build the Docker image
    build_docker_image "$IMAGE_NAME" "$IMAGE_TAG" "$DOCKERFILE_PATH" "$CONTEXT_PATH"
    
    # Success message
    if [[ "$QUIET" != true ]]; then
        print_colored "$GREEN" "Docker build process completed successfully!"
        print_colored "$GREEN" "Image '$IMAGE_NAME:$IMAGE_TAG' is ready for deployment or testing."
    fi
}

# Execute main function with all script arguments
main "$@"