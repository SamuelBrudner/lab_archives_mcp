# Contributing to LabArchives MCP Server

Thank you for your interest in contributing to the LabArchives MCP Server! This project bridges LabArchives electronic lab notebook data with AI applications using the Model Context Protocol (MCP). We welcome contributions from the community to improve, extend, and secure this integration.

## Table of Contents

- [Getting Started](#getting-started)
- [How to Contribute](#how-to-contribute)
- [Code of Conduct](#code-of-conduct)
- [Development Setup](#development-setup)
- [Code Style and Quality](#code-style-and-quality)
- [Testing Requirements](#testing-requirements)
- [Security and Compliance](#security-and-compliance)
- [Documentation](#documentation)
- [Issue Reporting](#issue-reporting)
- [Pull Request Process](#pull-request-process)
- [Maintainers and Reviewers](#maintainers-and-reviewers)
- [License](#license)

## Getting Started

### Project Overview

The LabArchives MCP Server is an open-source command-line tool that implements the Model Context Protocol (MCP) to enable secure access to LabArchives electronic lab notebook data for AI applications. The system provides:

- **MCP Protocol Compliance**: Full implementation of JSON-RPC 2.0 based MCP specification
- **Secure Authentication**: LabArchives API integration with comprehensive audit logging
- **Resource Management**: Hierarchical notebook/page/entry data access with scope controls
- **AI Integration**: Direct compatibility with Claude Desktop and other MCP-compatible clients

### Prerequisites

- Python 3.11 or higher
- LabArchives account with API access
- Git for version control
- Familiarity with async/await Python programming

## How to Contribute

### 1. Fork and Clone

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/your-username/labarchives-mcp-server.git
   cd labarchives-mcp-server
   ```

### 2. Create a Development Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bugfix-name
```

### 3. Set Up Development Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

### 4. Make Your Changes

- Follow the code style guidelines below
- Write comprehensive tests for new features
- Update documentation as needed
- Ensure all tests pass locally

### 5. Test Your Changes

```bash
# Run the full test suite
pytest tests/ -v --cov=src/

# Run type checking
mypy src/

# Run code formatting checks
black --check src/ tests/
flake8 src/ tests/
```

### 6. Submit a Pull Request

- Push your branch to your fork
- Create a pull request with a clear description
- Reference any related issues
- Wait for review and respond to feedback

## Code of Conduct

All contributors are expected to adhere to the project's Code of Conduct. Be respectful, inclusive, and constructive in all interactions. We are committed to providing a welcoming and harassment-free experience for everyone, regardless of background or identity.

### Our Standards

- **Be respectful**: Treat all community members with dignity and respect
- **Be inclusive**: Welcome newcomers and support learning
- **Be constructive**: Focus on what is best for the community and project
- **Be professional**: Maintain appropriate language and behavior

## Development Setup

### Environment Configuration

1. **Python Environment**:
   ```bash
   python --version  # Should be 3.11+
   pip install --upgrade pip
   ```

2. **Development Dependencies**:
   ```bash
   pip install -r requirements-dev.txt
   ```

3. **LabArchives API Access**:
   - Create a `.env.example` file with configuration templates
   - Never commit actual credentials
   - Use environment variables for sensitive data

### Development Tools

| Tool | Purpose | Configuration |
|------|---------|---------------|
| **pytest** | Testing framework | `pytest.ini` |
| **black** | Code formatting | `pyproject.toml` |
| **flake8** | Code linting | `.flake8` |
| **mypy** | Type checking | `mypy.ini` |
| **pre-commit** | Git hooks | `.pre-commit-config.yaml` |

## Code Style and Quality

### Language Standards

- **Python Version**: 3.11+
- **Async/Await**: Use async patterns for I/O operations
- **Type Hints**: Required for all public functions and class methods
- **Docstrings**: Follow Google-style docstring format

### Formatting and Linting

#### Code Formatting
```bash
# Format code with black
black src/ tests/

# Check formatting
black --check src/ tests/
```

#### Linting
```bash
# Run flake8 linting
flake8 src/ tests/
```

#### Type Checking
```bash
# Run mypy type checking
mypy src/
```

### Naming Conventions

Follow PEP 8 and project-specific conventions:

- **Functions and Variables**: `snake_case`
- **Classes**: `PascalCase`  
- **Constants**: `UPPER_CASE`
- **Private Methods**: `_leading_underscore`
- **MCP Resources**: `labarchives://` URI scheme

### Code Documentation

```python
async def authenticate_user(access_key: str, access_secret: str) -> AuthSession:
    """Authenticate user with LabArchives API.
    
    Args:
        access_key: LabArchives API access key ID
        access_secret: API password or user token
        
    Returns:
        AuthSession: Authenticated session with user context
        
    Raises:
        AuthenticationError: If credentials are invalid
        APIError: If API request fails
        
    Example:
        >>> session = await authenticate_user("AKID123", "secret_token")
        >>> print(session.user_id)
        12345
    """
```

### Commit Message Guidelines

Use clear, descriptive commit messages:

```bash
# Good commit messages
git commit -m "feat: add notebook scope filtering to resource manager"
git commit -m "fix: handle token expiration in authentication manager"
git commit -m "docs: update API integration examples"

# Include issue references
git commit -m "fix: resolve authentication timeout issue (#123)"
```

## Testing Requirements

### Test Framework

We use **pytest** with the following plugins:
- `pytest-asyncio` for async test support
- `pytest-cov` for coverage reporting
- `pytest-mock` for enhanced mocking

### Test Structure

```
tests/
├── unit/                     # Unit tests
│   ├── test_mcp_server.py
│   ├── test_labarchives_client.py
│   ├── test_authentication.py
│   └── test_resource_manager.py
├── integration/              # Integration tests
│   ├── test_mcp_protocol.py
│   ├── test_api_integration.py
│   └── test_end_to_end.py
├── fixtures/                 # Test data and fixtures
│   ├── labarchives_responses.py
│   └── test_data.py
└── conftest.py              # Shared test configuration
```

### Unit Tests

All new features and bug fixes must include comprehensive unit tests:

```python
import pytest
from unittest.mock import AsyncMock, patch
from src.authentication import AuthenticationManager

class TestAuthenticationManager:
    @pytest.mark.asyncio
    async def test_authenticate_valid_credentials_returns_session(self):
        """Test successful authentication with valid credentials."""
        auth_manager = AuthenticationManager(
            access_key="AKID123",
            access_secret="valid_token"
        )
        
        with patch('src.authentication.api_client') as mock_api:
            mock_api.authenticate.return_value = {"uid": "12345"}
            session = await auth_manager.authenticate()
            
            assert session.user_id == "12345"
            assert session.is_valid()
```

### Integration Tests

Integration tests verify component interactions:

```python
@pytest.mark.asyncio
async def test_mcp_resource_listing_integration(mock_labarchives_api):
    """Test complete MCP resource listing workflow."""
    from src.mcp_server import LabArchivesMCPServer
    
    server = LabArchivesMCPServer(config)
    resources = await server.list_resources()
    
    assert len(resources) > 0
    assert all(r.uri.startswith("labarchives://") for r in resources)
```

### Test Coverage Requirements

| Component | Target Coverage | Minimum Acceptable |
|-----------|----------------|---------------------|
| **Core MCP Logic** | 95% | 90% |
| **API Integration** | 90% | 85% |
| **Authentication** | 100% | 95% |
| **Resource Management** | 90% | 85% |

### Running Tests

```bash
# Run all tests with coverage
pytest tests/ -v --cov=src/ --cov-report=html

# Run specific test categories
pytest tests/unit/ -v
pytest tests/integration/ -v

# Run with performance profiling
pytest tests/ --profile-svg
```

## Security and Compliance

### Security Requirements

This project handles sensitive research data and must maintain high security standards:

#### Credential Security
- **Never commit secrets**: Use environment variables and `.env.example` templates
- **Secure storage**: Credentials only in memory during execution
- **No disk persistence**: No credential caching or storage
- **Audit logging**: All authentication events must be logged (without credentials)

#### Data Privacy
- **GDPR Compliance**: Follow data minimization and privacy by design
- **HIPAA Alignment**: Protect health-related research data
- **No sensitive data logging**: Sanitize all log outputs
- **Stateless operation**: No persistent data storage

#### Code Security
```python
# Good: Secure credential handling
@dataclass
class AuthConfig:
    access_key: str = field(repr=False)  # Hide from repr
    access_secret: str = field(repr=False)  # Hide from repr
    
    def __post_init__(self):
        if not self.access_key or not self.access_secret:
            raise ValueError("Credentials required")

# Bad: Credential exposure
logger.info(f"Authenticating with key: {access_key}")  # NEVER DO THIS
```

### Security Disclosure

If you discover a security vulnerability, please report it privately:

1. **Do NOT open a public issue** for security problems
2. **Report privately** via:
   - Email: security@labarchives-mcp.org
   - GitHub Security Advisories
3. **Include details**: Steps to reproduce, impact assessment, suggested fixes
4. **Allow time**: We aim to respond within 24 hours

### Security Review Process

All contributions undergo security review:
- **Credential handling**: Verify no credential exposure
- **Input validation**: Check for injection vulnerabilities  
- **Access control**: Ensure proper scope enforcement
- **Audit logging**: Verify comprehensive security event logging

## Documentation

### User Documentation

Update `README.md` for user-facing changes:

```markdown
# Example documentation update
## New Feature: Notebook Scope Filtering

You can now restrict MCP server access to specific notebooks:

```bash
labarchives-mcp --notebook-name "Research Lab A" --verbose
```

This limits data exposure to only the specified notebook.
```

### Developer Documentation

Document new modules, classes, and functions:

```python
class ResourceManager:
    """Manages MCP resource discovery and content retrieval.
    
    This class handles the conversion between LabArchives API responses
    and MCP-compliant resource representations, implementing scope
    enforcement and permission validation.
    
    Attributes:
        api_client: LabArchives API client instance
        scope_config: Access scope configuration
        
    Example:
        >>> manager = ResourceManager(api_client, scope_config)
        >>> resources = await manager.list_resources()
        >>> content = await manager.read_resource("labarchives://notebook/123")
    """
```

### API Documentation

Document MCP protocol compliance:

```python
@mcp.resource()
async def read_labarchives_resource(uri: str) -> ResourceContent:
    """Read specific LabArchives resource content.
    
    MCP Protocol: resources/read
    
    Args:
        uri: Resource URI (labarchives://notebook/123/page/456)
        
    Returns:
        ResourceContent: Structured resource data with metadata
        
    Raises:
        ResourceNotFoundError: If resource doesn't exist
        PermissionError: If user lacks access to resource
        
    MCP Compliance:
        - Implements resources/read method
        - Returns structured JSON content
        - Includes optional JSON-LD context
    """
```

### Configuration Examples

Add usage examples to `examples/` directory:

```bash
examples/
├── basic_setup.md
├── docker_deployment.md
├── claude_integration.md
└── troubleshooting.md
```

## Issue Reporting

### Bug Reports

Use the GitHub issue template for bug reports:

**Required Information:**
- **Steps to reproduce**: Detailed reproduction steps
- **Expected behavior**: What should happen
- **Actual behavior**: What actually happens
- **Environment details**: OS, Python version, dependencies
- **Log output**: Relevant log entries (with credentials redacted)

### Feature Requests

Use the feature request template:

**Required Information:**
- **Problem description**: What problem does this solve?
- **Proposed solution**: How should it work?
- **Alternatives considered**: Other approaches evaluated
- **Use case**: Who would benefit and how?

### Security Issues

**DO NOT** use public issues for security vulnerabilities. See [Security Disclosure](#security-disclosure) above.

## Pull Request Process

### Before Submitting

1. **Ensure branch is up to date** with main:
   ```bash
   git checkout main
   git pull upstream main
   git checkout your-branch
   git rebase main
   ```

2. **Run the complete test suite**:
   ```bash
   pytest tests/ -v --cov=src/
   mypy src/
   black --check src/ tests/
   flake8 src/ tests/
   ```

3. **Update documentation** as needed

### Pull Request Template

```markdown
## Description
Brief description of changes made.

## Related Issues
- Fixes #123
- Addresses #456

## Type of Change
- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that causes existing functionality to not work as expected)
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] All tests pass locally
- [ ] Code coverage maintained/improved

## Security Considerations
- [ ] No credentials exposed in code or logs
- [ ] Input validation implemented
- [ ] Access controls maintained
- [ ] Audit logging added where appropriate

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] Tests added and passing
- [ ] No breaking changes (or clearly documented)
```

### Review Process

1. **Automated Checks**: CI pipeline must pass
2. **Code Review**: At least one maintainer review required
3. **Security Review**: Security-focused review for sensitive changes
4. **Testing**: Comprehensive test validation
5. **Documentation**: Documentation completeness check

### Approval Criteria

- [ ] All CI checks pass
- [ ] Code review approved
- [ ] Security review passed (if applicable)
- [ ] Documentation updated
- [ ] Tests provide adequate coverage

## Maintainers and Reviewers

### Review Process

All code is reviewed by at least one core maintainer with focus on:

1. **Security and Compliance**: Credential handling, data protection, audit logging
2. **Code Quality**: Style, testing, documentation
3. **Protocol Compliance**: MCP specification adherence
4. **Performance**: Response times, resource usage
5. **Maintainability**: Code organization, documentation

### Core Team

- **Lead Maintainer**: Responsible for project direction and final decisions
- **Security Reviewers**: Focus on security and compliance aspects
- **API Specialists**: Review LabArchives integration and MCP protocol compliance
- **Documentation Reviewers**: Ensure documentation quality and completeness

### Release Management

Releases are managed by the core team:
- **Semantic Versioning**: Follow semantic versioning principles
- **Release Notes**: Contributors credited in release notes
- **Security Releases**: Fast-track security fixes
- **Breaking Changes**: Clearly documented with migration guides

## License

By contributing to this project, you agree that your contributions will be licensed under the MIT License as specified in the repository.

Your contributions become part of the project and are subject to the same license terms. This ensures the project remains open source and accessible to the research community.

## Getting Help

### Community Support

- **GitHub Discussions**: For questions and community support
- **Issue Tracker**: For bug reports and feature requests
- **Documentation**: Comprehensive guides and examples
- **Code Comments**: Inline documentation and examples

### Development Support

- **Code Review**: Maintainers provide constructive feedback
- **Mentoring**: New contributors receive guidance
- **Documentation**: Comprehensive development guides
- **Testing**: Automated testing and coverage reporting

## Attribution

Portions of these guidelines are inspired by best practices from the Python, Anthropic MCP, and LabArchives open-source communities. We thank these communities for their leadership in open source development practices.

---

**Thank you for contributing to the LabArchives MCP Server!** Your contributions help make AI-enhanced research workflows more accessible and secure for the global research community.