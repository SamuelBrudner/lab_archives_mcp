# LabArchives Upload API Documentation

## Overview

The upload functionality enables programmatic creation of notebook pages and uploading of files to LabArchives. This supports automated workflows for:

- Archiving analysis notebooks (`.ipynb`)
- Documenting code (`.py`, `.R`)
- Storing markdown documentation (`.md`)
- Uploading data files and results

## Architecture

```text
┌─────────────────────────────────────┐
│   MCP Tool: upload_to_labarchives   │
│   - Validates inputs                │
│   - Orchestrates page creation      │
│   - Stores page text (Markdown → HTML) or uploads attachment │
└──────────────┬──────────────────────┘
               │
               ↓
┌─────────────────────────────────────┐
│  LabArchivesClient                  │
│  - insert_node()                    │
│  - add_attachment()                 │
│  - add_entry()                      │
└──────────────┬──────────────────────┘
               │
               ↓
┌─────────────────────────────────────┐
│  LabArchives REST API               │
│  POST /tree_tools/insert_node       │
│  POST /entries/add_attachment       │
│  POST /entries/add_entry            │
## Use Cases

### UC1: Upload Analysis Notebook
**Actor**: Data Analyst
**Goal**: Archive a Jupyter notebook with analysis results
**Preconditions**:
- User has write access to notebook
- File exists on filesystem
- File size ≤ max upload limit
- **Git repository is clean or metadata is explicitly provided**

**Flow**:
1. User specifies notebook ID and target folder
2. **Tool extracts code provenance metadata** (Git SHA, branch, repo URL)
3. Tool creates new page with descriptive title
4. Tool uploads `.ipynb` file as attachment
5. **Tool adds text entry with structured metadata** (commit SHA, versions, execution time)
6. Tool returns page URL and entry ID

**Postconditions**:
- New page exists in notebook
- File is accessible via LabArchives web UI
- **Metadata entry documents code version and execution context**
- Audit trail records upload event with full provenance

### UC2: Sync Markdown Documentation
**Actor**: Software Developer
**Goal**: Keep protocol documentation synchronized with Git repo
**Preconditions**: Same as UC1

**Flow**:
1. CI/CD pipeline triggers on commit
2. Tool uploads `protocol.md` to "Protocols" folder
3. Tool converts Markdown to HTML and stores it as a text entry by default
4. Tool returns entry ID for tracking

**Postconditions**:
- Markdown rendered and stored as page text (HTML)
- Optional: Also attach original file if desired

### UC3: Archive Python Scripts
**Actor**: Researcher
**Goal**: Document analysis code alongside results
**Preconditions**: Same as UC1

**Flow**:
1. User uploads `.py` script after running analysis
2. Tool creates page titled with script name + date
3. Tool uploads script as attachment
4. Optional: Add text entry with execution summary

**Postconditions**:
- Script archived for reproducibility
- Associated with experiment data

## API Endpoints

### 1. `insert_node`
Creates a new page or folder in the notebook hierarchy.

**Method**: POST
**Endpoint**: `/api/tree_tools/insert_node`

**Parameters**:
- `uid` (required): User ID
- `nbid` (required): Notebook ID
- `parent_tree_id` (required): Parent folder tree_id, or "0" for root
- `display_text` (required): Page/folder title
- `is_folder` (required): "true" for folder, "false" for page
- `akid`, `expires`, `sig`: HMAC authentication

**Response**:
```xml
<tree-tools>
  <node>
    <tree-id>BASE64_ENCODED_ID</tree-id>
    <display-text>My Analysis Page</display-text>
    <is-page type="boolean">true</is-page>
  </node>
