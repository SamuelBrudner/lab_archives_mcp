# LabArchives MCP Server – Proof of Life (PoL) README

## Overview

This repository implements a **minimal MCP server** for LabArchives ELN, providing read-only access to notebooks. It wraps the LabArchives ELN API (XML) and exposes normalized JSON responses to MCP clients.

The purpose is to verify end-to-end connectivity, authentication, and data retrieval from LabArchives via the MCP protocol. **This is not a full wrapper**—it demonstrates a proof-of-life only.

---

## Features (In Scope)

* **Authentication**

  * API key signing (`akid`, `expires`, `sig`).
  * User login flow to obtain and cache `uid`.
* **Read-only resources**

  * List notebooks for a user.
* **Transport normalization**

  * XML → JSON for ELN notebooks.
  * Error code mapping (4500–4999) → MCP error schema.

---

## Out of Scope

* All other read operations (entries, tree traversal, search, metadata).
* Write operations (add/update entry, attachments, create notebooks, ownership transfer).
* Binary streaming (attachments, thumbnails, snapshots).
* Scheduler API.
* Notifications API.
* Site license / admin tools.
* Rich rendering (MathML, sketch JSON, proprietary container files).

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
conda-lock install --prefix ./conda_envs/pol-dev conda-lock.yml
```

Activate it:

```bash
conda activate ./conda_envs/pol-dev
```

Install git hooks and tooling:

```bash
pre-commit install
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
   conda run -p ./conda_envs/pol-dev python scripts/resolve_uid.py redeem \
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
   conda run -p ./conda_envs/pol-dev python scripts/resolve_uid.py login-url
   ```

2. Open the URL in your browser and complete the LabArchives sign-in
3. After redirect, extract the `auth_code` from the URL
4. Run the redeem command (same as Option A step 5)

**Note**: The UID is permanent for your account—once obtained, store it in `conf/secrets.yml` and you won't need to retrieve it again unless your LabArchives password changes.

### 5. Verify Setup

Test that everything works:

```bash
conda run -p ./conda_envs/pol-dev python -c "
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

### 6. Run the MCP Server

```bash
conda run -p ./conda_envs/pol-dev python -m labarchives_mcp.mcp_server
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
conda run -p ./conda_envs/pol-dev python -c "
from labarchives_mcp.eln_client import NotebookRecord
import json
print(json.dumps(NotebookRecord.model_json_schema(), indent=2))
"

# Configuration schema
conda run -p ./conda_envs/pol-dev python -c "
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

## Implementation Status

✅ **Completed**
- XML→JSON parser for notebook list
- `list_notebooks` endpoint via `user_info_via_id`
- Full authentication flow with UID resolution
- Request signing (HMAC-SHA512)
- Integration tests (7/7 passing)
- Verified with live LabArchives API

🚧 **Future Enhancements**
- Additional read operations (entries, tree traversal, search)
- Write operations (add/update entry, notebooks)
- Binary streaming (attachments, thumbnails)
- Rate limiting and retry policies
- Comprehensive error handling for all API error codes
