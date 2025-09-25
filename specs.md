# LabArchives MCP Server – Proof of Life (PoL) Spec

## 🎯 Purpose

Expose LabArchives ELN API as an MCP server, enabling agents to:

* Authenticate and sign API requests transparently.
* Retrieve a list of notebooks for a user in normalized JSON.

This is **not** a full API wrapper. It is a **minimal, verifiable PoL** implementation.

---

## ✅ In Scope (PoL)

### Authentication

* Handle API key signing (`akid`, `expires`, `sig`).
* Support user login flow to resolve `uid` (temporary password tokens accepted).
* Cache/refresh `uid` transparently.

### Resource Exposure (Minimal Set)

* **Notebooks**

  * `list_notebooks(uid)` → return notebooks for authenticated user.

### Transport Normalization

* Convert LabArchives XML responses into JSON before returning to MCP clients.
* Map LabArchives error codes (4500–4999) into MCP error schema.

### Server Implementation

* **Language**: Python.
* **Modules**:

  * `auth.py` (akid, sig signing, OAuth flow, uid cache).
  * `eln_client.py` (wraps only notebook listing).
  * `transform.py` (XML→JSON, error mapping).
  * `mcp_server.py` (MCP protocol loop).

### Security / Best Practices

* Never embed static API credentials; load from env/config.
* Rate limit outgoing requests (≥1s spacing, exponential backoff on retries).
* Cache results where possible (epoch_time, base_urls).

---

## 🚫 Out of Scope (PoL)

* All other ELN calls (entries, tree traversal, search, metadata).
* Write operations (add/update entry, attachments, notebooks, ownership transfer).
* Binary attachment streaming (downloads, thumbnails, snapshots).
* Scheduler API.
* Notifications.
* Site license tools / admin APIs.
* Rich rendering (MathML, sketch JSON, container manifests).

---

## 📦 Example MCP Resource Exposure

**Notebook List**

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

## 🔄 Example Request/Response Flow

### 1. MCP Client → MCP Server

```json
{
  "action": "list_notebooks",
  "params": {
    "user": "samuel.brudner@yale.edu"
  }
}
```

### 2. MCP Server → LabArchives API (HTTP Request)

```
GET https://api.labarchives.com/apiv1/notebooks/list?akid=XXXX&expires=1700000000000&sig=YYYY&uid=ZZZZ
```

* **akid**: Access Key ID.
* **expires**: Epoch ms (± 2 min window).
* **sig**: HMAC-SHA-512 of `akid + method + expires`, signed with access password.
* **uid**: User identifier resolved via login/auth flow.

### 3. LabArchives API → MCP Server (XML Response)

```xml
<notebooks>
  <response>
    <method>list</method>
    <uid>ZZZZ</uid>
  </response>
  <notebook>
    <nbid>12345</nbid>
    <name>Fly Behavior Study</name>
    <owner>samuel.brudner@yale.edu</owner>
    <created-at>2025-01-01T12:00:00Z</created-at>
  </notebook>
</notebooks>
```

### 4. MCP Server → MCP Client (Normalized JSON)

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

## 🔜 Next Steps

1. Implement XML→JSON normalizer for `<notebook>` list.
2. Implement auth signing + uid login helper.
3. Stand up MCP server exposing only `list_notebooks`.
4. Verify PoL by listing notebooks via MCP round-trip.
5. Log all requests/responses for debugging.

---

## 📌 Notes

* Fail **loud and fast**: if auth/signature errors occur, return structured MCP error immediately.
* **No fallback behavior**: avoid masking LabArchives failures.
* Aim: verifiable notebook listing via MCP round-trip.
