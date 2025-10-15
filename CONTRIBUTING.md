# Contributing to LabArchives MCP Server

Thank you for your interest in contributing! This document provides guidelines for setting up your development environment and contributing to the project.

## Code of Conduct

This project follows standard open-source community guidelines. Be respectful, constructive, and collaborative.

## Getting Started

### Prerequisites

- **Conda** or **Mamba** (recommended for faster package resolution)
- **Git**
- LabArchives API credentials (for integration testing)

### Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/SamuelBrudner/lab_archives_mcp.git
   cd lab_archives_mcp
   ```

2. **Create the development environment**:
   ```bash
   # Using conda-lock for reproducible environment
   conda-lock install --prefix ./conda_envs/dev conda-lock.yml

   # Activate the environment
   conda activate ./conda_envs/dev
   ```

3. **Install the package in editable mode**:
   ```bash
   pip install -e ".[dev,vector]"
   ```

4. **Install pre-commit hooks**:
   ```bash
   pre-commit install
   pre-commit install --hook-type commit-msg
   ```

### Configuration for Testing

To run integration tests, you'll need LabArchives API credentials:

1. Copy the secrets template:
   ```bash
   cp conf/secrets.example.yml conf/secrets.yml
   ```

2. Add your credentials to `conf/secrets.yml`:
   ```yaml
   LABARCHIVES_AKID: 'your_access_key_id'
   LABARCHIVES_PASSWORD: 'your_api_password'
   LABARCHIVES_UID: 'your_user_id'
   LABARCHIVES_REGION: 'https://api.labarchives.com'
   ```

3. For vector search tests (optional):
   ```yaml
   PINECONE_API_KEY: 'your_pinecone_key'
   ```

See the [README](README.md) for instructions on obtaining LabArchives credentials.

## Running Tests

### Unit Tests (No Credentials Required)

Run unit tests that don't require API access:

```bash
pytest -v -m "not integration"
```

### Integration Tests (Requires Credentials)

Run tests that interact with LabArchives API:

```bash
pytest -v -m integration
```

### All Tests

```bash
pytest -v
```

### Test Coverage

Generate a coverage report:

```bash
pytest --cov=src --cov-report=html --cov-report=term
# Open htmlcov/index.html in your browser
```

### Specific Test Files

```bash
# Test authentication
pytest tests/test_auth.py -v

# Test ELN client
pytest tests/test_eln_client.py -v

# Test page reading
pytest tests/unit/test_page_reading.py -v
```

## Code Style and Quality

This project enforces strict code quality standards via pre-commit hooks:

### Automated Checks

Pre-commit hooks run automatically on every commit:

- **Ruff**: Fast Python linter
- **Black**: Code formatter
- **isort**: Import sorting
- **mypy**: Static type checking
- **interrogate**: Docstring coverage
- **Commitizen**: Conventional commit messages

### Manual Checks

Run all pre-commit checks manually:

```bash
pre-commit run --all-files
```

Run specific checks:

```bash
# Linting
ruff check src tests

# Formatting
black src tests

# Type checking
mypy src

# Import sorting
isort src tests
```

### Auto-fix Issues

Most formatting issues can be auto-fixed:

```bash
black src tests
isort src tests
ruff check --fix src tests
```

## Commit Message Format

This project uses [Conventional Commits](https://www.conventionalcommits.org/). All commits **must** follow this format:

```
<type>[optional scope]: <description>

[optional body]

[optional footer]
```

### Types

- **feat**: New feature (triggers MINOR version bump)
- **fix**: Bug fix (triggers PATCH version bump)
- **docs**: Documentation changes
- **style**: Code style/formatting changes
- **refactor**: Code refactoring without behavior change
- **test**: Adding or updating tests
- **chore**: Build process, tooling, dependencies
- **ci**: CI/CD pipeline changes
- **perf**: Performance improvements

### Examples

```bash
git commit -m "feat(mcp): add semantic search tool"
git commit -m "fix(auth): handle expired UID gracefully"
git commit -m "docs: update installation instructions"
git commit -m "test: add unit tests for page navigation"
```

### Breaking Changes

For breaking changes, add `!` after the type or add `BREAKING CHANGE:` in the footer:

```bash
git commit -m "feat!: redesign authentication API"
```

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/my-new-feature
# or
git checkout -b fix/bug-description
```

### 2. Make Changes

- Write code following existing patterns
- Add tests for new functionality
- Update documentation as needed
- Ensure all tests pass

### 3. Run Quality Checks

```bash
# Run tests
pytest -v -m "not integration"

# Run pre-commit checks
pre-commit run --all-files

# Check type coverage
mypy src
```

### 4. Commit Changes

```bash
git add .
git commit -m "feat(scope): description of change"
```

