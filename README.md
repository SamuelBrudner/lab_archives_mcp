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

1. Clone this repo.
2. Set environment variables:

   ```bash
   export LABARCHIVES_AKID=... 
   export LABARCHIVES_PASSWORD=...
   export LABARCHIVES_REGION=https://api.labarchives.com
   ```
3. Create the pinned Conda environment (local prefix):

   ```bash
   conda-lock install --prefix ./conda_envs/pol-dev conda-lock.yml
   ```
4. Activate the environment:

   ```bash
   conda activate ./conda_envs/pol-dev
   ```
5. Install git hooks and tooling:

   ```bash
   pre-commit install
   ```
6. Run the MCP server (stub implementation for now):

   ```bash
   python -m labarchives_mcp.mcp_server
   ```

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
      "created_at": "2025-01-01T12:00:00Z"
    }
  ]
}
```

---

## Development Notes

* Fail loud and fast on errors (invalid signature, uid expired, etc.).
* No silent fallbacks—errors must propagate as structured MCP errors.
* Enforce backoff and ≥1s delay between API requests.
* Cache `epoch_time` and `api_base_urls` to reduce load.

---

## Next Steps

* Implement XML→JSON parser for notebook list.
* Implement `list_notebooks` endpoint.
* Verify round-trip with real LabArchives instance.
* Add logging of requests/responses for debugging.
