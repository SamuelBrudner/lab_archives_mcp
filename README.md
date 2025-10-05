# LabArchives MCP Server

[![Tests](https://github.com/SamuelBrudner/lab_archives_mcp/workflows/Tests/badge.svg?branch=main)](https://github.com/SamuelBrudner/lab_archives_mcp/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## Overview

A **Model Context Protocol (MCP) server** that connects AI assistants to LabArchives electronic lab notebooks (ELN). This enables researchers to chat with their lab data, search notebooks semantically, and integrate lab work into AI-assisted workflows.

**Key Features:**
- 🔍 **Semantic Search**: Vector-based search across notebook content
- 📖 **Read Access**: List notebooks, navigate pages, read entries
- 🤖 **AI Integration**: Works with Claude Desktop, Windsurf, and any MCP client
- 🔐 **Secure**: API key authentication with HMAC-SHA512 signing
- 📦 **Reproducible**: Conda-lock environment with pinned dependencies

---

## Features

✅ **Implemented**
- List all notebooks for a user
- Navigate notebook pages and folders
- Read page entries (text, headings, attachments)
- Semantic search across notebook content (vector search)
- Upload files with code provenance metadata (experimental)
- Full HMAC-SHA512 authentication flow

🚧 **Experimental**
- File upload with Git/Python provenance tracking

🔮 **Future**
- Attachment downloads
- Advanced search filters
- Batch operations

---

## Architecture

* **Language**: Python.
* **Modules**:

  * `auth.py` – API signing, OAuth login, uid cache.
  * `eln_client.py` – minimal ELN API call for listing notebooks.
  * `transform.py` – XML→JSON, error mapping.
  * `mcp_server.py` – MCP protocol server.

---

## Setup

### 1. Clone and Install

```bash
git clone https://github.com/SamuelBrudner/lab_archives_mcp.git
cd lab_archives_mcp
```

### 2. Create Environment

Create the pinned Conda environment (local prefix):

```bash
conda-lock install --prefix ./conda_envs/labarchives-mcp-pol conda-lock.yml
```

Activate it:

```bash
conda activate ./conda_envs/labarchives-mcp-pol
```

Install git hooks and tooling:

```bash
pre-commit install
pre-commit install --hook-type commit-msg
```

### 3. Configure LabArchives Credentials

Copy the secrets template:

```bash
cp conf/secrets.example.yml conf/secrets.yml
```

Contact LabArchives support to request API access credentials. You'll need:
- **Access Key ID** (`akid`)
- **Access Password** (used for HMAC-SHA512 signature)
- **API Region** (e.g., `https://api.labarchives.com`)

Edit `conf/secrets.yml` and add your credentials:

```yaml
LABARCHIVES_AKID: 'your_access_key_id'
LABARCHIVES_PASSWORD: 'your_api_password'
LABARCHIVES_REGION: 'https://api.labarchives.com'
OPENAI_API_KEY: 'sk-...'
PINECONE_API_KEY: 'your_pinecone_key'
PINECONE_ENVIRONMENT: 'us-east-1'
```

### 4. Obtain Your User ID (UID)

The LabArchives API requires a user-specific ID (`uid`) for all operations. You have two options:

#### Option A: Use Temporary Password Token (Recommended)

1. Log into your LabArchives notebook in the web browser
2. Navigate to **Account Settings** → **Password Token for External Applications**
3. Click to generate a temporary token (valid for 1 hour)
4. Copy the email and password token displayed
5. Run the helper script:

   ```bash
   conda run -p ./conda_envs/labarchives-mcp-pol python scripts/resolve_uid.py redeem \
       --email your.email@institution.edu \
       --auth-code <paste_token_here>
   ```

6. The script will print your UID. Copy it into `conf/secrets.yml`:

   ```yaml
   LABARCHIVES_UID: 'your_uid_value'
   ```

#### Option B: Browser-Based Login Flow

If you prefer the browser flow (or temporary tokens aren't working):

1. Generate a login URL:

   ```bash
   conda run -p ./conda_envs/labarchives-mcp-pol python scripts/resolve_uid.py login-url
   ```

2. Open the URL in your browser and complete the LabArchives sign-in
3. After redirect, extract the `auth_code` from the URL
4. Run the redeem command (same as Option A step 5)

**Note**: The UID is permanent for your account—once obtained, store it in `conf/secrets.yml` and you won't need to retrieve it again unless your LabArchives password changes.

### 5. Verify Setup

Test that everything works:

```bash
conda run -p ./conda_envs/labarchives-mcp-pol python -c "
from labarchives_mcp.auth import Credentials
from labarchives_mcp.eln_client import LabArchivesClient, AuthenticationManager
import httpx, asyncio

async def test():
    creds = Credentials.from_file()
    async with httpx.AsyncClient() as client:
        auth = AuthenticationManager(client, creds)
        uid = await auth.ensure_uid()
        print(f'✓ UID verified: {uid}')
        notebooks = await LabArchivesClient(client, auth).list_notebooks(uid)
        print(f'✓ Retrieved {len(notebooks)} notebooks')

asyncio.run(test())
"
```

### 6. Example: Querying Your Notebooks with AI

Once configured with an AI assistant (Windsurf or Claude Desktop), you can conversationally interact with your lab notebooks:

```
You: "What protocols did I document for my navigation experiments?"

AI: [Automatically calls list_labarchives_notebooks(),
     list_notebook_pages(), read_notebook_page()]

AI: "In your 'Mosquito Navigation' notebook, you documented three main protocols:

1. Wind tunnel setup with IR tracking (updated Aug 12, 2024)
   - Camera calibration procedure
   - LED array configuration
   - Temperature and humidity controls

2. Odor delivery system calibration (updated Aug 13, 2024)
   - Olfactometer settings
   - Odor concentration measurements
   - Flow rate verification

3. Flight trajectory analysis pipeline (updated Aug 15, 2024)
   - Video preprocessing steps
   - Tracking algorithm parameters
   - Statistical analysis methods

Would you like me to retrieve specific details from any of these protocols?"
```

The AI assistant autonomously:
- Searches through your notebooks to find relevant content
- Reads the appropriate pages and entries
- Synthesizes the information into a coherent answer
- Maintains context for follow-up questions

You can also use semantic search: *"Find experiments related to olfactory behavior"* will retrieve conceptually related content even if exact keywords differ.

### 7. Run the MCP Server

The server can be started in several ways:

```bash
# Method 1: As a Python module
conda run -p ./conda_envs/labarchives-mcp-pol python -m labarchives_mcp

# Method 2: Using the console script (after pip install -e .[dev])
conda run -p ./conda_envs/labarchives-mcp-pol labarchives-mcp

# Method 3: Direct Python (if environment is activated)
conda activate ./conda_envs/labarchives-mcp-pol
labarchives-mcp
```

The server runs in stdio mode and waits for MCP protocol messages. Press `Ctrl+C` to stop.

---

## Connecting to AI Agents

The MCP server exposes LabArchives notebooks to AI agents via the MCP protocol.

### Windsurf (Codeium) - Verified Working ✅

**Config file**: `~/.codeium/windsurf/mcp_config.json`

```json
{
  "mcpServers": {
    "labarchives": {
      "command": "conda",
      "args": [
        "run",
        "--no-capture-output",
        "-p",
        "/absolute/path/to/lab_archives_mcp/conda_envs/labarchives-mcp-pol",
        "python",
        "-m",
        "labarchives_mcp"
      ],
      "env": {
        "LABARCHIVES_CONFIG_PATH": "/absolute/path/to/lab_archives_mcp/conf/secrets.yml",
        "FASTMCP_SHOW_CLI_BANNER": "false",
        "LABARCHIVES_ENABLE_UPLOAD": "true"
      }
    }
  }
}
```

**Steps**:
1. Replace both `/absolute/path/to/lab_archives_mcp` with your actual repository path
2. Save the config file
3. **Completely restart Windsurf** (Cmd+Q, then reopen)
4. Test by asking: "List my LabArchives notebooks"

### Claude Desktop

**Config file**: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "labarchives": {
      "command": "conda",
      "args": [
        "run",
        "--no-capture-output",
        "-p",
        "/absolute/path/to/lab_archives_mcp/conda_envs/labarchives-mcp-pol",
        "python",
        "-m",
        "labarchives_mcp"
      ],
      "env": {
        "LABARCHIVES_CONFIG_PATH": "/absolute/path/to/lab_archives_mcp/conf/secrets.yml",
        "FASTMCP_SHOW_CLI_BANNER": "false",
        "LABARCHIVES_ENABLE_UPLOAD": "true"
      }
    }
  }
}
```

**Steps**:
1. Replace `/absolute/path/to/lab_archives_mcp` with your repository path
2. Save and restart Claude Desktop
3. The server provides:
   - **Tool**: `list_labarchives_notebooks()` - List all notebooks
   - **Resource**: `labarchives://notebooks` - Read notebooks resource

### Available Tools

**Discovery**:
- **`list_labarchives_notebooks()`** - List all your notebooks
- **`list_notebook_pages(notebook_id)`** - Show table of contents for a notebook

**Reading**:
- **`read_notebook_page(notebook_id, page_id)`** - Read content from a specific page

#### Tool Schemas

**`list_labarchives_notebooks()`**
```python
# Returns list of notebooks:
[{
  "nbid": "MTU2MTI4NS43...",  # Notebook ID
  "name": "Mosquito Navigation",
  "owner": "samuel.brudner@yale.edu",
  "owner_name": "Sam snb6@yale.edu",
  "created_at": "1970-01-01T00:00:00Z",
  "modified_at": "1970-01-01T00:00:00Z"
}]
```

**`list_notebook_pages(notebook_id, folder_id=None)`**
```python
# Returns pages and folders:
[{
  "tree_id": "12345",
  "title": "Introduction",
  "is_page": true,      # Can contain entries
  "is_folder": false
}, {
  "tree_id": "67890",
  "title": "Methods",
  "is_page": false,
  "is_folder": true     # Contains sub-pages - use tree_id as folder_id to navigate
}]

# Navigate into a folder by passing its tree_id as folder_id:
list_notebook_pages(notebook_id, folder_id="67890")
```

**`read_notebook_page(notebook_id, page_id)`**
```python
# Returns page content:
{
  "notebook_id": "MTU2MTI4NS43...",
  "page_id": "12345",
  "entries": [{
    "eid": "e789",
    "part_type": "text_entry",  # or "heading", "plain_text", "attachment"
    "content": "<p>Entry text content...</p>",
    "created_at": "2025-01-01T00:00:00Z",
    "updated_at": "2025-01-02T08:30:00Z"
  }]
}
```

**`upload_to_labarchives(...)`** ⭐ NEW
```python
# Upload a file with code provenance metadata
# MANDATORY parameters:
upload_to_labarchives(
  notebook_id="MTU2MTI4NS43...",
  page_title="Analysis - 2025-09-30",
  file_path="/path/to/analysis.ipynb",
  git_commit_sha="a1b2c3d4...",  # Full 40-char SHA
  git_branch="main",
  git_repo_url="https://github.com/user/repo",
  python_version="3.11.8",
  executed_at="2025-09-30T12:00:00Z",
  dependencies={"numpy": "1.26.0", "pandas": "2.1.0"},
  as_page_text=True  # default: store contents as page text (Markdown → HTML)
)

# Returns:
{
  "page_tree_id": "NEW_PAGE_ID",
  "entry_id": "ENTRY_ID",  # text entry or attachment EID
  "page_url": "https://mynotebook.labarchives.com/...",
  "created_at": "2025-09-30T12:00:00Z",
  "file_size_bytes": 12345,
  "filename": "analysis.ipynb"
}
```

### Library Usage (Python)

```python
import asyncio
from datetime import datetime, UTC
from pathlib import Path

import httpx
from labarchives_mcp.auth import Credentials, AuthenticationManager
from labarchives_mcp.eln_client import LabArchivesClient
from labarchives_mcp.models.upload import UploadRequest, ProvenanceMetadata

async def main():
    creds = Credentials.from_file()  # reads conf/secrets.yml
    async with httpx.AsyncClient(base_url=str(creds.region)) as http_client:
        auth = AuthenticationManager(http_client, creds)
        client = LabArchivesClient(http_client, auth)
        uid = await auth.ensure_uid()

        # A) Render Markdown → HTML as page text (recommended for .md)
        md_req = UploadRequest(
            notebook_id="NBID...",
            page_title="Protocol - 2025-10-02",
            file_path=Path("protocol.md"),
            metadata=ProvenanceMetadata(
                git_commit_sha="a" * 40,
                git_branch="main",
                git_repo_url="https://github.com/user/repo",
                git_is_dirty=False,
                executed_at=datetime.now(UTC),
                python_version="3.11.8",
                dependencies={"numpy": "1.26.0"},
                os_name="Darwin",
                hostname=None,
            ),
            create_as_text=True,
        )
        result = await client.upload_to_labarchives(uid, md_req)
        print("Page:", result.page_url)

        # B) Keep file as attachment (e.g., .ipynb)
        nb_req = UploadRequest(
            notebook_id="NBID...",
            page_title="Analysis - 2025-10-02",
            file_path=Path("analysis.ipynb"),
            metadata=md_req.metadata,
            create_as_text=False,
        )
        result = await client.upload_to_labarchives(uid, nb_req)
        print("Page:", result.page_url)

asyncio.run(main())
```

> **🔒 Security Note**: The upload tool is enabled by default. For production deployments or shared environments, **disable write capabilities** by setting `LABARCHIVES_ENABLE_UPLOAD=false` in the environment configuration above. This prevents AI assistants from unintentionally modifying your research records.

#### Example Agent Workflow

```
User: "What notebooks do I have?"
Agent: calls list_labarchives_notebooks()
→ Shows: Mosquito Navigation, Odor motion PNAS, etc.

User: "What's in my Mosquito Navigation notebook?"
Agent: calls list_notebook_pages("MTU2MTI4NS43...")
→ Shows: Protocols (folder), Sample Log (folder), Experiment Data (folder), etc.

User: "What's in the Protocols folder?"
Agent: calls list_notebook_pages("MTU2MTI4NS43...", folder_id="MS4z...")
→ Shows: Pages and sub-folders inside Protocols

User: "Show me the first page"
Agent: calls read_notebook_page("MTU2MTI4NS43...", "12345")
→ Returns: All text entries, headings, and attachment info from that page
```

---

## Troubleshooting

### "The supplied signature parameter was invalid" (Error 4520)

This means the API signature computation failed. Common causes:
- Wrong `LABARCHIVES_PASSWORD` in secrets file
- Incorrect method name (should omit class prefix, e.g., `user_access_info` not `users:user_access_info`)
- Clock skew between your machine and LabArchives servers

### "404 Not Found" on API endpoints

- Verify `LABARCHIVES_REGION` is correct for your institution
- Confirm with LabArchives support that your access key has the required API methods enabled
- Check that you're using `/api/` paths (not `/apiv1/` or `/api/v1/`)

### Cannot generate or redeem UID

- Ensure you have API access credentials from LabArchives support
- Try the temporary password token method (Option A) first
- If browser-based flow fails with 404, contact LabArchives to enable callback URLs for your key

### MCP Server Won't Start

- Verify `LABARCHIVES_UID` is set in `conf/secrets.yml`
- Run the verification script (step 5 of setup) to test credentials
- Check logs in `logs/` directory for detailed error messages

---

## Usage (Example)

### List notebooks

```json
{
  "resource": "labarchives:notebooks",
  "list": [
    {
      "nbid": "12345",
      "name": "Fly Behavior Study",
      "owner": "samuel.brudner@yale.edu",
      "owner_email": "samuel.brudner@yale.edu",
      "owner_name": "Samuel Brudner",
      "created_at": "2025-01-01T12:00:00Z",
      "modified_at": "2025-01-02T08:30:00Z"
    }
  ]
}

## API Schema

The API contract is defined by **Pydantic models** (single source of truth):
- **Configuration**: `Credentials` in `src/labarchives_mcp/auth.py`
- **Resources**: `NotebookRecord` in `src/labarchives_mcp/eln_client.py`

Generate JSON Schema for API documentation:

```bash
# Notebook resource schema
conda run -p ./conda_envs/labarchives-mcp-pol python -c "
from labarchives_mcp.eln_client import NotebookRecord
import json
print(json.dumps(NotebookRecord.model_json_schema(), indent=2))
"

# Configuration schema
conda run -p ./conda_envs/labarchives-mcp-pol python -c "
from labarchives_mcp.auth import Credentials
import json
print(json.dumps(Credentials.model_json_schema(), indent=2))
"
```

All field descriptions, examples, and validation rules are in the Pydantic models. No separate YAML/JSON schema files—code is the source of truth.

---

## Development Notes

* Fail loud and fast on errors (invalid signature, uid expired, etc.).
* No silent fallbacks—errors must propagate as structured MCP errors.
* Enforce backoff and ≥1s delay between API requests.
* Cache `epoch_time` and `api_base_urls` to reduce load.

---

## Versioning & Release Management

This project follows [**Semantic Versioning**](https://semver.org/) with automated version bumping via [Commitizen](https://commitizen-tools.github.io/commitizen/).

### Commit Message Format

All commits **must** follow the [Conventional Commits](https://www.conventionalcommits.org/) specification. The pre-commit hook enforces this format:

```
<type>[optional scope]: <description>

[optional body]

[optional footer]
```

**Common types**:
- `feat`: New feature (triggers MINOR version bump)
- `fix`: Bug fix (triggers PATCH version bump)
- `docs`: Documentation changes
- `style`: Code style/formatting changes
- `refactor`: Code refactoring without behavior change
- `test`: Adding or updating tests
- `chore`: Build process, tooling, dependencies
- `ci`: CI/CD pipeline changes
- `perf`: Performance improvements
- `BREAKING CHANGE`: (footer or `!` after type) triggers MAJOR version bump

**Examples**:
```bash
git commit -m "feat(auth): add OAuth token refresh"
git commit -m "fix: handle expired UID gracefully"
git commit -m "docs: update API usage examples"
git commit -m "chore(deps): bump pydantic to 2.7.1"
```

### Version Bumping

To create a new release:

```bash
# Dry run (preview changes without committing)
conda run -p ./conda_envs/labarchives-mcp-pol cz bump --dry-run --yes

# Automated version bump (examines commit history)
conda run -p ./conda_envs/labarchives-mcp-pol cz bump --yes        # Auto-detect: patch/minor/major
conda run -p ./conda_envs/labarchives-mcp-pol cz bump --patch      # Force patch: 0.1.0 → 0.1.1
conda run -p ./conda_envs/labarchives-mcp-pol cz bump --minor      # Force minor: 0.1.0 → 0.2.0
conda run -p ./conda_envs/labarchives-mcp-pol cz bump --major      # Force major: 0.1.0 → 1.0.0
```

This will:
1. Analyze commit messages since last tag
2. Determine appropriate version increment
3. Update version in `pyproject.toml`
4. Generate/update `CHANGELOG.md`
5. Create a git commit with the changes
6. Create a git tag `v<version>`

**Push the release**:
```bash
git push && git push --tags
```

### Version Configuration

Version is managed in:
- **Source of truth**: `pyproject.toml` (`version = "0.1.0"`)
- **Commitizen config**: `[tool.commitizen]` section in `pyproject.toml`

The configuration is set to automatically update `CHANGELOG.md` and use `v` prefix for git tags (e.g., `v0.1.0`).

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Development setup instructions
- Code style guidelines
- Testing procedures
- Pull request process

## Citation

If you use this software in your research, please cite:

```bibtex
@software{brudner2025labarchives,
  author = {Brudner, Samuel},
  title = {LabArchives MCP Server: AI Integration for Electronic Lab Notebooks},
  year = {2025},
  url = {https://github.com/SamuelBrudner/lab_archives_mcp},
  version = {0.1.0}
}
```

## License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built on the [Model Context Protocol](https://modelcontextprotocol.io/) by Anthropic
- Uses [FastMCP](https://github.com/jlowin/fastmcp) framework
- LabArchives API documentation and support
