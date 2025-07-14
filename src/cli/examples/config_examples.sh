#!/bin/bash

#################################################################################
# LabArchives MCP Server Configuration Examples
#################################################################################
#
# This script provides comprehensive examples for configuring and launching the
# LabArchives MCP Server in various deployment scenarios. It demonstrates best
# practices for secure credential management, notebook scoping, and integration
# with Claude Desktop or Docker deployments.
#
# The examples cover:
# - Environment variable configuration
# - CLI argument configuration  
# - Docker deployment scenarios
# - Regional API endpoint configuration
# - Debug and logging options
# - Security best practices
#
# Prerequisites:
# - LabArchives MCP Server installed (pip install labarchives-mcp)
# - Valid LabArchives API credentials
# - Python 3.11+ runtime environment
#
# Security Notice:
# - Never hardcode credentials in scripts
# - Always use environment variables or secure secrets management
# - Regularly rotate API keys and tokens
# - Monitor access logs for suspicious activity
#
# Version: 1.0.0
# Last Updated: 2024-07-15
#
#################################################################################

# Script configuration
set -euo pipefail  # Exit on error, undefined variables, pipe failures
IFS=$'\n\t'        # Set Internal Field Separator for security

# Color codes for output formatting
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly PURPLE='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Display header
display_header() {
    echo -e "${CYAN}"
    echo "################################################################################"
    echo "# LabArchives MCP Server Configuration Examples"
    echo "# Version: 1.0.0"
    echo "# Model Context Protocol Integration for AI-Enhanced Research"
    echo "################################################################################"
    echo -e "${NC}"
}

#################################################################################
# EXAMPLE 1: Basic Environment Variable Configuration
#################################################################################
# This example demonstrates the recommended approach for setting up credentials
# and running the server with notebook scoping using environment variables.
# Environment variables provide secure credential management and are the
# preferred method for production deployments.
#################################################################################

example_1_environment_variables() {
    log_info "Example 1: Basic Environment Variable Configuration"
    echo
    
    cat << 'EOF'
# =============================================================================
# EXAMPLE 1: Basic Environment Variable Configuration
# =============================================================================

# Step 1: Set LabArchives API credentials securely in your shell environment
# These credentials should be obtained from your LabArchives account settings
# under API Management or Application Authentication sections

# Set your LabArchives API Access Key ID
export LABARCHIVES_AKID="your_access_key_id_here"

# Set your LabArchives API Secret/Token
# For SSO users: Use the app authentication token from your profile settings
# For direct users: Use your API password
export LABARCHIVES_SECRET="your_secret_token_here"

# Set your LabArchives username (email address)
# Required for token-based authentication, especially for SSO users
export LABARCHIVES_USER="your_email@institution.edu"

# Optional: Set custom API base URL for regional deployments
# Default: https://api.labarchives.com/api (US region)
# Australia: https://auapi.labarchives.com/api
export LABARCHIVES_API_BASE="https://api.labarchives.com/api"

# Step 2: Launch the MCP server with notebook scoping
# This restricts the server to only access data from the specified notebook
# Recommended for security and compliance with data governance policies

# Option A: Scope to a specific notebook by name
labarchives-mcp --notebook-name "My Research Notebook" --verbose

# Option B: Scope to a specific notebook by ID (more reliable)
labarchives-mcp --notebook-id 12345 --verbose

# Option C: Enable JSON-LD context for enhanced semantic data structure
labarchives-mcp --notebook-name "My Research Notebook" --json-ld --verbose

# Step 3: Verify server is running and accessible
# Check Claude Desktop for the MCP connection indicator (🔌 icon)
# The server should appear in the available tools list

# Security Best Practices:
# 1. Store credentials in secure environment management systems
# 2. Use temporary tokens when possible (they expire automatically)
# 3. Regularly rotate API keys and monitor usage
# 4. Always scope access to specific notebooks or projects
# 5. Enable verbose logging for audit trails in production

EOF
    
    log_success "Example 1 configuration displayed"
    echo
}

#################################################################################
# EXAMPLE 2: CLI Argument Configuration
#################################################################################
# This example shows how to pass credentials and configuration options directly
# as command-line arguments. While less secure than environment variables,
# this method is useful for testing and development scenarios.
#################################################################################

example_2_cli_arguments() {
    log_info "Example 2: CLI Argument Configuration"
    echo
    
    cat << 'EOF'
# =============================================================================
# EXAMPLE 2: CLI Argument Configuration
# =============================================================================

# Direct CLI argument configuration for development and testing
# WARNING: Command-line arguments may be visible in process lists and logs
# Use environment variables for production deployments

# Basic CLI configuration with all parameters
labarchives-mcp \
    --access-key "ABCD1234567890" \
    --access-secret "your_secret_token" \
    --username "researcher@university.edu" \
    --notebook-id 12345 \
    --verbose

# Short form arguments for quick testing
labarchives-mcp -k ABCD1234 -p my_token -u user@lab.edu -n "Lab Notebook A" -v

# Advanced CLI configuration with logging and JSON-LD output
labarchives-mcp \
    --access-key "ABCD1234567890" \
    --access-secret "your_secret_token" \
    --username "researcher@university.edu" \
    --notebook-name "Protein Analysis Research" \
    --json-ld \
    --log-file "/var/log/labarchives-mcp.log" \
    --verbose

# Quiet mode for production with minimal logging
labarchives-mcp \
    --access-key "ABCD1234567890" \
    --access-secret "your_secret_token" \
    --notebook-id 67890 \
    --log-file "/var/log/labarchives-mcp.log" \
    --quiet

# Configuration with regional API endpoint
labarchives-mcp \
    --access-key "ABCD1234567890" \
    --access-secret "your_secret_token" \
    --username "researcher@university.edu" \
    --notebook-name "Australian Research Project" \
    --api-base "https://auapi.labarchives.com/api" \
    --verbose

# Help and version information
labarchives-mcp --help
labarchives-mcp --version

# Security Considerations for CLI Arguments:
# 1. Arguments may be visible in process lists (ps, htop)
# 2. Shell history may record sensitive information
# 3. Log files might capture command lines
# 4. Use environment variables for production deployments
# 5. Clear shell history after testing: history -c

EOF
    
    log_success "Example 2 configuration displayed"
    echo
}

