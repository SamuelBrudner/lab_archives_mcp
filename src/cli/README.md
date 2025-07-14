# LabArchives MCP Server CLI

A comprehensive command-line interface for the LabArchives MCP Server, providing secure, read-only access to electronic lab notebooks via the Model Context Protocol (MCP). This tool enables seamless integration between AI applications like Claude Desktop and your LabArchives research data.

## Table of Contents

- [Introduction](#introduction)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Authentication](#authentication)
- [Scope Limitation](#scope-limitation)
- [Usage Examples](#usage-examples)
- [Docker Deployment](#docker-deployment)
- [Integration with Claude Desktop](#integration-with-claude-desktop)
- [Logging and Audit](#logging-and-audit)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)
- [Contributing](#contributing)
- [License](#license)

## Introduction

The LabArchives MCP Server CLI is a production-ready tool that bridges the gap between electronic lab notebook data and AI applications. Built on the Model Context Protocol (MCP), an open standard introduced by Anthropic, it provides a universal way for AI systems to access LabArchives research data securely and efficiently.

### Key Features

- **🔐 Secure Authentication**: Support for both permanent API keys and temporary user tokens
- **📊 Comprehensive Data Access**: Read-only access to notebooks, pages, and entries
- **🎯 Scope Limitation**: Configurable access control to specific notebooks or folders
- **📝 Audit Logging**: Comprehensive logging for compliance and security monitoring
- **🔌 MCP Protocol Compliance**: Full compatibility with MCP specification (2024-11-05)
- **🐳 Docker Ready**: Container support for easy deployment
- **🌍 Multi-Region Support**: Compatible with US, Australian, and European deployments
- **🔧 CLI Interface**: User-friendly command-line interface with extensive configuration options

## Installation

### Prerequisites

- Python 3.11 or higher
- Valid LabArchives account with API access
- LabArchives API credentials (Access Key ID and Secret/Token)

### Installation Methods

#### Method 1: pip Installation (Recommended)

```bash
pip install labarchives-mcp
```

#### Method 2: Docker Installation

```bash
docker pull labarchives-mcp:latest
```

#### Method 3: Development Installation

```bash
git clone https://github.com/org/labarchives-mcp-server.git
cd labarchives-mcp-server
pip install -r requirements.txt
python setup.py install
```

### Verify Installation

```bash
labarchives-mcp --version
labarchives-mcp --help
```

## Quick Start

### 1. Set up Environment Variables

```bash
# Set your LabArchives API credentials
export LABARCHIVES_AKID="your_access_key_id"
export LABARCHIVES_SECRET="your_access_secret_or_token"
export LABARCHIVES_USER="your_email@institution.edu"
```

### 2. Test Authentication

```bash
# Verify your credentials work
labarchives-mcp authenticate --verbose
```

### 3. Start the MCP Server

```bash
# Start server with notebook scoping
labarchives-mcp start --notebook-name "My Research Notebook" --verbose
```

### 4. Configure Claude Desktop

Add the MCP server configuration to your Claude Desktop config file:

```json
{
  "mcpServers": {
    "labarchives": {
      "command": "labarchives-mcp",
      "args": ["start", "--notebook-name", "My Research Notebook", "--verbose"]
    }
  }
}
```

## Configuration

The CLI supports configuration through multiple sources with the following precedence:

1. **CLI Arguments** (highest priority)
2. **Environment Variables**
3. **Configuration Files**
4. **Default Values** (lowest priority)

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LABARCHIVES_AKID` | LabArchives API Access Key ID | Required |
| `LABARCHIVES_SECRET` | API Secret or User Token | Required |
| `LABARCHIVES_USER` | Username (email) for token auth | Required for SSO |
| `LABARCHIVES_API_BASE` | API base URL | `https://api.labarchives.com/api` |
| `LABARCHIVES_LOG_LEVEL` | Logging level | `INFO` |

### Configuration File

Create a JSON configuration file for persistent settings:

```json
{
  "authentication": {
    "access_key_id": "your_access_key_id",
    "api_base_url": "https://api.labarchives.com/api"
  },
  "scope": {
    "notebook_name": "My Research Notebook"
  },
  "output": {
    "json_ld_enabled": true
  },
  "logging": {
    "log_level": "INFO",
    "log_file": "labarchives_mcp.log"
  }
}
```

### CLI Arguments

```bash
labarchives-mcp start [OPTIONS]

Options:
  --access-key-id TEXT     LabArchives API Access Key ID
  --access-secret TEXT     LabArchives API Secret/Token
  --username TEXT          Username for token authentication
  --api-base-url TEXT      LabArchives API base URL
  --notebook-id TEXT       Limit access to specific notebook ID
  --notebook-name TEXT     Limit access to specific notebook name
  --folder-path TEXT       Limit access to specific folder path
  --json-ld               Enable JSON-LD output format
  --log-file TEXT         Path to log file
  --verbose               Enable verbose logging
  --quiet                 Suppress non-error output
  --help                  Show help message
```

## Authentication

The CLI supports two authentication methods:

### 1. Permanent API Key Authentication

For service accounts and direct API access:

```bash
export LABARCHIVES_AKID="AKID1234567890"
export LABARCHIVES_SECRET="your_api_password"
```

### 2. Temporary User Token Authentication

For SSO users with app authentication tokens:

```bash
export LABARCHIVES_AKID="AKID1234567890"
export LABARCHIVES_SECRET="your_app_token"
export LABARCHIVES_USER="your_email@institution.edu"
```

### Regional Endpoints

Configure the appropriate API endpoint for your region:

```bash
# United States (default)
export LABARCHIVES_API_BASE="https://api.labarchives.com/api"

# Australia
export LABARCHIVES_API_BASE="https://auapi.labarchives.com/api"

# Europe
export LABARCHIVES_API_BASE="https://euapi.labarchives.com/api"
```

### Authentication Testing

```bash
# Test authentication without starting the server
labarchives-mcp authenticate --verbose

# Test with specific credentials
labarchives-mcp authenticate \
  --access-key-id "AKID123" \
  --access-secret "token456" \
  --username "user@lab.edu"
```

## Scope Limitation

Control which data the MCP server can access using scope limitations:

### Notebook Scope

Limit access to a specific notebook:

```bash
# By notebook name
labarchives-mcp start --notebook-name "Protein Analysis"

# By notebook ID (more reliable)
labarchives-mcp start --notebook-id "12345"
```

### Folder Scope

Limit access to a specific folder within a notebook:

```bash
labarchives-mcp start --folder-path "/Research/Experiments/2024"
```

### Environment Variable Scope

```bash
export LABARCHIVES_NOTEBOOK_NAME="My Research Notebook"
export LABARCHIVES_FOLDER_PATH="/Research/Active Projects"
```

## Usage Examples

### Basic Usage

```bash
# Start server with environment variables
labarchives-mcp start --verbose

# Start with specific notebook
labarchives-mcp start --notebook-name "Lab Notebook A" --verbose

# Start with JSON-LD support
labarchives-mcp start --notebook-name "Research Data" --json-ld --verbose
```

### Advanced Usage

```bash
# Production deployment with logging
labarchives-mcp start \
  --notebook-name "Production Research" \
  --log-file "/var/log/labarchives-mcp.log" \
  --json-ld \
  --quiet

# Development with verbose logging
labarchives-mcp start \
  --notebook-name "Development Notebook" \
  --verbose \
  --log-file "/tmp/debug.log"
```

### Configuration Management

```bash
# Show current configuration
labarchives-mcp config show

# Validate configuration
labarchives-mcp config validate

# Validate configuration file
labarchives-mcp config validate --config-file config.json
```

## Docker Deployment

### Basic Docker Usage

```bash
# Run with environment variables
docker run -d \
  -e LABARCHIVES_AKID="your_access_key" \
  -e LABARCHIVES_SECRET="your_secret" \
  -e LABARCHIVES_USER="your_email@lab.edu" \
  labarchives-mcp:latest \
  start --notebook-name "Docker Notebook" --verbose
```

### Docker with Volume Mounting

```bash
# Persistent logging
docker run -d \
  -e LABARCHIVES_AKID="your_access_key" \
  -e LABARCHIVES_SECRET="your_secret" \
  -e LABARCHIVES_USER="your_email@lab.edu" \
  -v "/host/logs:/app/logs" \
  labarchives-mcp:latest \
  start --notebook-name "Research" --log-file "/app/logs/mcp.log"
```

### Docker Compose

```yaml
version: '3.8'
services:
  labarchives-mcp:
    image: labarchives-mcp:latest
    environment:
      - LABARCHIVES_AKID=${LABARCHIVES_AKID}
      - LABARCHIVES_SECRET=${LABARCHIVES_SECRET}
      - LABARCHIVES_USER=${LABARCHIVES_USER}
    command: >
      start
      --notebook-name "Research Notebook"
      --json-ld
      --verbose
      --log-file /app/logs/mcp.log
    volumes:
      - "./logs:/app/logs"
    restart: unless-stopped
```

## Integration with Claude Desktop

### Configuration File Setup

Edit your Claude Desktop configuration file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "labarchives": {
      "command": "labarchives-mcp",
      "args": [
        "start",
        "--notebook-name", "My Research Notebook",
        "--json-ld",
        "--verbose"
      ],
      "env": {
        "LABARCHIVES_AKID": "your_access_key_id",
        "LABARCHIVES_SECRET": "your_secret_token",
        "LABARCHIVES_USER": "your_email@institution.edu"
      }
    }
  }
}
```

### Secure Configuration

For production environments, use environment variables:

```json
{
  "mcpServers": {
    "labarchives": {
      "command": "labarchives-mcp",
      "args": [
        "start",
        "--notebook-name", "Production Research",
        "--json-ld",
        "--log-file", "/var/log/labarchives-mcp.log"
      ]
    }
  }
}
```

### Restart Claude Desktop

After configuration changes:

1. Quit Claude Desktop completely
2. Restart Claude Desktop
3. Look for the plug icon (🔌) indicating MCP connection
4. Use the hammer icon (🔨) to access LabArchives resources

## Logging and Audit

### Logging Configuration

```bash
# File logging
labarchives-mcp start --log-file "/var/log/labarchives-mcp.log"

# Verbose logging
labarchives-mcp start --verbose

# Quiet mode (errors only)
labarchives-mcp start --quiet

# Custom log level via environment
export LABARCHIVES_LOG_LEVEL="DEBUG"
```

### Log Levels

- `DEBUG`: Detailed execution information
- `INFO`: General operational information
- `WARNING`: Recoverable issues and warnings
- `ERROR`: System failures and exceptions

### Audit Features

The system provides comprehensive audit logging:

- **Authentication Events**: Login attempts, token validation
- **Data Access Events**: Resource requests, content retrieval
- **API Interactions**: LabArchives API calls and responses
- **Security Events**: Scope violations, authentication failures
- **System Events**: Server startup, shutdown, configuration changes

### Log Analysis

```bash
# Monitor logs in real-time
tail -f /var/log/labarchives-mcp.log

# Search for errors
grep "ERROR" /var/log/labarchives-mcp.log

# Authentication events
grep "Authentication" /var/log/labarchives-mcp.log

# Resource access patterns
grep "Resource accessed" /var/log/labarchives-mcp.log
```

## Troubleshooting

### Common Issues

#### 1. Authentication Failures

```bash
# Check credentials
labarchives-mcp authenticate --verbose

# Verify environment variables
echo $LABARCHIVES_AKID
echo $LABARCHIVES_SECRET
echo $LABARCHIVES_USER

# Test API connectivity
curl -v "https://api.labarchives.com/api/users/user_info"
```

#### 2. Network Connectivity

```bash
# Test DNS resolution
nslookup api.labarchives.com

# Test HTTPS connectivity
curl -v "https://api.labarchives.com/api"

# Check firewall settings
telnet api.labarchives.com 443
```

#### 3. Configuration Issues

```bash
# Validate configuration
labarchives-mcp config validate

# Check configuration file syntax
labarchives-mcp config show

# Test with minimal configuration
labarchives-mcp start --verbose --log-file /tmp/debug.log
```

#### 4. Claude Desktop Integration

```bash
# Verify configuration file syntax
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json | jq .

# Check Claude Desktop logs
# Look for MCP-related messages in system console
```

### Diagnostic Script

Use the included diagnostic script for automated troubleshooting:

```bash
# Run comprehensive diagnostics
./diagnostic_check.sh

# Check specific issues
./diagnostic_check.sh --network
./diagnostic_check.sh --auth
./diagnostic_check.sh --config
```

### Error Codes

| Exit Code | Description |
|-----------|-------------|
| 0 | Success |
| 1 | General error |
| 2 | Authentication error |
| 3 | Network/API error |
| 130 | User interruption (Ctrl+C) |

## FAQ

### Q: What is the Model Context Protocol (MCP)?

A: MCP is an open standard introduced by Anthropic that provides a universal way for AI applications to connect with external data sources. It enables secure, standardized communication between AI systems and tools like the LabArchives MCP Server.

### Q: Do I need special permissions to use this tool?

A: Yes, you need:
- A valid LabArchives account
- API access enabled on your account
- API credentials (Access Key ID and Secret/Token)
- Appropriate permissions to access the notebooks you want to scope

### Q: Is this tool read-only?

A: Yes, the LabArchives MCP Server provides read-only access to your laboratory data. It cannot modify, delete, or create new entries in your notebooks.

### Q: Can I limit access to specific notebooks?

A: Yes, you can use scope limitations to restrict access to:
- Specific notebooks (by name or ID)
- Specific folders within notebooks
- Custom scope patterns

### Q: How do I get LabArchives API credentials?

A: 
1. Log into your LabArchives account
2. Go to Account Settings > API Management
3. Generate an Access Key ID and Secret
4. For SSO users, you may need to use App Authentication tokens

### Q: What regions are supported?

A: The tool supports multiple LabArchives regions:
- United States: `https://api.labarchives.com/api`
- Australia: `https://auapi.labarchives.com/api`
- Europe: `https://euapi.labarchives.com/api`

### Q: How do I enable JSON-LD output?

A: Use the `--json-ld` flag when starting the server:
```bash
labarchives-mcp start --notebook-name "Research" --json-ld
```

### Q: Can I run this in production?

A: Yes, the tool is designed for production use with:
- Comprehensive audit logging
- Security best practices
- Docker container support
- Systemd service integration
- Log rotation and monitoring

### Q: How do I update the server?

A: For pip installations:
```bash
pip install --upgrade labarchives-mcp
```

For Docker:
```bash
docker pull labarchives-mcp:latest
```

### Q: What if I encounter issues?

A: Follow this troubleshooting process:
1. Check the troubleshooting section above
2. Run the diagnostic script
3. Check logs for error messages
4. Verify your credentials and network connectivity
5. Consult the GitHub issues page for known problems

## Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

### Development Setup

```bash
git clone https://github.com/org/labarchives-mcp-server.git
cd labarchives-mcp-server
python -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
```

### Running Tests

```bash
# Run unit tests
pytest tests/unit/

# Run integration tests
pytest tests/integration/

# Run all tests with coverage
pytest --cov=src/cli/
```

### Code Style

We use:
- Black for code formatting
- isort for import sorting
- flake8 for linting
- mypy for type checking

```bash
# Format code
black src/
isort src/

# Check linting
flake8 src/
mypy src/
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

**Version:** 0.1.0  
**Last Updated:** July 2024  
**MCP Protocol Version:** 2024-11-05  

For more information and updates, visit the [GitHub repository](https://github.com/org/labarchives-mcp-server).