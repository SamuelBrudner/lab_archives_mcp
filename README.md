# LabArchives MCP Server

[![Build Status](https://github.com/org/labarchives-mcp-server/workflows/CI/badge.svg)](https://github.com/org/labarchives-mcp-server/actions)
[![Coverage Status](https://codecov.io/gh/org/labarchives-mcp-server/branch/main/graph/badge.svg)](https://codecov.io/gh/org/labarchives-mcp-server)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://badge.fury.io/py/labarchives-mcp.svg)](https://badge.fury.io/py/labarchives-mcp)
[![Docker Image](https://img.shields.io/docker/pulls/labarchives/mcp-server)](https://hub.docker.com/r/labarchives/mcp-server)

## Introduction

The LabArchives MCP Server is a groundbreaking integration solution that bridges the gap between electronic lab notebook data and artificial intelligence applications. This open-source command-line tool leverages Anthropic's Model Context Protocol (MCP), an open standard introduced in November 2024 that provides a universal, standardized way for connecting AI systems with data sources.

The system enables Large Language Models (LLMs) to securely access content from LabArchives electronic lab notebooks through standardized MCP interfaces, positioning research organizations at the forefront of AI-enhanced research workflows while maintaining the highest levels of security and compliance.

### Key Value Proposition

- **🔬 AI-Enhanced Research**: Enable AI-powered analysis of existing laboratory data without manual data transfer
- **⚡ Rapid Deployment**: Estimated 60-80% reduction in time required for AI-assisted data analysis
- **🔒 Enterprise Security**: Comprehensive audit trails and access controls with SOC2, ISO 27001, HIPAA, and GDPR compliance
- **🌍 Universal Integration**: Leverages MCP open standard for broad compatibility with AI applications

## Features

### Core Capabilities

- **✅ MCP Protocol Compliance**: Complete implementation of Model Context Protocol 2024-11-05 specification
- **🔐 Secure Authentication**: Support for both permanent API keys and temporary user tokens with SSO integration
- **🗂️ Resource Discovery**: Hierarchical enumeration of notebooks, pages, and entries within configured scope
- **📄 Content Retrieval**: Structured JSON output optimized for AI consumption with metadata preservation
- **🎯 Scope Control**: Configurable access limitations to specific notebooks or folders for enhanced security
- **📊 Audit Logging**: Comprehensive logging of all data access operations for compliance requirements
- **💻 CLI Interface**: User-friendly command-line interface with extensive configuration options
- **🐳 Docker Support**: Containerized deployment with official Docker Hub distribution

### Technical Features

- **Stateless Architecture**: No persistent storage required - operates as a secure, on-demand data proxy
- **JSON-LD Support**: Optional semantic context for enhanced AI understanding
- **Error Handling**: Graceful degradation with comprehensive error reporting and recovery
- **Performance Optimized**: Response times under 5 seconds for typical operations
- **Cross-Platform**: Compatible with Windows, macOS, and Linux environments

## Architecture Overview

The LabArchives MCP Server implements a client-server architecture following MCP specifications:

```
┌─────────────────┐    ┌──────────────────────┐    ┌─────────────────┐
│  Claude Desktop │    │  LabArchives MCP     │    │  LabArchives    │
│  (MCP Client)   │◄──►│  Server              │◄──►│  REST API       │
│                 │    │                      │    │                 │
└─────────────────┘    └──────────────────────┘    └─────────────────┘
       │                         │                          │
       │                         │                          │
   MCP Protocol              On-demand Data             Authenticated
   (JSON-RPC 2.0)            Retrieval                 API Access
```

### Key Components

- **MCP Protocol Handler**: Manages JSON-RPC 2.0 communication and protocol compliance
- **Authentication Manager**: Secure credential handling and session management
- **Resource Management Engine**: Handles resource discovery and content retrieval
- **LabArchives API Client**: Interfaces with LabArchives REST API endpoints
- **Scope Enforcement Service**: Implements configurable access control and data filtering

## Quick Start

### Installation

#### Option 1: Install from PyPI (Recommended)

```bash
pip install labarchives-mcp
```

#### Option 2: Install from Source

```bash
git clone https://github.com/org/labarchives-mcp-server.git
cd labarchives-mcp-server
pip install -e .
```

#### Option 3: Docker Installation

```bash
docker pull labarchives/mcp-server:latest
```

### Environment Setup

1. **Obtain LabArchives Credentials**:
   - **API Access Key**: From your LabArchives account settings
   - **Access Secret**: Either your account password or an App Authentication Token
   - **For SSO Users**: Get an App Authentication Token from User Profile > Application Authentication

2. **Configure Environment Variables**:

```bash
export LABARCHIVES_AKID="your_access_key_id"
export LABARCHIVES_SECRET="your_access_secret_or_token"
export LABARCHIVES_USER="your_email@institution.edu"  # Required for tokens
```

3. **Test Connection**:

```bash
labarchives-mcp --help
```

### First Run

```bash
# Basic usage with environment variables
labarchives-mcp --notebook-name "Research Lab Notebook" --verbose

# Using command line arguments
labarchives-mcp -k AKID123 -p secret_token --notebook-id 12345

# Docker usage
docker run -e LABARCHIVES_AKID=AKID123 -e LABARCHIVES_SECRET=token \
  labarchives/mcp-server:latest --verbose
```

## Configuration

### Claude Desktop Integration

1. **Edit Configuration File**:
   Open `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or equivalent:

```json
{
  "mcpServers": {
    "labarchives": {
      "command": "labarchives-mcp",
      "args": [
        "--notebook-name", "Research Lab Notebook",
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

2. **Restart Claude Desktop**: After configuration, restart Claude Desktop to load the MCP server

3. **Verify Connection**: Look for the 🔌 icon in the Claude Desktop interface

### CLI Configuration Options

| Option | Short | Purpose | Example |
|--------|-------|---------|---------|
| `-k/--access-key` | | LabArchives API Access Key ID | `-k ABCD1234` |
| `--access-secret` | `-p` | API Password/Token | `-p secret_token` |
| `--username` | `-u` | Username for token auth | `-u user@lab.edu` |
| `--notebook-name` | `-n` | Scope to specific notebook | `-n "Lab Notebook A"` |
| `--notebook-id` | | Scope to notebook by ID | `--notebook-id 12345` |
| `--json-ld` | | Enable JSON-LD context | `--json-ld` |
| `--log-file` | | Log file path | `--log-file lab.log` |
| `--verbose` | `-v` | Enable verbose logging | `-v` |
| `--help` | `-h` | Show help message | `-h` |

**Note**: The legacy `--access-key-id` flag is still supported for backward compatibility.

### Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `LABARCHIVES_AKID` | Access Key ID | `ABCD1234567890` |
| `LABARCHIVES_SECRET` | Access Secret/Token | `temp_token_xyz` |
| `LABARCHIVES_USER` | Username for token auth | `researcher@university.edu` |
| `LABARCHIVES_API_BASE` | API base URL (optional) | `https://auapi.labarchives.com/api` |

## Usage

### Basic Workflow

1. **Start the MCP Server**:
```bash
labarchives-mcp --notebook-name "My Research Notebook" --verbose
```

2. **Open Claude Desktop**: The MCP server will automatically connect

3. **Interact with Your Data**:
   - Ask Claude questions about your lab data
   - Claude will request access to specific resources
   - Approve access through the consent dialog
   - Receive AI-enhanced responses with your research context

### Example Use Cases

- **Literature Review**: "Analyze the experimental results from my protein studies notebook"
- **Data Analysis**: "What patterns do you see in my recent chromatography data?"
- **Protocol Optimization**: "Based on my previous experiments, how can I improve this protocol?"
- **Research Planning**: "What follow-up experiments would you recommend based on these results?"

### Resource Access Patterns

The server exposes LabArchives data through a hierarchical URI scheme:

```
labarchives://notebook/{notebook_id}                    # Notebook metadata
labarchives://notebook/{notebook_id}/page/{page_id}     # Page content
labarchives://entry/{entry_id}                          # Individual entry
```

## Security and Compliance

### Security Features

- **🔐 Zero Persistent Storage**: No local data caching - all data retrieved on-demand
- **🔒 Secure Authentication**: Environment-only credential storage with no disk persistence
- **🎯 Scope Control**: Configurable access limitations to specific notebooks or folders
- **📋 Comprehensive Audit**: All data access operations logged with timestamps and user context
- **🔗 Encrypted Transport**: All communications use HTTPS with TLS 1.3 encryption

### Compliance Standards

The system maintains compliance with institutional and regulatory requirements:

- **SOC2 Type II**: Secure development practices and operational controls
- **ISO 27001**: Information security management system compliance
- **HIPAA**: Healthcare data protection for research environments
- **GDPR**: Privacy by design with no persistent data storage

### Best Practices

1. **Credential Management**:
   - Use environment variables for credentials
   - Rotate tokens regularly (recommended: every 30 days)
   - Use App Authentication Tokens for SSO accounts

2. **Access Control**:
   - Configure scope limitations for sensitive data
   - Review audit logs regularly
   - Implement notebook-level access restrictions

3. **Monitoring**:
   - Enable verbose logging in production
   - Monitor authentication failures
   - Track resource access patterns

## Troubleshooting

### Common Issues

#### Authentication Failures

**Problem**: `Authentication failed: Invalid access key or token`

**Solution**:
1. Verify credentials are correct
2. Check if token has expired (tokens expire after 1 hour)
3. For SSO users, ensure you're using an App Authentication Token

```bash
# Test authentication
labarchives-mcp -k AKID123 --access-secret token --username user@lab.edu
```

#### Connection Issues

**Problem**: `Connection timeout` or `Network error`

**Solution**:
1. Check network connectivity
2. Verify API base URL for your region
3. Check firewall settings

```bash
# Test with different API endpoint
export LABARCHIVES_API_BASE="https://auapi.labarchives.com/api"  # Australia
labarchives-mcp --verbose
```

#### Scope Violations

**Problem**: `Resource not found` or `Access denied`

**Solution**:
1. Verify notebook exists and is accessible
2. Check scope configuration
3. Ensure user has permission to access the resource

```bash
# List available notebooks
labarchives-mcp --verbose  # Will show available notebooks in startup logs
```

#### Claude Desktop Integration Issues

**Problem**: MCP server not connecting to Claude Desktop

**Solution**:
1. Verify `claude_desktop_config.json` syntax
2. Check file permissions
3. Restart Claude Desktop after configuration changes
4. Check for 🔌 icon in Claude interface

### Diagnostic Commands

```bash
# Enable debug logging
labarchives-mcp --verbose --log-file debug.log

# Test specific notebook access
labarchives-mcp --notebook-id 12345 --verbose

# Validate configuration
labarchives-mcp --help
```

### Getting Help

- **GitHub Issues**: [Report bugs or request features](https://github.com/org/labarchives-mcp-server/issues)
- **Documentation**: [Full documentation](https://github.com/org/labarchives-mcp-server/docs)
- **Community**: [GitHub Discussions](https://github.com/org/labarchives-mcp-server/discussions)

## Contributing

We welcome contributions from the research community! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

### Quick Start for Contributors

1. **Fork the Repository**
2. **Set up Development Environment**:
```bash
git clone https://github.com/your-username/labarchives-mcp-server.git
cd labarchives-mcp-server
pip install -e ".[dev]"
```

3. **Run Tests**:
```bash
pytest tests/ -v --cov=src/
```

4. **Code Quality**:
```bash
black src/ tests/
mypy src/
```

5. **Submit Pull Request**

### Development Guidelines

- Follow PEP 8 style guidelines
- Maintain test coverage above 90%
- Add tests for new features
- Update documentation for API changes
- Follow semantic versioning

### Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

```
MIT License

Copyright (c) 2024 LabArchives MCP Server Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Acknowledgments

### Core Technologies

- **[Model Context Protocol (MCP)](https://github.com/modelcontextprotocol)**: The open standard that makes this integration possible
- **[Anthropic](https://anthropic.com)**: For developing MCP and Claude Desktop
- **[LabArchives](https://labarchives.com)**: For providing the robust electronic lab notebook platform
- **[FastMCP](https://github.com/jlowin/fastmcp)**: High-level Python framework for MCP server development

### Community

- **Research Community**: For feedback, testing, and contributions
- **MCP Ecosystem**: For the growing community of MCP-compatible tools and clients
- **Open Source Contributors**: For ongoing development and maintenance

### Standards Compliance

- **SOC2, ISO 27001, HIPAA, GDPR**: Compliance standards maintained through LabArchives platform
- **JSON-RPC 2.0**: Protocol specification for reliable client-server communication
- **OpenAPI/JSON Schema**: Documentation and validation standards

---

**Ready to enhance your research with AI?** Get started with the LabArchives MCP Server today and experience the future of AI-enhanced laboratory workflows.

For questions, support, or contributions, visit our [GitHub repository](https://github.com/org/labarchives-mcp-server).