#################################################################################
# EXAMPLE 3: Docker Deployment Configuration
#################################################################################
# This example demonstrates running the LabArchives MCP Server in a Docker
# container with proper environment variable injection and volume mounting.
# Docker deployment provides isolation and consistency across environments.
#################################################################################

example_3_docker_deployment() {
    log_info "Example 3: Docker Deployment Configuration"
    echo
    
    cat << 'EOF'
# =============================================================================
# EXAMPLE 3: Docker Deployment Configuration
# =============================================================================

# Docker deployment provides environment isolation and consistent deployment
# across different systems. Environment variables are passed using -e flags.

# Basic Docker deployment with environment variables
docker run \
    -e LABARCHIVES_AKID="ABCD1234567890" \
    -e LABARCHIVES_SECRET="your_secret_token" \
    -e LABARCHIVES_USER="researcher@university.edu" \
    labarchives-mcp:latest \
    --notebook-name "Research Lab Notebook" \
    --verbose

# Docker deployment with volume mounting for log persistence
docker run \
    -e LABARCHIVES_AKID="ABCD1234567890" \
    -e LABARCHIVES_SECRET="your_secret_token" \
    -e LABARCHIVES_USER="researcher@university.edu" \
    -v "/host/logs:/app/logs" \
    labarchives-mcp:latest \
    --notebook-name "Research Lab Notebook" \
    --log-file "/app/logs/mcp-server.log" \
    --json-ld

# Docker deployment with custom API endpoint for regional instances
docker run \
    -e LABARCHIVES_AKID="ABCD1234567890" \
    -e LABARCHIVES_SECRET="your_secret_token" \
    -e LABARCHIVES_USER="researcher@university.edu" \
    -e LABARCHIVES_API_BASE="https://auapi.labarchives.com/api" \
    labarchives-mcp:latest \
    --notebook-name "Australian Research Notebook" \
    --verbose

# Docker deployment with environment file for credential management
# Create a .env file with your credentials (ensure it's in .gitignore)
cat > .env << 'ENVFILE'
LABARCHIVES_AKID=ABCD1234567890
LABARCHIVES_SECRET=your_secret_token
LABARCHIVES_USER=researcher@university.edu
LABARCHIVES_API_BASE=https://api.labarchives.com/api
ENVFILE

# Run container with environment file
docker run \
    --env-file .env \
    labarchives-mcp:latest \
    --notebook-name "Secure Research Notebook" \
    --json-ld \
    --verbose

# Docker Compose configuration for advanced deployment
cat > docker-compose.yml << 'COMPOSE'
version: '3.8'

services:
  labarchives-mcp:
    image: labarchives-mcp:latest
    environment:
      - LABARCHIVES_AKID=${LABARCHIVES_AKID}
      - LABARCHIVES_SECRET=${LABARCHIVES_SECRET}
      - LABARCHIVES_USER=${LABARCHIVES_USER}
      - LABARCHIVES_API_BASE=${LABARCHIVES_API_BASE:-https://api.labarchives.com/api}
    command: 
      - "--notebook-name"
      - "Research Lab Notebook"
      - "--json-ld"
      - "--verbose"
      - "--log-file"
      - "/app/logs/mcp-server.log"
    volumes:
      - "./logs:/app/logs"
    restart: unless-stopped

  # Optional: Add a monitoring sidecar container
  log-monitor:
    image: alpine:latest
    depends_on:
      - labarchives-mcp
    command: tail -f /app/logs/mcp-server.log
    volumes:
      - "./logs:/app/logs"
COMPOSE

# Launch with Docker Compose
docker-compose up -d

# Docker Security Best Practices:
# 1. Use official Docker images from trusted registries
# 2. Regularly update base images for security patches
# 3. Use environment files (.env) for sensitive data
# 4. Mount volumes for persistent logging
# 5. Enable Docker content trust for image verification
# 6. Use Docker secrets for production deployments
# 7. Run containers with non-root users when possible

EOF
    
    log_success "Example 3 configuration displayed"
    echo
}

#################################################################################
# EXAMPLE 4: Regional API Endpoint Configuration
#################################################################################
# This example demonstrates how to configure the server for different regional
# LabArchives deployments, which use different API base URLs.
#################################################################################

example_4_regional_endpoints() {
    log_info "Example 4: Regional API Endpoint Configuration"
    echo
    
    cat << 'EOF'
# =============================================================================
# EXAMPLE 4: Regional API Endpoint Configuration
# =============================================================================

# LabArchives operates in multiple regions with different API endpoints
# Configure the appropriate endpoint for your institution's deployment

# United States (Default) - api.labarchives.com
export LABARCHIVES_API_BASE="https://api.labarchives.com/api"
labarchives-mcp \
    --notebook-name "US Research Notebook" \
    --verbose

# Australia - auapi.labarchives.com
export LABARCHIVES_API_BASE="https://auapi.labarchives.com/api"
labarchives-mcp \
    --notebook-name "Australian Research Notebook" \
    --verbose

# Europe (if available) - euapi.labarchives.com
export LABARCHIVES_API_BASE="https://euapi.labarchives.com/api"
labarchives-mcp \
    --notebook-name "European Research Notebook" \
    --verbose

# Custom institutional deployment
export LABARCHIVES_API_BASE="https://labarchives.institution.edu/api"
labarchives-mcp \
    --notebook-name "Institutional Research Notebook" \
    --verbose

# CLI argument override for regional endpoints
labarchives-mcp \
    --api-base "https://auapi.labarchives.com/api" \
    --notebook-name "Australian Research Notebook" \
    --verbose

# Docker deployment with regional endpoint
docker run \
    -e LABARCHIVES_AKID="ABCD1234567890" \
    -e LABARCHIVES_SECRET="your_secret_token" \
    -e LABARCHIVES_USER="researcher@university.edu" \
    -e LABARCHIVES_API_BASE="https://auapi.labarchives.com/api" \
    labarchives-mcp:latest \
    --notebook-name "Multi-Regional Research" \
    --verbose

# Testing connectivity to regional endpoints
# Use curl to verify API endpoint accessibility before running the server

echo "Testing US API endpoint..."
curl -s -o /dev/null -w "%{http_code}" "https://api.labarchives.com/api/users/user_info"

echo "Testing Australian API endpoint..."
curl -s -o /dev/null -w "%{http_code}" "https://auapi.labarchives.com/api/users/user_info"

# Regional Configuration Notes:
# 1. Always verify the correct API endpoint with your institution
# 2. Regional endpoints may have different authentication requirements
# 3. Data residency requirements may mandate specific regional endpoints
# 4. Network latency varies by region - choose the nearest endpoint
# 5. Some features may be region-specific or have different availability

EOF
    
    log_success "Example 4 configuration displayed"
    echo
}

#################################################################################
# EXAMPLE 5: Debug and Logging Configuration
#################################################################################
# This example shows various logging and debugging options for troubleshooting
# and monitoring the MCP server in development and production environments.
#################################################################################

example_5_debug_logging() {
    log_info "Example 5: Debug and Logging Configuration"
    echo
    
    cat << 'EOF'
# =============================================================================
# EXAMPLE 5: Debug and Logging Configuration
# =============================================================================

# Comprehensive logging and debugging options for development and production
# monitoring of the LabArchives MCP Server

# Basic verbose logging to console
labarchives-mcp \
    --notebook-name "Development Notebook" \
    --verbose

# Debug logging with file output
labarchives-mcp \
    --notebook-name "Project Data" \
    --verbose \
    --log-file "/var/log/labarchives-mcp/debug.log"

# Quiet mode for production (errors and warnings only)
labarchives-mcp \
    --notebook-name "Production Notebook" \
    --log-file "/var/log/labarchives-mcp/production.log" \
    --quiet

# Structured logging with JSON-LD context for enhanced debugging
labarchives-mcp \
    --notebook-name "Research Analysis" \
    --json-ld \
    --verbose \
    --log-file "/var/log/labarchives-mcp/structured.log"

# Development environment with comprehensive logging
export LABARCHIVES_AKID="ABCD1234567890"
export LABARCHIVES_SECRET="dev_token"
export LABARCHIVES_USER="developer@lab.edu"

labarchives-mcp \
    --notebook-name "Development Testing" \
    --verbose \
    --json-ld \
    --log-file "/tmp/mcp-dev.log"

# Production environment with audit logging
export LABARCHIVES_AKID="PROD1234567890"
export LABARCHIVES_SECRET="prod_token"
export LABARCHIVES_USER="service@institution.edu"

labarchives-mcp \
    --notebook-name "Production Research Data" \
    --log-file "/var/log/labarchives-mcp/audit.log" \
    --json-ld

# Docker deployment with persistent logging
docker run \
    -e LABARCHIVES_AKID="ABCD1234567890" \
    -e LABARCHIVES_SECRET="your_secret_token" \
    -e LABARCHIVES_USER="researcher@university.edu" \
    -v "/host/logs:/app/logs" \
    labarchives-mcp:latest \
    --notebook-name "Docker Research" \
    --verbose \
    --log-file "/app/logs/mcp-server.log"

# Log rotation setup for production deployments
# Create logrotate configuration
cat > /etc/logrotate.d/labarchives-mcp << 'LOGROTATE'
/var/log/labarchives-mcp/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0644 mcp-user mcp-group
    postrotate
        systemctl reload labarchives-mcp || true
    endscript
}
LOGROTATE

# Monitoring and alerting setup
# Example script to monitor log files for errors
cat > monitor_mcp_logs.sh << 'MONITOR'
#!/bin/bash
LOG_FILE="/var/log/labarchives-mcp/production.log"
ERROR_THRESHOLD=5

# Count recent errors
ERROR_COUNT=$(tail -n 1000 "$LOG_FILE" | grep -c "ERROR" || echo 0)

if [ "$ERROR_COUNT" -gt "$ERROR_THRESHOLD" ]; then
    echo "Alert: High error count ($ERROR_COUNT) in MCP server logs"
    # Send alert (email, Slack, etc.)
fi

# Check for authentication failures
AUTH_FAILURES=$(tail -n 1000 "$LOG_FILE" | grep -c "Authentication failed" || echo 0)

if [ "$AUTH_FAILURES" -gt 0 ]; then
    echo "Alert: Authentication failures detected in MCP server"
    # Send security alert
fi
MONITOR

chmod +x monitor_mcp_logs.sh

# Performance monitoring with timing logs
# Enable detailed timing information
export MCP_PERFORMANCE_LOGGING=true
labarchives-mcp \
    --notebook-name "Performance Testing" \
    --verbose \
    --log-file "/var/log/labarchives-mcp/performance.log"

# Log Analysis Commands:
# 1. Monitor logs in real-time:
#    tail -f /var/log/labarchives-mcp/debug.log
#
# 2. Search for specific errors:
#    grep "ERROR" /var/log/labarchives-mcp/production.log
#
# 3. Analyze authentication patterns:
#    grep "Authentication" /var/log/labarchives-mcp/audit.log | head -20
#
# 4. Monitor API response times:
#    grep "response_time" /var/log/labarchives-mcp/performance.log
#
# 5. Check resource access patterns:
#    grep "Resource accessed" /var/log/labarchives-mcp/audit.log

# Logging Best Practices:
# 1. Use structured logging (JSON) for automated analysis
# 2. Implement log rotation to prevent disk space issues
# 3. Set up monitoring and alerting for critical errors
# 4. Separate development and production logging levels
# 5. Include sufficient context in log messages for debugging
# 6. Regularly review logs for security and performance issues
# 7. Ensure logs don't contain sensitive information like tokens

EOF
    
    log_success "Example 5 configuration displayed"
    echo
}