The pre-commit hook will:
- Run code formatters and linters
- Validate commit message format
- Block the commit if checks fail

### 5. Push and Create Pull Request

```bash
git push origin feature/my-new-feature
```

Create a pull request on GitHub with:
- Clear description of changes
- Link to related issues
- Screenshots/examples if applicable

## Pull Request Guidelines

### PR Title

Use the same Conventional Commits format:

```
feat(mcp): add notebook search functionality
fix(auth): resolve token expiration issue
```

### PR Description

Include:
- **Summary**: What does this PR do?
- **Motivation**: Why is this change needed?
- **Implementation**: How does it work?
- **Testing**: How was it tested?
- **Breaking Changes**: Any API changes?

### PR Checklist

- [ ] Tests pass locally (`pytest -v -m "not integration"`)
- [ ] Pre-commit hooks pass (`pre-commit run --all-files`)
- [ ] New functionality has unit tests
- [ ] Documentation updated (README, docstrings)
- [ ] Commit messages follow Conventional Commits
- [ ] No breaking changes (or clearly documented)

## Project Structure

```
lab_archives_mcp/
├── src/
│   ├── labarchives_mcp/       # Core MCP server
│   │   ├── auth.py            # Authentication & signing
│   │   ├── eln_client.py      # LabArchives API client
│   │   ├── mcp_server.py      # FastMCP server
│   │   ├── transform.py       # XML→JSON transformation
│   │   └── upload_client.py   # Upload functionality
│   └── vector_backend/        # Semantic search
│       ├── models.py          # Pydantic models
│       ├── chunking.py        # Text chunking
│       ├── embedding.py       # Embedding client(s)
│       ├── config.py          # Hydra config loading
│       └── index.py           # Vector index operations
├── tests/
│   ├── unit/                  # Unit tests (no API calls)
│   ├── spec/                  # Specification tests
│   └── test_vector_backend/   # Vector search tests
├── conf/                      # Configuration files
├── scripts/                   # Utility scripts
└── docs/                      # Documentation

```

## Adding New Features

### 1. New MCP Tool

To add a new tool to the MCP server:

1. Add the API method to `eln_client.py`:
   ```python
   async def my_new_method(self, param: str) -> MyResultType:
       """Docstring with API details."""
       response = await self._call_api("method_name", {"param": param})
       return parse_response(response)
   ```

2. Add the tool to `mcp_server.py`:
   ```python
   @mcp.tool()
   async def my_new_tool(param: str) -> MyResultType:
       """Tool description for AI agents."""
       return await client.my_new_method(param)
   ```

3. Write unit tests in `tests/unit/`:
   ```python
   @pytest.mark.asyncio
   async def test_my_new_method():
       # Test implementation
       pass
   ```

4. Update documentation in `README.md`

### 2. New API Endpoint

1. Add method to `LabArchivesClient` class
2. Add Pydantic model for response schema
3. Add unit tests with mocked responses
4. Add integration test (marked with `@pytest.mark.integration`)
5. Update API documentation

## Debugging

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Or set environment variable:
```bash
export LOG_LEVEL=DEBUG
```

### Check Logs

Logs are written to `logs/` directory:
```bash
tail -f logs/labarchives_mcp.log
```

### Interactive Testing

```python
from labarchives_mcp.auth import Credentials
from labarchives_mcp.eln_client import LabArchivesClient, AuthenticationManager
import httpx, asyncio

async def test():
    creds = Credentials.from_file()
    async with httpx.AsyncClient() as client:
        auth = AuthenticationManager(client, creds)
        uid = await auth.ensure_uid()
        notebooks = await LabArchivesClient(client, auth).list_notebooks(uid)
        print(notebooks)

asyncio.run(test())
```

## Release Process

Releases are managed via [Commitizen](https://commitizen-tools.github.io/commitizen/):

```bash
# Preview version bump
cz bump --dry-run

# Create release (auto-determines version from commits)
cz bump --yes

# Push release
git push && git push --tags
```

This automatically:
- Analyzes commit history
- Determines version bump (major/minor/patch)
- Updates `CHANGELOG.md`
- Creates git tag

### Version Configuration

- Source of truth: `pyproject.toml` (`version = "<current>"`)
- Commitizen configuration: `[tool.commitizen]` in `pyproject.toml`
- Tags use `v` prefix (e.g., `v0.2.0`); CHANGELOG follows Keep a Changelog format

If you are using the pinned conda environment, you can also run Commitizen via `conda run` without activating:

```bash
conda run -p ./conda_envs/dev cz bump --dry-run --yes
conda run -p ./conda_envs/dev cz bump --yes
```

## Getting Help

- **Issues**: Open an issue on GitHub for bugs or feature requests
- **Discussions**: Use GitHub Discussions for questions
- **Documentation**: Check the [README](README.md) and inline code documentation

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