</tree-tools>
```

**Returns**:
- `tree_id`: New page/folder identifier (used as `pid` for uploads)

### 2. `add_attachment`
Uploads a file to a notebook page.

**Method**: POST
**Endpoint**: `/api/entries/add_attachment`
**Content-Type**: `application/octet-stream`

**Parameters**:
- `uid` (required): User ID
- `nbid` (required): Notebook ID
- `pid` (required): Page tree_id (from insert_node)
- `filename` (required): Original filename with extension
- `caption` (optional): Display caption
- `change_description` (optional): Audit log message
- `client_ip` (optional): Client IP for audit
- `akid`, `expires`, `sig`: HMAC authentication

**Request Body**: Binary file content

**Response**:
```xml
<entries>
  <entry>
    <eid>ENTRY_ID</eid>
    <part-type>attachment</part-type>
    <filename>analysis.ipynb</filename>
    <caption>Analysis results for experiment 123</caption>
    <created-at>2025-09-30T12:00:00Z</created-at>
  </entry>
</entries>
```

### 3. `add_entry` (Optional)
Adds text content to a page.

**Method**: POST
**Endpoint**: `/api/entries/add_entry`

**Parameters**:
- `uid` (required): User ID
- `nbid` (required): Notebook ID
- `pid` (required): Page tree_id
- `part_type` (required): "text entry", "plain text entry", or "heading"
- `entry_data` (required): Content (HTML or UTF-8 text)
- `caption` (optional): Display caption
- `change_description` (optional): Audit log message
- `akid`, `expires`, `sig`: HMAC authentication

**Response**: Similar to add_attachment

## Code Provenance & Metadata (MANDATORY)

All uploads of code, notebooks, or figures **MUST** include provenance metadata to ensure reproducibility and comply with FAIR data principles.

### Required Metadata Fields

```python
class ProvenanceMetadata(BaseModel):
    """Code execution and environment metadata (MANDATORY for notebooks/figures)."""

    # Git provenance
    git_commit_sha: str  # Full 40-char SHA
    git_branch: str  # e.g., "main", "analysis-2025-09"
    git_repo_url: str  # e.g., "https://github.com/user/repo"
    git_is_dirty: bool  # True if uncommitted changes exist

    # Code version
    code_version: str | None  # Git tag or semantic version

    # Execution context
    executed_at: datetime  # When code was run
    python_version: str  # e.g., "3.11.8"

    # Key dependencies (for notebooks)
    dependencies: dict[str, str]  # {"numpy": "1.26.0", "pandas": "2.1.0"}

    # System info
    os_name: str  # e.g., "Darwin", "Linux"
    hostname: str | None  # Execution machine
```

### Metadata Capture Strategy

1. **Automatic extraction** from Git repository
2. **Fail-fast validation**: Refuse upload if Git is dirty (unless override flag set)
3. **Structured storage**: Metadata added as plain-text entry on page
4. **Human-readable format**: Markdown table for easy viewing

### Example Metadata Entry

```markdown
## Code Provenance

**Git Information**
- Commit: `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0`
- Branch: `analysis-temporal-integration`
- Repository: https://github.com/SamuelBrudner/temporal-integration-analysis
- Status: ✅ Clean (no uncommitted changes)

**Execution Context**
- Executed: 2025-09-30 12:19:03 UTC
- Python: 3.11.8
- Key Packages: numpy==1.26.0, pandas==2.1.0, matplotlib==3.8.0

**System**
- OS: Darwin (macOS)
- Hostname: sam-macbook-pro.local
```

## Data Contracts

### UploadRequest
```python
class UploadRequest(BaseModel):
    notebook_id: str  # nbid
    parent_folder_id: str | None  # tree_id or None for root
    page_title: str  # display_text for new page
    file_path: Path  # Local file to upload
    caption: str | None = None
    change_description: str | None = None

    # MANDATORY for .ipynb, .py, figures
    metadata: ProvenanceMetadata | None = None

    # Allow upload despite dirty Git state (use with caution)
    allow_dirty_git: bool = False

    # Store file contents as page text (Markdown → HTML for .md)
    create_as_text: bool = False
```

### UploadResponse
```python
class UploadResponse(BaseModel):
    page_tree_id: str  # tree_id of created page
    entry_id: str  # EID of text entry or attachment
    page_url: str  # LabArchives web URL
    created_at: datetime
    file_size_bytes: int