#################################################################################
# EXAMPLE 6: Production Deployment Best Practices
#################################################################################
# This example demonstrates production-ready configuration with security,
# monitoring, and operational best practices.
#################################################################################

example_6_production_deployment() {
    log_info "Example 6: Production Deployment Best Practices"
    echo
    
    cat << 'EOF'
# =============================================================================
# EXAMPLE 6: Production Deployment Best Practices
# =============================================================================

# Production deployment configuration with security, monitoring, and 
# operational best practices for enterprise environments

# Production environment setup with secure credential management
# Use a dedicated service account with minimal required permissions

# Step 1: Create secure environment configuration
cat > /etc/labarchives-mcp/environment << 'PRODENV'
# LabArchives MCP Server Production Configuration
# Managed by: IT Security Team
# Last Updated: 2024-07-15

# API Credentials (replace with actual values)
LABARCHIVES_AKID=PROD_ACCESS_KEY_ID
LABARCHIVES_SECRET=PROD_SECRET_TOKEN
LABARCHIVES_USER=mcp-service@institution.edu

# Regional Configuration
LABARCHIVES_API_BASE=https://api.labarchives.com/api

# Security Settings
MCP_SECURITY_AUDIT=true
MCP_RATE_LIMIT=100
MCP_TIMEOUT=30

# Monitoring Configuration
MCP_METRICS_ENABLED=true
MCP_HEALTH_CHECK_INTERVAL=300
PRODENV

# Secure the environment file
chmod 600 /etc/labarchives-mcp/environment
chown mcp-service:mcp-service /etc/labarchives-mcp/environment

# Step 2: Create systemd service for production deployment
cat > /etc/systemd/system/labarchives-mcp.service << 'SERVICE'
[Unit]
Description=LabArchives MCP Server
Documentation=https://github.com/org/labarchives-mcp-server
After=network.target
Wants=network.target

[Service]
Type=simple
User=mcp-service
Group=mcp-service
WorkingDirectory=/opt/labarchives-mcp
EnvironmentFile=/etc/labarchives-mcp/environment
ExecStart=/opt/labarchives-mcp/venv/bin/labarchives-mcp \
    --notebook-name "Production Research Data" \
    --log-file /var/log/labarchives-mcp/production.log \
    --json-ld \
    --quiet
ExecReload=/bin/kill -HUP $MAINPID
KillMode=mixed
Restart=on-failure
RestartSec=10
TimeoutStopSec=30

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/log/labarchives-mcp
CapabilityBoundingSet=CAP_NET_BIND_SERVICE

# Resource limits
LimitNOFILE=65536
LimitNPROC=4096
MemoryMax=1G
CPUQuota=50%

[Install]
WantedBy=multi-user.target
SERVICE

# Enable and start the service
systemctl daemon-reload
systemctl enable labarchives-mcp
systemctl start labarchives-mcp

# Step 3: Configure monitoring and health checks
cat > /opt/labarchives-mcp/health-check.sh << 'HEALTH'
#!/bin/bash
# LabArchives MCP Server Health Check
# Monitors server status and performance metrics

LOG_FILE="/var/log/labarchives-mcp/production.log"
PID_FILE="/var/run/labarchives-mcp/server.pid"
HEALTH_ENDPOINT="http://localhost:8080/health"

# Check if service is running
if ! systemctl is-active --quiet labarchives-mcp; then
    echo "ERROR: LabArchives MCP Server is not running"
    exit 1
fi

# Check recent log entries for errors
RECENT_ERRORS=$(tail -n 100 "$LOG_FILE" | grep -c "ERROR" || echo 0)
if [ "$RECENT_ERRORS" -gt 10 ]; then
    echo "WARNING: High error count detected ($RECENT_ERRORS)"
fi

# Check authentication status
AUTH_STATUS=$(tail -n 50 "$LOG_FILE" | grep "Authentication successful" | tail -1)
if [ -z "$AUTH_STATUS" ]; then
    echo "WARNING: No recent successful authentication found"
fi

# Check memory usage
MEMORY_USAGE=$(pgrep -f labarchives-mcp | xargs ps -o pid,vsz,rss | awk 'NR>1 {sum+=$3} END {print sum}')
if [ "$MEMORY_USAGE" -gt 1048576 ]; then  # 1GB in KB
    echo "WARNING: High memory usage detected (${MEMORY_USAGE}KB)"
fi

echo "Health check completed successfully"
exit 0
HEALTH

chmod +x /opt/labarchives-mcp/health-check.sh

# Step 4: Set up log monitoring and alerting
cat > /opt/labarchives-mcp/log-monitor.sh << 'LOGMON'
#!/bin/bash
# LabArchives MCP Server Log Monitor
# Analyzes logs for security and operational issues

LOG_FILE="/var/log/labarchives-mcp/production.log"
ALERT_EMAIL="admin@institution.edu"
ALERT_THRESHOLD=5

# Monitor for authentication failures
AUTH_FAILURES=$(tail -n 1000 "$LOG_FILE" | grep -c "Authentication failed" || echo 0)
if [ "$AUTH_FAILURES" -gt 0 ]; then
    echo "SECURITY ALERT: Authentication failures detected ($AUTH_FAILURES)"
    echo "Review logs immediately for potential security breach"
fi

# Monitor for API rate limiting
RATE_LIMIT_HITS=$(tail -n 1000 "$LOG_FILE" | grep -c "Rate limit exceeded" || echo 0)
if [ "$RATE_LIMIT_HITS" -gt "$ALERT_THRESHOLD" ]; then
    echo "PERFORMANCE ALERT: API rate limit exceeded ($RATE_LIMIT_HITS times)"
fi

# Monitor for network connectivity issues
NETWORK_ERRORS=$(tail -n 1000 "$LOG_FILE" | grep -c "Connection timeout\|DNS resolution failed" || echo 0)
if [ "$NETWORK_ERRORS" -gt 0 ]; then
    echo "NETWORK ALERT: Connectivity issues detected ($NETWORK_ERRORS)"
fi

# Monitor for scope violations
SCOPE_VIOLATIONS=$(tail -n 1000 "$LOG_FILE" | grep -c "Scope violation" || echo 0)
if [ "$SCOPE_VIOLATIONS" -gt 0 ]; then
    echo "SECURITY ALERT: Scope violations detected ($SCOPE_VIOLATIONS)"
fi

# Generate daily summary report
DAILY_REQUESTS=$(tail -n 10000 "$LOG_FILE" | grep -c "Resource accessed" || echo 0)
DAILY_ERRORS=$(tail -n 10000 "$LOG_FILE" | grep -c "ERROR" || echo 0)
ERROR_RATE=$(awk "BEGIN {printf \"%.2f\", ($DAILY_ERRORS / ($DAILY_REQUESTS > 0 ? $DAILY_REQUESTS : 1)) * 100}")

echo "Daily Summary:"
echo "  Total Requests: $DAILY_REQUESTS"
echo "  Total Errors: $DAILY_ERRORS"
echo "  Error Rate: $ERROR_RATE%"
LOGMON

chmod +x /opt/labarchives-mcp/log-monitor.sh

# Step 5: Create backup and recovery procedures
cat > /opt/labarchives-mcp/backup.sh << 'BACKUP'
#!/bin/bash
# LabArchives MCP Server Backup Script
# Backs up configuration, logs, and operational data

BACKUP_DIR="/var/backups/labarchives-mcp"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/mcp-backup-$DATE.tar.gz"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup configuration files
tar -czf "$BACKUP_FILE" \
    /etc/labarchives-mcp/ \
    /etc/systemd/system/labarchives-mcp.service \
    /opt/labarchives-mcp/ \
    /var/log/labarchives-mcp/ \
    --exclude='*.log' \
    --exclude='venv/'

# Rotate old backups (keep last 30 days)
find "$BACKUP_DIR" -name "mcp-backup-*.tar.gz" -mtime +30 -delete

echo "Backup completed: $BACKUP_FILE"
BACKUP

chmod +x /opt/labarchives-mcp/backup.sh

# Step 6: Configure automated maintenance
cat > /etc/cron.d/labarchives-mcp << 'CRON'
# LabArchives MCP Server Maintenance Cron Jobs
# Automated health checks, log monitoring, and backups

# Health check every 5 minutes
*/5 * * * * mcp-service /opt/labarchives-mcp/health-check.sh

# Log monitoring every 15 minutes
*/15 * * * * mcp-service /opt/labarchives-mcp/log-monitor.sh

# Daily backup at 2:00 AM
0 2 * * * mcp-service /opt/labarchives-mcp/backup.sh

# Weekly service restart (Sunday 3:00 AM)
0 3 * * 0 root systemctl restart labarchives-mcp

# Monthly log cleanup (1st of month, 4:00 AM)
0 4 1 * * mcp-service find /var/log/labarchives-mcp -name "*.log.*.gz" -mtime +90 -delete
CRON

# Production Security Checklist:
# ✓ Dedicated service account with minimal permissions
# ✓ Secure credential storage (not in command line)
# ✓ Regular security updates and patches
# ✓ Comprehensive audit logging
# ✓ Network security and firewall configuration
# ✓ Regular backup and recovery testing
# ✓ Monitoring and alerting setup
# ✓ Resource limits and rate limiting
# ✓ Log rotation and retention policies
# ✓ Incident response procedures

# Operational Best Practices:
# 1. Regular health checks and monitoring
# 2. Automated log analysis and alerting
# 3. Scheduled maintenance and updates
# 4. Configuration management and version control
# 5. Performance monitoring and optimization
# 6. Disaster recovery procedures
# 7. Documentation and runbooks
# 8. Team training and knowledge sharing

EOF
    
    log_success "Example 6 configuration displayed"
    echo
}

