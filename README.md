# LabArchives MCP Server

[![Tests](https://github.com/SamuelBrudner/lab_archives_mcp/workflows/Tests/badge.svg?branch=main)](https://github.com/SamuelBrudner/lab_archives_mcp/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## Overview

A **Model Context Protocol (MCP) server** that connects AI assistants to LabArchives electronic lab notebooks (ELN). This enables researchers to chat with their lab data, search notebooks semantically, and integrate lab work into AI-assisted workflows.

**Key Features:**

- 🧭 **Agent Onboarding**: `onboard()` returns a structured lab overview, sticky context, and usage guidance
- 🔍 **Semantic Search**: Vector-based search across notebook content with enhanced filters
- 📖 **Read Access**: List notebooks, navigate pages, read entries
- 🤖 **AI Integration**: Works with Claude Desktop, Windsurf, and any MCP client
- 🔐 **Secure**: API key authentication with HMAC-SHA512 signing
- 📦 **Reproducible**: Conda-lock environment with pinned dependencies

---

## Documentation

- Quick start: `docs/QUICKSTART.md`
- Agent configuration: `docs/agent_configuration.md`
- Onboarding payload reference: `docs/onboard_example.json`
- Onboarding walkthrough: see `docs/QUICKSTART.md` and `docs/agent_configuration.md`
- Upload API: `docs/upload_api.md`
- Vector backend design and ops: `README_VECTOR_BACKEND.md`

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

- **Language**: Python.

- **Modules**:

  - `auth.py` – credential loading, HMAC signing, UID resolution.
  - `eln_client.py` – notebook navigation, page entry retrieval, upload orchestration.
  - `models/upload.py` – Pydantic contracts for uploads and provenance metadata.
  - `transform.py` – XML→JSON transforms and API fault translation.
  - `mcp_server.py` – MCP server wiring and tool registration.
  - `vector_backend/` – semantic search indexing and Pinecone/Qdrant integrations.

---

## Setup

### 1. Clone and Install

#### Method 1: As a Python module

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

## Requirements & limitations

- **LabArchives account and API access**
  - Full functionality (listing notebooks, reading pages, semantic search, upload with provenance) requires a LabArchives account and API token.
  - The MCP server assumes that authentication has been configured via the documented environment variables and configuration files.

- **Optional external vector stores**
  - The semantic search and embedding layers can use external services such as OpenAI or Pinecone when configured.
  - When these backends are enabled, text content and/or embeddings will be sent to the corresponding provider; institutions should review their data-governance policies before enabling them.

- **On-premise and open backends**
  - The core vector backend and Pydantic models are designed to work without LabArchives and without any commercial vector store.
  - Institutions can plug in a local or on-prem backend (for example, a filesystem or database-backed index) to keep all embeddings and metadata on institutional hardware.

- **Intended usage**
  - `lab_archives_mcp` is designed as an integration layer between ELNs and AI assistants, not as a general-purpose ELN or standalone LIMS.
  - Production deployments should run behind institutional authentication and logging appropriate for research data.

## FAIR & provenance

- **Reproducible environments**
  - Conda-lock files pin Python and dependency versions, enabling deterministic reconstruction of the MCP server environment.
  - Continuous integration runs the test suite against these environments on multiple operating systems.

- **Provenance-aware uploads**
  - The upload tools capture rich code-provenance metadata, including:
    - `git_commit_sha`, `git_branch`, `git_repo_url`, `git_is_dirty`
    - Optional `code_version` tag
    - `executed_at` timestamp
    - `python_version` and key `dependencies`
    - Operating system and (optionally) hostname
  - This metadata is stored alongside the uploaded file in LabArchives, providing a durable link between notebook entries and the code that produced them.

- **Structured schemas**
  - All API payloads and configuration structures are defined using Pydantic models.
  - This ensures explicit, versioned schemas for:
    - LabArchives notebook and page representations
    - Upload requests with provenance
    - Server configuration, including vector backends

- **Data and code versioning**
  - The MCP server is intended to be used in conjunction with Git-based workflows (and optionally DVC or similar tools) so that raw data, processed data, and analysis code can be versioned in tandem with ELN entries.

## For reviewers and editors

- **Code organization and testing**
  - The MCP server is organized into logical modules with clear responsibilities.
  - Unit tests and integration tests cover key functionality, including authentication, notebook navigation, and upload workflows.

- **Security and authentication**
  - The MCP server uses HMAC-SHA512 signing for authentication, with credentials stored securely in environment variables or configuration files.
  - API keys and access tokens are never stored in plaintext or committed to version control.

- **Vector backend and search**
  - The semantic search and embedding layers are designed to be modular and extensible.
  - Institutions can choose to use external vector stores or implement their own on-premise solutions.

## Agent Onboarding Workflow

- From the CLI, run `labarchives-mcp --print-onboard json` (or `markdown`) to capture:
  - Server banner and purpose summary
  - Recommended tool usage (`search_labarchives`, `list_notebook_pages`, `read_notebook_page`)
  - Current lab notebook snapshot and sticky context block to persist in responses
- Persist the returned `sticky_context` in your agent memory before invoking other tools.

### 6. Example: Querying Your Notebooks with AI

Once configured with an AI assistant (Windsurf or Claude Desktop), you can conversationally interact with your lab notebooks:

```CHATBOT
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

For the most up-to-date configuration examples (Claude Desktop, Windsurf, generic MCP clients), see `docs/agent_configuration.md`. The snippets below are included for convenience.

For configuration examples for Windsurf and Claude Desktop (including environment variables and restart steps), see `docs/agent_configuration.md`.

### Available Tools

**Discovery**:

- **`list_labarchives_notebooks()`** - List all your notebooks
- **`list_notebook_pages(notebook_id)`** - Show table of contents for a notebook
- **`search_labarchives(query, limit=5)`** - Semantic search across indexed notebooks

**Reading**:

- **`read_notebook_page(notebook_id, page_id)`** - Read content from a specific page

### Indexing & Sync

- Semantic search operates over content that has already been indexed. Searches do not
  perform indexing implicitly.
- To index or refresh the vector database, use the MCP tool:
  - `sync_vector_index(force=False, dry_run=False, max_age_hours=None, notebook_id=None)`
  - The tool:
    - Loads config from `conf/vector_search/default.yaml`
    - Reads the persisted build record from `incremental_updates.last_indexed_file`
    - Decides one of:
      - `skip` when config + embedding version match and the build is recent
      - `incremental` when the build is older than `max_age_hours` (only changed entries)
      - `rebuild` when embedding version or config fingerprint changed, or `force=True`
    - Use `dry_run=True` to return the plan without any side effects
- Details of the build record and planning are documented in
  `README_VECTOR_BACKEND.md` under “Build Records” and “MCP Sync”.

#### Tool Schemas

**`list_labarchives_notebooks()`**

```json
# Returns list of notebooks:
[{
  "nbid": "MTU2MTI4NS43...",  # Notebook ID
  "name": "Mosquito Navigation",
  "owner": "owner@example.com",
  "owner_name": "Example Owner",
  "created_at": "1970-01-01T00:00:00Z",
  "modified_at": "1970-01-01T00:00:00Z"
}]
```

**`list_notebook_pages(notebook_id, folder_id=None)`**

```json
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

See `docs/upload_api.md` for the complete API documentation and usage notes.

```
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
```json

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
```python

> **🔒 Security Note**: The upload tool is enabled by default. For production deployments or shared environments, **disable write capabilities** by setting `LABARCHIVES_ENABLE_UPLOAD=false` in the environment configuration above. This prevents AI assistants from unintentionally modifying your research records.

#### Example Agent Workflow

```Chat
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
```text

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
- Inspect stderr output for Loguru messages, or configure a Loguru file sink if you need persistent logs

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
      "owner": "owner@example.com",
      "owner_email": "owner@example.com",
      "owner_name": "Example Owner",
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

- Fail loud and fast on errors (invalid signature, uid expired, etc.).
- No silent fallbacks—errors must propagate as structured MCP errors.
- Core LabArchives requests run directly through `httpx.AsyncClient`; add external throttling if your deployment demands rate limits beyond the platform defaults.
- The MCP server does not currently cache `epoch_time` or `api_base_urls`; extend `AuthenticationManager` if you need those optimisations.

---

## Versioning & Release Management

See `CONTRIBUTING.md` for versioning, Conventional Commits, and release steps.

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
  version = {0.2.4}
}
```

## License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built on the [Model Context Protocol](https://modelcontextprotocol.io/) by Anthropic
- Uses [FastMCP](https://github.com/jlowin/fastmcp) framework
- LabArchives API documentation and support
