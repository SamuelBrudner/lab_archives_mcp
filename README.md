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
2. Copy the secrets template and fill in LabArchives credentials:

   ```bash
   cp conf/secrets.example.yml conf/secrets.yml
   $EDITOR conf/secrets.yml
   ```

   Required keys:

   - `LABARCHIVES_AKID`
   - `LABARCHIVES_PASSWORD`
   - `LABARCHIVES_REGION` (e.g., `https://api.labarchives.com`)

   Optional helpers for non-interactive workflows:

   - `LABARCHIVES_UID`: reuse a known uid instead of re-authenticating.
   - `LABARCHIVES_AUTH_EMAIL` + `LABARCHIVES_AUTH_CODE`: supply the email and temporary token returned from LabArchives so the PoL client can call `users:user_access_info` and resolve the uid automatically.

   If none of the optional values are provided, the MCP server will raise an error prompting you to obtain either a uid or temporary token. See **Authentication workflow** below for details.
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

   The configured hooks automatically strip notebook outputs (via `nbstripout`) and
   format `.ipynb` diffs using `nbdime`, keeping commits reviewable even as notebooks evolve.
6. Run the MCP server (stub implementation for now):

   python -m labarchives_mcp.mcp_server
   ```

---

## Authentication workflow

- **Obtain a uid once**: follow the LabArchives `api_user_login` flow in a browser, then call `users:user_access_info` (or request a temporary token from LabArchives support). Record the uid in `conf/secrets.yml` as `LABARCHIVES_UID` for subsequent runs.
- **Or use temporary tokens**: populate `LABARCHIVES_AUTH_EMAIL` and `LABARCHIVES_AUTH_CODE`. On start-up the PoL server exchanges the token via `users:user_access_info` and caches the resulting uid. Tokens are short-lived; replace them when LabArchives issues a new value.
- **Signature details**: every API call includes an HMAC-SHA512 signature over `<akid> + <method> + <expires>` using millisecond precision and UTC. Clock drift should be mitigated by calling the LabArchives `epoch_time` utility before long sessions.
- **Rate limiting**: respect LabArchives guidance—pause ≥1 s between calls and back off on errors (`tenacity` handles this when we wire up retry policies in future work).

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