#################################################################################
# EXAMPLE 7: Troubleshooting and Diagnostic Commands
#################################################################################
# This example provides diagnostic commands and troubleshooting procedures
# for common issues encountered when running the LabArchives MCP Server.
#################################################################################

example_7_troubleshooting() {
    log_info "Example 7: Troubleshooting and Diagnostic Commands"
    echo
    
    cat << 'EOF'
# =============================================================================
# EXAMPLE 7: Troubleshooting and Diagnostic Commands
# =============================================================================

# Comprehensive troubleshooting guide for common LabArchives MCP Server issues
# Including diagnostic commands, error resolution, and debugging procedures

# ---------------------------------------------------------------------------
# 1. Connection and Authentication Issues
# ---------------------------------------------------------------------------

# Test LabArchives API connectivity
echo "Testing LabArchives API connectivity..."
curl -v "https://api.labarchives.com/api/users/user_info" \
    -H "Authorization: Bearer YOUR_TOKEN" \
    -H "Content-Type: application/json"

# Test authentication with your credentials
labarchives-mcp --version  # Verify installation
labarchives-mcp --help     # Check available options

# Debug authentication issues
export LABARCHIVES_AKID="your_access_key"
export LABARCHIVES_SECRET="your_secret"
export LABARCHIVES_USER="your_email@institution.edu"

# Run with maximum verbosity for debugging
labarchives-mcp \
    --notebook-name "Test Notebook" \
    --verbose \
    --log-file "/tmp/debug.log"

# Check authentication logs
grep "Authentication" /tmp/debug.log

# ---------------------------------------------------------------------------
# 2. Network and Connectivity Diagnostics
# ---------------------------------------------------------------------------

# Test DNS resolution
nslookup api.labarchives.com
nslookup auapi.labarchives.com

# Test network connectivity
ping -c 4 api.labarchives.com
traceroute api.labarchives.com

# Test HTTPS connectivity
openssl s_client -connect api.labarchives.com:443 -servername api.labarchives.com

# Check firewall and proxy settings
echo "Current proxy settings:"
env | grep -i proxy

# Test with curl for detailed connection information
curl -v --connect-timeout 10 "https://api.labarchives.com/api/users/user_info"

# ---------------------------------------------------------------------------
# 3. Configuration Validation
# ---------------------------------------------------------------------------

# Validate environment variables
echo "Checking environment variables..."
echo "LABARCHIVES_AKID: ${LABARCHIVES_AKID:+[SET]} ${LABARCHIVES_AKID:-[NOT SET]}"
echo "LABARCHIVES_SECRET: ${LABARCHIVES_SECRET:+[SET]} ${LABARCHIVES_SECRET:-[NOT SET]}"
echo "LABARCHIVES_USER: ${LABARCHIVES_USER:+[SET]} ${LABARCHIVES_USER:-[NOT SET]}"
echo "LABARCHIVES_API_BASE: ${LABARCHIVES_API_BASE:-[DEFAULT]}"

# Validate credential format
if [[ ${#LABARCHIVES_AKID} -lt 8 ]]; then
    echo "WARNING: Access Key ID seems too short"
fi

if [[ ${#LABARCHIVES_SECRET} -lt 8 ]]; then
    echo "WARNING: Secret token seems too short"
fi

if [[ ! "$LABARCHIVES_USER" =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
    echo "WARNING: Username doesn't appear to be a valid email address"
fi

# ---------------------------------------------------------------------------
# 4. MCP Protocol Debugging
# ---------------------------------------------------------------------------

# Test MCP server startup
echo "Testing MCP server startup..."
timeout 30 labarchives-mcp \
    --notebook-name "Test Notebook" \
    --verbose \
    --log-file "/tmp/mcp-startup.log" || echo "Startup timeout or error"

# Check MCP server logs
tail -n 50 /tmp/mcp-startup.log

# Test MCP protocol compatibility
echo "Testing MCP protocol compatibility..."
# This would typically be done through Claude Desktop or MCP Inspector

# ---------------------------------------------------------------------------
# 5. Performance Diagnostics
# ---------------------------------------------------------------------------

# Monitor system resources during operation
echo "Monitoring system resources..."
ps aux | grep labarchives-mcp
top -p $(pgrep labarchives-mcp) -n 1

# Check memory usage
echo "Memory usage for MCP server:"
pmap $(pgrep labarchives-mcp) | tail -1

# Monitor network connections
echo "Network connections:"
netstat -tulpn | grep labarchives-mcp

# Check file descriptor usage
echo "File descriptor usage:"
lsof -p $(pgrep labarchives-mcp) | wc -l

# ---------------------------------------------------------------------------
# 6. Log Analysis and Error Patterns
# ---------------------------------------------------------------------------

# Common error patterns and solutions
echo "Analyzing common error patterns..."

# Authentication errors
grep -i "authentication.*failed\|invalid.*credential\|token.*expired" /tmp/debug.log

# Network errors
grep -i "connection.*timeout\|dns.*resolution\|network.*error" /tmp/debug.log

# API errors
grep -i "rate.*limit\|api.*error\|http.*[45][0-9][0-9]" /tmp/debug.log

# Permission errors
grep -i "permission.*denied\|access.*denied\|scope.*violation" /tmp/debug.log

# ---------------------------------------------------------------------------
# 7. Docker Troubleshooting
# ---------------------------------------------------------------------------

# Debug Docker deployment
echo "Docker troubleshooting..."

# Check Docker container status
docker ps -a | grep labarchives-mcp

# View Docker container logs
docker logs labarchives-mcp-container

# Execute shell in running container
docker exec -it labarchives-mcp-container /bin/bash

# Test container networking
docker run --rm labarchives-mcp:latest ping -c 3 api.labarchives.com

# Check container environment
docker run --rm labarchives-mcp:latest env | grep LABARCHIVES

# ---------------------------------------------------------------------------
# 8. Claude Desktop Integration Issues
# ---------------------------------------------------------------------------

# Check Claude Desktop configuration
echo "Claude Desktop integration troubleshooting..."

# Verify configuration file
CLAUDE_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
if [[ -f "$CLAUDE_CONFIG" ]]; then
    echo "Claude Desktop configuration found:"
    cat "$CLAUDE_CONFIG" | jq . || echo "Invalid JSON format"
else
    echo "Claude Desktop configuration not found at: $CLAUDE_CONFIG"
fi

# Check for MCP server in Claude Desktop
echo "Checking MCP server registration..."
# This would require Claude Desktop to be running

# ---------------------------------------------------------------------------
# 9. Automated Diagnostic Script
# ---------------------------------------------------------------------------

# Create comprehensive diagnostic script
cat > diagnostic_check.sh << 'DIAGNOSTIC'
#!/bin/bash
# LabArchives MCP Server Diagnostic Script
# Automated troubleshooting and system validation

echo "=== LabArchives MCP Server Diagnostic Report ==="
echo "Generated: $(date)"
echo "System: $(uname -a)"
echo

# Check Python installation
echo "1. Python Environment:"
python3 --version || echo "Python 3 not found"
pip3 --version || echo "pip3 not found"

# Check package installation
echo "2. Package Installation:"
pip3 show labarchives-mcp || echo "Package not installed"

# Check environment variables
echo "3. Environment Configuration:"
env | grep LABARCHIVES | sed 's/=.*$/=[REDACTED]/'

# Check network connectivity
echo "4. Network Connectivity:"
ping -c 2 api.labarchives.com &>/dev/null && echo "✓ API endpoint reachable" || echo "✗ API endpoint unreachable"

# Check recent logs
echo "5. Recent Log Analysis:"
if [[ -f /var/log/labarchives-mcp/production.log ]]; then
    echo "Recent errors:"
    tail -n 100 /var/log/labarchives-mcp/production.log | grep ERROR | tail -5
else
    echo "No production logs found"
fi

# Check system resources
echo "6. System Resources:"
echo "Memory: $(free -h | grep Mem | awk '{print $3 "/" $2}')"
echo "Disk: $(df -h / | tail -1 | awk '{print $3 "/" $2 " (" $5 ")"}')"

# Check running processes
echo "7. Running Processes:"
pgrep -f labarchives-mcp && echo "✓ MCP server process running" || echo "✗ MCP server not running"

echo "=== End of Diagnostic Report ==="
DIAGNOSTIC

chmod +x diagnostic_check.sh

# ---------------------------------------------------------------------------
# 10. Error Recovery Procedures
# ---------------------------------------------------------------------------

# Service recovery script
cat > service_recovery.sh << 'RECOVERY'
#!/bin/bash
# LabArchives MCP Server Recovery Script
# Automated recovery procedures for common issues

echo "Starting LabArchives MCP Server recovery..."

# Stop existing processes
echo "Stopping existing processes..."
pkill -f labarchives-mcp || echo "No existing processes found"

# Clear temporary files
echo "Clearing temporary files..."
rm -f /tmp/mcp-*.log /tmp/labarchives-*

# Restart with clean environment
echo "Restarting with clean environment..."
unset LABARCHIVES_AKID LABARCHIVES_SECRET LABARCHIVES_USER

# Reload environment from secure location
if [[ -f /etc/labarchives-mcp/environment ]]; then
    source /etc/labarchives-mcp/environment
fi

# Restart service
echo "Restarting MCP server..."
systemctl restart labarchives-mcp || echo "Service restart failed"

# Wait for startup
sleep 5

# Verify recovery
if pgrep -f labarchives-mcp; then
    echo "✓ Recovery successful - MCP server is running"
else
    echo "✗ Recovery failed - manual intervention required"
    exit 1
fi

echo "Recovery completed successfully"
RECOVERY

chmod +x service_recovery.sh

# Common Solutions:
# 1. Authentication Issues:
#    - Verify credentials are correct and not expired
#    - Check regional API endpoint configuration
#    - Ensure username matches token authentication requirements
#
# 2. Network Issues:
#    - Check firewall and proxy settings
#    - Verify DNS resolution for LabArchives endpoints
#    - Test HTTPS connectivity and certificate validation
#
# 3. Configuration Issues:
#    - Validate environment variable format and values
#    - Check Claude Desktop configuration syntax
#    - Verify notebook names and IDs are correct
#
# 4. Performance Issues:
#    - Monitor system resources (memory, CPU, disk)
#    - Check for API rate limiting
#    - Optimize logging verbosity for production
#
# 5. Integration Issues:
#    - Restart Claude Desktop after configuration changes
#    - Check MCP protocol compatibility
#    - Verify server process is running and accessible

EOF
    
    log_success "Example 7 configuration displayed"
    echo
}

#################################################################################
# Main Menu and Interactive Functions
#################################################################################

show_menu() {
    echo -e "${CYAN}Available Configuration Examples:${NC}"
    echo "1. Basic Environment Variable Configuration"
    echo "2. CLI Argument Configuration"
    echo "3. Docker Deployment Configuration"
    echo "4. Regional API Endpoint Configuration"
    echo "5. Debug and Logging Configuration"
    echo "6. Production Deployment Best Practices"
    echo "7. Troubleshooting and Diagnostic Commands"
    echo "8. Show All Examples"
    echo "9. Exit"
    echo
}

run_example() {
    case $1 in
        1) example_1_environment_variables ;;
        2) example_2_cli_arguments ;;
        3) example_3_docker_deployment ;;
        4) example_4_regional_endpoints ;;
        5) example_5_debug_logging ;;
        6) example_6_production_deployment ;;
        7) example_7_troubleshooting ;;
        8) 
            example_1_environment_variables
            example_2_cli_arguments
            example_3_docker_deployment
            example_4_regional_endpoints
            example_5_debug_logging
            example_6_production_deployment
            example_7_troubleshooting
            ;;
        9) 
            log_info "Exiting LabArchives MCP Server configuration examples"
            exit 0
            ;;
        *)
            log_error "Invalid selection. Please choose 1-9."
            return 1
            ;;
    esac
}

