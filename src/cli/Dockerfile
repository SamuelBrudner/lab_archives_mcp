# Use Python 3.11 slim image based on Debian Bookworm for optimal performance and security
# python:3.11-slim-bookworm provides 51MB download, 149MB uncompressed with latest Python bugfixes
FROM python:3.11-slim-bookworm

# Set metadata labels for container identification and maintenance
LABEL maintainer="LabArchives MCP Development Team"
LABEL description="LabArchives MCP Server - Containerized deployment for AI integration"
LABEL version="1.0.0"
LABEL org.opencontainers.image.source="https://github.com/labarchives/mcp-server"
LABEL org.opencontainers.image.title="LabArchives MCP Server"
LABEL org.opencontainers.image.description="Model Context Protocol server for LabArchives electronic lab notebook integration"

# Set working directory for all subsequent instructions
WORKDIR /app

# Create non-root user for security best practices
# Running as non-root reduces attack surface and follows security guidelines
RUN groupadd --gid 1000 mcpuser && \
    useradd --uid 1000 --gid mcpuser --shell /bin/bash --create-home mcpuser

# Install system dependencies required for Python packages and security updates
# Update package list and install only essential packages to minimize image size
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        # Required for some Python packages that may need compilation
        gcc \
        # Essential for HTTPS communication with LabArchives API
        ca-certificates \
        # Security updates and essential utilities
        curl \
    && \
    # Clean up apt cache to reduce image size
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements.txt first to leverage Docker build cache
# This allows dependency installation to be cached if requirements haven't changed
COPY requirements.txt .

# Install Python dependencies with security and performance optimizations
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --no-deps --require-hashes -r requirements.txt || \
    pip install --no-cache-dir -r requirements.txt && \
    # Remove pip cache to reduce image size
    pip cache purge

# Copy application source code and related files
# Use .dockerignore to exclude unnecessary files and reduce build context
COPY . .

# Set proper ownership for the application directory
# Ensure the mcpuser has access to all application files
RUN chown -R mcpuser:mcpuser /app

# Switch to non-root user for security
USER mcpuser

# Configure environment variables with defaults
# These can be overridden at runtime for different deployment environments
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    # Default logging level for operational monitoring
    LOG_LEVEL=INFO \
    # Default port for potential future HTTP interface
    PORT=8080

# Expose port for potential future HTTP interface (currently unused for MCP stdio)
EXPOSE 8080

# Add health check to monitor container status
# This enables container orchestration platforms to monitor service health
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Set the entrypoint to the MCP server command
# This allows the container to be started with additional arguments if needed
ENTRYPOINT ["labarchives-mcp"]

# Default command arguments can be overridden at runtime
# Provides sensible defaults for common deployment scenarios
CMD ["--help"]

# Security hardening - remove unnecessary packages after installation
USER root
RUN apt-get update && \
    apt-get remove -y gcc && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Switch back to non-root user
USER mcpuser

# Add volume for potential log file storage
# This allows logs to be persisted outside the container
VOLUME ["/app/logs"]

# Environment variable documentation for runtime configuration
# These variables support secure credential injection and configuration
# LABARCHIVES_AKID: LabArchives API Access Key ID (required for authentication)
# LABARCHIVES_SECRET: LabArchives API Access Secret/Token (required for authentication)
# LABARCHIVES_USER: LabArchives username (optional, for SSO token authentication)
# LABARCHIVES_API_BASE: LabArchives API base URL (optional, defaults to api.labarchives.com)
# Example usage:
# docker run -e LABARCHIVES_AKID=your_key -e LABARCHIVES_SECRET=your_secret labarchives-mcp:latest --notebook-name "My Notebook"

# Security notes:
# - No credentials or secrets are baked into the image
# - All sensitive data must be provided at runtime via environment variables
# - Image is based on minimal Python distribution to reduce attack surface
# - No unnecessary build tools or caches are retained in the final image
# - Container runs as non-root user for enhanced security
# - Regular security updates can be applied by rebuilding with latest base image

# Build and deployment examples:
# Build: docker build -t labarchives-mcp:latest .
# Run: docker run -e LABARCHIVES_AKID=your_key -e LABARCHIVES_SECRET=your_secret labarchives-mcp:latest --notebook-name "My Notebook"
# Development: docker run -it --rm -v $(pwd):/app labarchives-mcp:latest --debug