```

## Library Usage Example

```python
import asyncio
from pathlib import Path
from datetime import datetime, UTC

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

        # Example A: Upload Markdown as page text (rendered to HTML)
        md_request = UploadRequest(
            notebook_id="NBID...",
            parent_folder_id=None,
            page_title="Protocol - 2025-10-02",
            file_path=Path("protocol.md"),
            metadata=ProvenanceMetadata(
                git_commit_sha="a"*40,
                git_branch="main",
                git_repo_url="https://github.com/user/repo",
                git_is_dirty=False,
                executed_at=datetime.now(UTC),
                python_version="3.11.8",
                dependencies={"numpy": "1.26.0"},
                os_name="Darwin",
                hostname=None,
            ),
            create_as_text=True,  # Render Markdown → HTML on the page
        )
        result = await client.upload_to_labarchives(uid, md_request)
        print("Page:", result.page_url)

        # Example B: Upload notebook as attachment
        nb_request = UploadRequest(
            notebook_id="NBID...",
            page_title="Analysis - 2025-10-02",
            file_path=Path("analysis.ipynb"),
            metadata=md_request.metadata,
            create_as_text=False,  # Keep as attachment
        )
        result = await client.upload_to_labarchives(uid, nb_request)
        print("Page:", result.page_url)

asyncio.run(main())
```

### PageCreationResult
```python
class PageCreationResult(BaseModel):
    tree_id: str
    display_text: str
    is_page: bool
```

### AttachmentUploadResult
```python
class AttachmentUploadResult(BaseModel):
    eid: str
    part_type: Literal["attachment"]
    filename: str
    caption: str | None
    created_at: datetime
```

## Error Handling

### Validation Errors
- `FileNotFoundError`: file_path does not exist
- `ValueError`: file_size exceeds limit
- `PermissionError`: no write access to notebook

### API Errors
- `400 Bad Request`: Invalid parameters
- `403 Forbidden`: Insufficient permissions
- `413 Payload Too Large`: File exceeds upload limit
- `500 Internal Server Error`: LabArchives service error

## Configuration

### File Size Limits
- Default: Check via `users/max_upload_size` API
- Fallback: 100 MB
- Validation: Fail fast if file exceeds limit

### Supported File Types
- Notebooks: `.ipynb`
- Code: `.py`, `.R`, `.jl`, `.m`
- Documentation: `.md`, `.txt`, `.rst`
- Data: `.csv`, `.parquet`, `.h5`, `.npz`
- Binary: Any file type (uploaded as-is)

### Page Title Generation
- User-provided: Use as-is
- Auto-generated: `{filename} - {YYYY-MM-DD HH:MM}`
- Sanitization: Remove/escape invalid XML characters

## Security Considerations

1. **Authentication**: All requests use HMAC-SHA512 signatures
2. **Authorization**: Verify write access before upload
3. **Input Validation**:
   - Sanitize filenames (prevent path traversal)
   - Validate file extensions
   - Check file sizes
4. **Audit Trail**: Include `change_description` for provenance
5. **Rate Limiting**: Respect LabArchives API limits

## Testing Strategy

### Specification Tests
- Page creation with valid parameters
- File upload with various types
- Error handling for missing files
- Permission validation

### Unit Tests
- Mock HTTP client responses
- Test HMAC signature generation
- Validate Pydantic models
- Test file reading and streaming

### Integration Tests
- Create page in test notebook
- Upload small test file
- Verify via read API
- Clean up test data

## Future Enhancements

1. **Batch Upload**: Upload multiple files to one page
2. **Markdown Rendering**: Convert `.md` to HTML entry
3. **Notebook Rendering**: Extract cells from `.ipynb` as entries
4. **Version Control**: Link to Git commit SHA
5. **Metadata Extraction**: Parse frontmatter from markdown
6. **Progress Reporting**: Callback for upload progress
7. **Retry Logic**: Exponential backoff for transient failures