#################################################################################
# Main Script Execution
#################################################################################

main() {
    display_header
    
    log_info "LabArchives MCP Server Configuration Examples"
    log_info "This script provides comprehensive configuration examples for various deployment scenarios."
    echo
    
    # Check if running interactively
    if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
        # Interactive mode
        while true; do
            show_menu
            read -p "Select an example (1-9): " choice
            echo
            
            run_example "$choice"
            
            echo
            read -p "Press Enter to continue..."
            echo
        done
    else
        # Script sourced - display all examples
        log_info "Script sourced - displaying all configuration examples"
        run_example 8
    fi
}

# Security validation
validate_environment() {
    log_info "Validating security environment..."
    
    # Check for common security issues
    if [[ -n "${LABARCHIVES_AKID:-}" ]] && [[ -n "${LABARCHIVES_SECRET:-}" ]]; then
        log_warn "Credentials detected in environment - ensure secure handling"
    fi
    
    # Check file permissions
    if [[ -f "/etc/labarchives-mcp/environment" ]]; then
        local perms=$(stat -c "%a" /etc/labarchives-mcp/environment 2>/dev/null)
        if [[ "$perms" != "600" ]]; then
            log_warn "Insecure permissions on environment file - should be 600"
        fi
    fi
    
    log_success "Security validation completed"
}

# Usage information
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo "  -h, --help     Show this help message"
    echo "  -v, --version  Show version information"
    echo "  -e, --example  Show specific example (1-7)"
    echo "  -a, --all      Show all examples"
    echo "  -s, --security Validate security configuration"
    echo
    echo "Examples:"
    echo "  $0                    # Interactive mode"
    echo "  $0 --example 1        # Show environment variable example"
    echo "  $0 --all              # Show all examples"
    echo "  $0 --security         # Validate security configuration"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            usage
            exit 0
            ;;
        -v|--version)
            echo "LabArchives MCP Server Configuration Examples v1.0.0"
            exit 0
            ;;
        -e|--example)
            if [[ -n "$2" ]] && [[ "$2" =~ ^[1-7]$ ]]; then
                run_example "$2"
                exit 0
            else
                log_error "Invalid example number. Use 1-7."
                exit 1
            fi
            ;;
        -a|--all)
            run_example 8
            exit 0
            ;;
        -s|--security)
            validate_environment
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi

#################################################################################
# End of LabArchives MCP Server Configuration Examples
#################################################################################