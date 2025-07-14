# LabArchives MCP Server – MVP Product Requirements Document

## Executive Summary

The LabArchives MCP Server is a command-line tool (CLI) that enables Large Language Models (LLMs) to securely access content from LabArchives electronic lab notebooks via the new **Model Context Protocol (MCP)**. MCP is an open standard by Anthropic that provides a universal way to connect AI assistants to external data sources. This MVP (Minimum Viable Product) focuses on a **read-only** integration: it will fetch LabArchives notebook data (notebooks, pages, entries and metadata) through LabArchives’ REST API, and expose that data as structured context to AI applications like Claude Desktop (Anthropic’s MCP-enabled LLM client). By adhering to MCP, the server can plug into Claude Desktop or any future MCP-compatible host out-of-the-box.

This document outlines the requirements for the MVP implementation, which is intended to be developed and deployed within one week by a small lab team or developer. The solution will be **open-source** (permissive license) and easy to run, ensuring researchers can reproducibly integrate their LabArchives data with LLM tools in a controlled, secure manner. Key features include CLI-based configuration, LabArchives API authentication (via Access Key ID and token), JSON/JSON-LD structured output preserving notebook hierarchy, context scope limitation, and comprehensive logging for traceability. Future enhancements (beyond MVP) are also noted, such as a safe write-back mode and version history access, to guide the roadmap.

## Goals and Success Criteria

**Goals:**

- **Seamless LLM Integration with LabArchives:** Enable LLM applications to retrieve LabArchives notebook content as context, bridging the gap between “isolated” AI and real lab data. The tool should follow the MCP standard so that connecting to Claude Desktop (or similar clients) is straightforward.
- **Fast Deployment and Ease of Use:** Deliver a solution that can be set up within one week. A single developer or small lab team should be able to install and configure the MCP server with minimal effort, using familiar tools (Python CLI, Docker, etc.). Clear documentation and simple CLI options will facilitate quick adoption.
- **Read-Only, Secure Access:** Focus on read-only operations to ensure no unintended modifications to notebook data. This addresses immediate user needs (context retrieval for LLM queries) while minimizing risk. All access should respect user permissions and require explicit user consent on the LLM side before an AI can use the data.
- **Open-Source & Extensible:** Release the MVP as open-source (e.g. MIT-licensed) to encourage community contributions and transparency. Success includes having a clean, modular codebase that others can review, audit, and extend (for example, adding new features like write-back or supporting other LLM hosts in the future).
- **Flexibility Across LLM Hosts:** Though Claude Desktop is the initial target, the MCP server should not be hardcoded to Claude. By conforming strictly to the MCP spec, it can work with *any* MCP-compliant client. A goal is that switching to a different LLM (OpenAI’s or others) that supports MCP would require no changes in the server.
- **Traceability and Compliance:** Ensure every piece of LabArchives data provided to the LLM is tracked. Logging of API calls and resource accesses is crucial for compliance and auditing. Users (or IT admins) should be able to review logs to see what was retrieved and when, which is important in regulated lab environments.

**Success Criteria:**

- **MCP Connectivity:** The server successfully registers with an MCP host (e.g. appears as a tool/integration in Claude Desktop) and responds to MCP requests. For instance, a user in Claude Desktop can list available LabArchives notebooks and retrieve a page’s content via this server without errors. All required MCP message types (e.g. `resources/list` and `resources/read`) are implemented correctly.

- **Data Retrieval Functionality:** Using the MCP server, a user can fetch real data from LabArchives:

  - *Listing:* The server provides a list of notebooks (or pages within a notebook, depending on scope) in a structured format when prompted.
  - *Content:* Given a specific notebook/page/entry selection, the server returns the content and metadata (e.g. an experiment entry’s text, the date it was created, etc.) as JSON. The structure should reflect LabArchives’ hierarchy (notebook → folder → page → entries).
  - *Accuracy:* The content and metadata must match what is in LabArchives, confirming the server’s API calls are correct.

- **Authentication & Security:** The server can authenticate to LabArchives using provided credentials (Access Key ID and token/external password) and maintain an authorized session. Success includes handling token expiry gracefully: if using a short-lived token, the server detects expiration and prompts for renewal or returns a clear error without crashing. Credentials are **not** exposed in logs or error messages.

- **Context Scoping:** When launched with a scope restriction (e.g. only a specific notebook), the server limits resource listing and access to that scope. A test would be to configure the server for a single notebook and verify that attempting to access another notebook’s ID is either not listed or returns an access denied. This demonstrates enforcement of the context scope setting.

- **Logging & Traceability:** All interactions are logged with sufficient detail. Success means that after a session, the user can inspect a log file (or console output) and see: which LabArchives API endpoints were called, which notebook/page/entry IDs were accessed, timestamps, and any errors. No sensitive content should be logged beyond what’s necessary (e.g. maybe log “Page 123 fetched” but not the full page content in plaintext, unless in debug mode). Additionally, the MCP server should identify itself (with a version) in logs and maybe to the user, for traceability.

- **Performance & Stability:** The server should handle typical notebook sizes without timing out or crashing. A success benchmark might be fetching a page with \~100 entries in under a few seconds (assuming network latency to LabArchives is normal). Memory usage should remain reasonable (streaming or paging large data if needed). The server must run steadily during a multi-hour Claude session without memory leaks or deadlocks.

- **User Acceptance:** Finally, success is measured by a small lab team being able to **use** the tool in practice. This means the documentation is clear (they know how to input their credentials and start the server), and the integration actually helps them (e.g. Claude can answer a question that requires looking at their LabArchives notes). Positive feedback from an initial user (like “I asked Claude to summarize yesterday’s experiment, and it pulled the protocol from LabArchives successfully”) would validate the product.

## Functional Requirements

- **Open-Source CLI Tool:** The product shall be delivered as an open-source command-line application. It must be runnable on the command line (e.g. `labarchives-mcp-server` command) without a graphical interface. All configuration will be via CLI arguments, environment variables, or config files – suitable for developers and advanced users. The source code will be published (e.g. on GitHub) under a permissive license for community use and contributions.

- **MCP Protocol Compliance:** The server must implement the Model Context Protocol according to the official specification. This includes supporting the necessary MCP **server features** for exposing data as “resources.” At minimum, the MVP will implement:

  - `resources/list` – to list available LabArchives resources (e.g. notebooks or pages) that can be provided as context.
  - `resources/read` – to retrieve the content of a specified resource (e.g. the contents of a given page or entry).
    It should register a unique server name/ID and declare its capabilities during the MCP handshake. The implementation should be compatible with Anthropic’s Claude Desktop out-of-the-box, meaning Claude can launch and communicate with it. (By using the standard MCP SDK and JSON-RPC transport, compatibility with Claude and other hosts is ensured.)

- **Read-Only Data Access:** The MCP server will provide **read-only** access to LabArchives notebooks. It shall never modify or delete notebook content through the API in MVP. Specifically, it will support:

  - **Listing Notebooks/Pages:** The ability to fetch a list of the user’s notebooks, and within a given notebook, list its folders and pages (to navigate the hierarchy). This may be presented as a tree or as separate listing commands (e.g. list notebooks first, then list pages in a chosen notebook).
  - **Retrieving Page Content:** Given a specific page identifier, retrieve all entries on that page. Each entry’s content (e.g. text, attachments) and metadata (entry title, entry type, timestamp of last edit, creator name, etc.) should be fetched. For textual entries, the full text should be returned. For attachments or non-text entries, metadata (filename, file type) should be returned, and if feasible, a link or indication of how to download the file (the actual binary may be skipped or represented in base64 if small). *Note:* Sketches or specialized entry types that LabArchives returns in JSON format will be passed through as-is or simplified, as MVP focuses on core entry types.
  - **Metadata Retrieval:** Retrieve basic metadata about notebooks and pages: e.g. notebook name, description, page title, the hierarchy (folder path), and last modified times. This allows the LLM to provide context like “Notebook X &gt; Protocols Folder &gt; Page Y (last edited 2023-10-01) contains the procedure details.”
    All data retrieval will be done via the LabArchives public API endpoints. The design assumes that any content accessible via the LabArchives web interface (for the authenticated user) should be accessible via the API, and thus via this tool.

- **LabArchives API Authentication:** The tool will authenticate to LabArchives using valid API credentials. It must support two authentication modes:

  1. **API Access Key & Secret:** LabArchives issues an Access Key ID (`akid`) and a corresponding secret key (or password) to approved third parties or integrations. If the user has such credentials, the server should accept them (e.g. via `--access-key` and `--access-secret` flags or env vars). These are typically long-lived credentials tied to an integration.
  2. **External App Password (User Token):** For users without a dedicated API key (especially those using Single Sign-On to log in), the server should allow using a temporary **personal access token**. LabArchives lets users generate an “LA App Authentication” password token (often valid for \~1 hour) for external applications. The server should accept this token (likely in place of the secret key) along with the user’s email/username if needed. It will then perform the necessary API calls to exchange it for a session or user ID. For example, the server might call the `users/user_access_info` API method with the login email and token to obtain the user’s UID, which is required for subsequent data calls.
     The CLI should provide a clear way to input these credentials (command options or prompting securely). The credentials must be stored in-memory only and used for API calls; do not write them to disk. If the token expires during use, the server should detect an authentication failure from the API and notify the user (e.g. through an error in the LLM client or a log message) that re-authentication is needed. (Automatic re-login could be a future feature; MVP can require restarting with new token.)

- **Structured JSON/JSON-LD Output:** All resource data returned by the MCP server should be structured, machine-readable, and preserve the context needed by the AI. JSON will be the primary format for responses:

  - When listing resources (notebooks/pages), return a JSON list of items with fields like `id`, `name`, `description` (if available). For hierarchical data, the server can either nest the structure or use separate list calls for each level. For MVP simplicity, it may present a flat list at the scope level (e.g. list pages of one notebook if scope is one notebook; or list notebooks if scope is all notebooks).
  - When reading a resource (page or entry), return the content in JSON form. If multiple entries are being returned (e.g. a whole page’s entries), the response can be a JSON object representing the page with an array of entries. Each entry object contains its fields (text, type, metadata). Binary data (if included at all) should be base64 encoded as per MCP binary resource guidelines, though for MVP we might choose to exclude large blobs and only indicate their presence.
  - **Preserving Hierarchy:** The data should include context of where it came from. For example, a page’s JSON could include the notebook name and folder path, or at least identifiers, so that an AI response can mention those if needed. This mirrors LabArchives’ internal hierarchy (we can include a “path” field or provide separate resource URIs for each level).
  - **JSON-LD (Semantic Layer):** Where appropriate, the server might augment the JSON with a JSON-LD context to define terms like “Notebook”, “Page”, “Entry” in a vocabulary. This can help AI interpret the data unambiguously. For MVP, JSON-LD is optional; if implemented, it could be a small `@context` block in the JSON responses linking to a schema (for example, a custom or existing ontology for notebooks). The primary goal is that the output is **structured**; an AI client (or the user) should not have to parse unstructured text to get the data fields.

- **Configurable Context Scope:** The MCP server must allow the user to restrict the available data context to a subset of their LabArchives content. This scoping could be configured at launch, so that only certain notebooks or folders are exposed to the AI:

  - The simplest implementation is a `--notebook-id` (or `--notebook-name`) option when starting the server, to limit all operations to that single notebook. In this mode, the server would only list pages/folders from that notebook (and no other notebooks). Attempts by the client to access a resource outside this notebook would be refused or simply not listed.
  - Optionally, we could allow scoping to a folder within a notebook (e.g. by an identifier or path). This further restricts context to, say, one project’s folder.
  - If no scope is specified, the default is that all notebooks accessible by the credentials are exposed. In any case, scope limitations should be *clearly enforced* in the code to avoid accidental leakage of other data. This feature is important for controlled usage in multi-project environments.
  - The server’s resource URIs and listings should reflect the scope. For example, if scoped to notebook “Lab Book A”, the root resources listed might be the pages or top folders of that notebook (rather than listing all notebook names). We will document this behavior for the user’s understanding.

- **Logging and Audit Trail:** Comprehensive logging is a required feature for transparency. The server will log:

  - **Startup and Config:** When it starts, log the configuration (e.g. “Scope: Notebook 123 (Name XYZ)”, “JSON-LD output: enabled”, “Connecting to [api.labarchives.com](http://api.labarchives.com)”). This gives context in the log file.
  - **MCP Requests:** Log each high-level MCP request received from the client (e.g. “resources/list called by client”, “resources/read called for resource URI labarchives://notebook123/page456”). This can be at an INFO level.
  - **LabArchives API Calls:** For each API call the server makes to LabArchives, log the endpoint and parameters (at least at DEBUG level). For example: “GET /api/notebooks/list?uid=... (success)” or “GET /api/pages/getEntries?pageid=...”. If the API returns an error or slow response, log that as well (including HTTP status codes or error messages).
  - **Data Returned:** We do not log full data by default (to avoid sensitive info in logs), but we do log summary info – e.g. “Returned Page 456 with 10 entries (total size 24KB) to client.” This indicates what was sent to the LLM.
  - **Errors/Exceptions:** Any exceptions or unexpected conditions (like parse errors, missing notebook ID, permission denied from API) should be logged as warnings or errors. The server should handle these gracefully (perhaps returning an error message resource to the client) but still record them.
  - **Traceability:** Each log entry should have a timestamp. Consider including a session or request ID if multiple requests are processed concurrently (though likely sequential in MVP). This log will allow a post-hoc analysis of exactly what information was accessed by the AI, addressing any data compliance concerns.
  - **Storage and Access:** Logs can be written to a file (`labarchives_mcp.log`) in the working directory or a specified location. The CLI might allow a `--log` filepath option. If no file is specified, printing to stderr/stdout is acceptable for simplicity, as the user can redirect it. The log format should be simple text, and we’ll document that sensitive tokens are not recorded.
  - *Privacy consideration:* Because LabArchives data can be sensitive, the logs themselves are sensitive. We will note that logs should be handled accordingly, or provide an option to disable detailed logging if desired by the user.

- **Consent & Safety Mechanisms:** (Partially handled by MCP Host) The server should cooperate with the MCP host’s security model. Claude Desktop, for example, requires the user to approve new MCP servers and explicitly select any resource before the model can read it. Our server will present resources in a way that the host can prompt the user. We also ensure that no data is pushed to the LLM without a specific request. In other words, the server will not automatically stream notebook content; it only provides data in response to the host/client’s explicit instructions (which come with user consent steps on the host side). This functional requirement aligns with maintaining a **human-in-the-loop** for data access.

## Non-Functional Requirements

- **Portability:** The solution must be portable across operating systems and environments. The core implementation will be in Python (a cross-platform language), using standard libraries or well-supported packages. It should run on Linux and macOS out-of-the-box, and also on Windows (either natively or via WSL) without code changes. All configuration is via text (CLI or env vars), making it easy to use remotely (SSH) or script into workflows. We will avoid any OS-specific dependencies. To further ensure consistency across environments, we will provide a Docker container configuration as part of the project. Containerization allows the MCP server to run in an isolated environment, avoiding Python dependency conflicts and differences in user setups. *(For MVP, the Docker setup can be basic; the key is to document it so the team can reliably deploy the same setup on their machines.)*

- **Performance and Efficiency:** While LabArchives API latency will dominate in many cases, the MCP server should add minimal overhead. Non-functional goals here include:

  - **Responsive Listing:** Listing notebooks or pages (likely small metadata operations) should happen within a second or two. The server should not pre-fetch entire notebooks on startup (which could be slow); instead, it should fetch data on demand to keep the experience snappy and resource usage low.
  - **Streaming Large Content:** If a page has a very large entry (say a huge text or many attachments), the server should handle it gracefully. The MCP protocol and SDK support streaming or chunking if needed, but for MVP it’s acceptable to fetch the whole content as long as it doesn’t exceed memory. We assume typical usage is text and moderate file sizes. If extremely large data is encountered, we ensure the server doesn’t freeze the LLM indefinitely – perhaps by sending partial content or an error message if too large (this can be noted as a limitation).
  - **Memory Footprint:** The server process should remain lightweight. It will not cache entire notebooks in memory (unless the user specifically reads them). After serving a request, it can allow Python’s GC to free memory. We won’t load data structures larger than necessary. This ensures the server can run alongside other tools on a standard lab computer (e.g., using maybe tens of MBs of RAM, not gigabytes).

- **Reliability and Robustness:** The server should be robust against common failure scenarios:

  - **Network Issues:** If LabArchives API is unreachable (network down, LabArchives service outage), the server should handle the exception without crashing. It can propagate a readable error to the client (which the user will see via the LLM interface) like “Error: Unable to reach LabArchives API”. It will keep running so the user can retry when connectivity returns.
  - **Invalid Inputs:** If the MCP client requests an invalid resource (e.g., a malformed URI or an ID that doesn’t exist or isn’t in scope), the server should respond with a clear not-found or forbidden error message, and log the incident. It should not crash or return undefined data.
  - **LabArchives API Errors:** LabArchives might return errors (like HTTP 401 if token expired, 403 if unauthorized, 429 if rate-limited, etc.). The server should detect these and handle them. For 401/403, inform the user that credentials might be invalid or expired. For 429 (if applicable), perhaps a warning that the API is being called too frequently. We might implement simple **backoff** or rate limiting on our side if needed (e.g., if a user tries to read a lot of pages in a loop, slow down to avoid hitting LabArchives limits).
  - **Logging Failures:** If logging to file fails (e.g., disk full or permission issue), the server should catch that and possibly revert to console logging to not lose logs entirely.

- **Security and Privacy:** Security is paramount since this tool interfaces with potentially sensitive research data:

  - **Credential Security:** The Access Key ID and token/password must be kept secure. The server will accept them via secure means (environment variables or prompt) to avoid exposing on the command line (as CLI args can be visible in process lists). If provided via CLI flag, we will document the risk and suggest env var usage instead. The server will not print these credentials at any time (even in debug logs).
  - **Data Security:** The server should not expose data to any network interface by default. Ideally, MCP communication happens over a local IPC mechanism (Claude Desktop launches the process and communicates via pipes or localhost). We will ensure that if a network socket is used, it’s bound to localhost and not an external interface. This prevents any external actor from connecting to the MCP server and accessing data. In deployment notes, we’ll encourage running this on a secure machine and not exposing it beyond intended use.
  - **Consent and Isolation:** As noted, each resource must only be served when explicitly requested (consented) by the user. The server itself does not enforce GUI confirmation (that’s the host’s job), but it should respect any “cancel” signals if the user denies consent. (In MCP, if the user doesn’t approve a resource, the request may not even reach the server, or the server might receive a cancellation – the implementation will need to handle that state if applicable.)
  - **No Broader Access:** The server will be coded to access **only LabArchives API**. It will not have any generic file system access or other data source access (except what the MCP framework itself might allow for logging etc.). This containment is a security feature: even though running on the user’s machine, it won’t scan local files or send anything unless it’s part of LabArchives data through the API. (Any extension to allow local file access would be a separate tool, not in this scope.)

- **Maintainability & Extensibility:** Though a quick MVP, the project should be maintainable:

  - **Code Structure:** Use clear modular structure – e.g., a module for LabArchives API interaction (so that if LabArchives changes their API or if we want to upgrade to a newer version, it’s isolated), a module for MCP server setup (using the SDK), and a separate config/cli handling module. This separation makes it easier to extend. For example, adding “write mode” later will likely involve the LabArchives module (adding POST requests) and exposing new MCP **tools** – we can plan the structure accordingly.
  - **Use of SDKs/Libraries:** By leveraging the official MCP Python SDK and possibly a LabArchives API wrapper, we reduce custom code, which means less surface area for bugs. The Python MCP SDK is well-supported and follows the spec, so using it ensures our server stays compatible with protocol updates and has a lower maintenance burden (e.g., the SDK might handle JSON-RPC details, threading, etc.). The code should clearly indicate SDK usage (so future developers know to update SDK version if needed).
  - **Testing:** We will include basic tests (even if manual) to verify functionality. For maintainability, perhaps a few unit tests for the LabArchives API module (e.g., parsing a sample API response) and an integration test that simulates an MCP client call (if time permits, using the MCP SDK’s testing utilities). This will guard against regressions as the tool evolves.

- **Compatibility and Standards:** Ensure the tool is compatible with relevant standards and versions:

  - **MCP Version:** The tool will target the latest MCP spec version (as of mid-2025). If the SDK has versioning, use the stable version that matches Claude Desktop’s expectations. In docs, note the MCP version compliance (so if the spec updates, users know which version we implemented).
  - **LabArchives API Version:** Use the current LabArchives API endpoints. If LabArchives has versions (v1, v2, etc.), clarify which is used. We choose the one that’s documented and stable. (If the API responses are in XML, we might convert to JSON internally – the user/LLM will only see JSON output.) We also need to abide by any API usage policies (e.g., if they request a User-Agent string or have call limits, we should comply).
  - **Standards:** JSON-LD usage (if any) should follow the JSON-LD 1.1 spec. Security practices should follow OAuth2 / API key best practices (though LabArchives uses a custom scheme, we handle tokens carefully).

- **Logging and Observability:** (In addition to functional logging reqs) The logging system should be configurable:

  - Support verbosity levels (e.g., quiet vs debug). By default, use an **info** level that logs major actions without overwhelming detail. For troubleshooting, a `--verbose` flag can turn on debug-level logs (including API response codes, etc.).
  - The log format might include structured elements (e.g., we could output as JSON lines for easier parsing, but plain text is fine for MVP). The key is that if something goes wrong, a developer can diagnose it from logs.
  - **Monitoring:** In future or for power users, if running this server continuously, one might integrate with monitoring systems. While not in MVP, we note that the tool could output health pings or metrics. At minimum, it could have an option to output a simple heartbeat or status upon request. (This is just noted for completeness; not a requirement now.)

- **Deployment & DevOps:** Though a small tool, consider the deployment ease:

  - The system should start up quickly (a few seconds at most to initialize). It should not require a heavy environment (no large database or caches needed). This makes it easy to start/stop as needed.
  - We aim for the ability to run multiple instances on one machine (if two different users want to run their own scopes) without conflict. This means default configurations (like default ports, if any, or file paths) shouldn’t collide – but since likely using separate processes with separate Claude instances, it’s fine. We just avoid using a fixed file or socket name that could conflict.
  - **Backward compatibility:** Not a big issue for MVP, but if the LabArchives API requires changes or if a newer MCP client is used, the design should allow iteration without breaking existing usage. For example, if we release v0.1 and then add features, ensure we don’t remove the basic read-only functionality or change the output format in a way that would break existing prompts that rely on it (unless necessary). This is more of a principle than a hard requirement at this stage.

In summary, the non-functional requirements ensure the LabArchives MCP server is not only *functional* but also secure, reliable, and easy to use in practice. Even as an MVP developed in one week, these considerations will make the difference between a prototype and a deployable tool in a real lab environment.

## Architecture and API Overview

**System Architecture:** The LabArchives MCP Server follows a client-server architecture inherent to MCP. In this context:

- The **MCP Host/Client** is an LLM application like Claude Desktop (running on the user’s machine), which acts as the MCP client initiator.
- The **MCP Server** (our tool) runs as a separate process, providing an API that the client communicates with. Communication is handled via JSON-RPC over MCP’s transport (likely standard input/output streams if launched by Claude, or a local WebSocket/HTTP if configured otherwise). The architecture is summarized as follows:

```plaintext
[Claude Desktop (LLM Host & MCP Client)]  <-- JSON-RPC/MCP -->  [LabArchives MCP Server]  <-- HTTPS REST -->  [LabArchives API Server]
```

Claude Desktop will spawn or connect to the MCP Server process when the user enables the integration (usually via a config file entry pointing to the server’s executable). The communication channel between Claude and the MCP Server is local and secure (Claude often uses an IPC mechanism; e.g., it might launch the process with pipes). When Claude (or another host) sends a request, the MCP Server’s JSON-RPC handler (from the SDK) dispatches it to our implemented methods.

**MCP Interface & Resource Model:** We define **LabArchives data as MCP resources**. Each resource has a URI and can be listed or read:

- We will establish a custom URI scheme for LabArchives, e.g., `labarchives://`. The exact URI patterns could be:

  - `labarchives://notebook/{notebookId}` – representing a notebook resource (which might list its pages).
  - `labarchives://notebook/{notebookId}/{pageId}` – representing a page resource (which can be read to get entries content).
  - `labarchives://entry/{entryId}` – possibly for individual entries (though in MVP we might fetch entries only as part of reading a page).
  - Alternatively, we might keep it simpler: one resource type for pages and one for notebooks. For example, listing might return URIs for each page in the scope (with an embedded path in the name). The approach will be guided by how the MCP client (Claude) presents resources to the user. Claude Desktop typically shows a list of resources by name; here we might name them like “Notebook X – Page Y” for direct page access.

- **Resource Listing Implementation:** When the client calls `resources/list`, our server needs to return an array of available resources (each with `uri`, `name`, optional description). If the scope is a single notebook, we might list all pages as the resources. If the scope is all notebooks, we might list notebooks first (the user would then select a notebook, possibly triggering another list of pages – this depends on whether hierarchical listing is supported in MCP natively or if we simulate it via naming conventions or templates). MCP does support the concept of *resource templates* for dynamic hierarchies, which we could use to allow clients to query for pages of a specific notebook by filling in a template. For MVP, a straightforward approach is fine (e.g., list all accessible pages in one go, or implement a two-step selection by listing notebooks then pages).

- **Resource Reading Implementation:** When `resources/read` is called with a specific URI (say `labarchives://notebook123/page456`), the server will:

  1. Parse the URI to extract identifiers (notebook 123, page 456).

  2. Call the LabArchives API to retrieve that page’s content. Likely this involves an endpoint like `.../api/entries/list` or `.../api/pages/{pageId}/entries` (the exact API call will be determined from LabArchives docs). The response might be XML or JSON containing all entries. We parse that into our internal representation.

  3. Construct a JSON object (or Python dict) for the page. For example:

     ```json
     {
       "notebook": "Lab Book A",
       "page": "Experiment Results Oct 2025",
       "page_id": 456,
       "entries": [
          { "entry_id": 111, "entry_type": "Rich Text", "title": "Observation", "content": "We observed ...", "last_modified": "2025-10-05T10:00:00Z" },
          { "entry_id": 112, "entry_type": "Attachment", "title": "Microscopy Image", "file_name": "cell.png", "download_url": "...", "size": 502314 }
       ]
     }
     ```

     This JSON will then be returned via MCP. The Python SDK likely allows returning structured data – if we return a Python dict, it may serialize to JSON for the client automatically (possibly as a `text` resource containing JSON text, or using structured output support).

  4. The MCP server sends the response. Claude Desktop, upon receiving it, will not automatically show it to the user until the user chooses to “insert” or use it (typical flow: the user selects a resource, then the content might be inserted into the chat context for the LLM). Our server doesn’t control that part; it just needs to deliver the data when asked.

- **LabArchives API Integration:** Internally, the server will use LabArchives’ REST API. The base URL is typically `https://api.labarchives.com/api` (with region-specific domains as needed). The API is somewhat RPC-like, with endpoints structured by *classes* and *methods* (e.g., `Notebook.getBooks`, `Page.getPageEntries` etc., as hinted by their documentation). We will use the patterns from LabArchives API docs or existing wrappers:

  - Example: to list notebooks, the API might have an endpoint that returns all notebooks accessible to the user’s credentials. The response could be a list of notebook IDs and names.
  - To list pages in a notebook, possibly an endpoint with the notebook ID.
  - To get entries on a page, an endpoint with the page ID returning entry records (including content or links to content).
  - Authentication: likely each call needs the `akid` (Access Key) and either a `sid` (session ID) or `uid` (user ID) plus a signature or token. In one documented approach, after obtaining a user’s UID via a login call, subsequent calls include `uid` and the permanent or temporary password token. Another approach might use a session token if login returns one. We will figure out the exact flow and implement it within an `Auth` class/module. On startup, the server can perform an authentication step (if needed) to obtain any session or user context required. This could be as simple as one GET request to verify credentials and get a UID.
  - Error handling: if the LabArchives API call fails (network or HTTP error), the internal function will throw an exception or return an error object which we catch and translate to an MCP error response or log message.

- **Components and Data Flow:**

  - **CLI/Config Layer:** Parses command-line args (using Python’s `argparse` or similar) to get credentials, scope, options. It then initializes the core server.
  - **MCP Server (Core):** Utilizes the Python MCP SDK to define handlers for `list_resources` and `read_resource`. For example, using a decorator or registering callbacks: `@mcp.resource("labarchives://{type}/{id}")` could be used to handle various resource URIs dynamically (if SDK supports wildcard URIs), or we manually handle routing in a single handler. We will set the server’s name and version here (e.g. “labarchives_mcp” v0.1).
  - **LabArchives API Client:** A small subsystem (could be just functions or a class) that knows how to call LabArchives API endpoints. It will likely use the `requests` library to make HTTPS calls. This client will format the URLs, add required auth parameters (like akid, token, uid), and parse the responses. We might integrate or reference logic from the open-source `labarchives-py` project or LabArchives documentation to construct these calls. For instance, their README shows usage of a `make_call('users', 'user_info_via_id', params=...)` style. We can either use that wrapper or directly do similar.
  - **Data Model & Conversion:** The data returned from LabArchives might be XML (the wrapper’s example uses XML parsing with `xml.etree`). We will convert that to Python dictionaries. For consistency, we’ll produce JSON keys that are human-readable (like "title", "content") rather than the LabArchives raw field names if they are cryptic. We will preserve essential identifiers (so that in the future, write operations or specific retrievals can reference them).
  - **Logging Module:** A simple logging configuration that all parts use to record events (as described in requirements).

- **MCP Capabilities:** During the handshake, our server will advertise its capabilities. In MCP terms, since we support resources, we’ll advertise the `resources` capability (and any relevant sub-capabilities like `resources.list` and `resources.read`). We are not implementing MCP tools or prompts in this MVP, so those capabilities will be absent. The host (Claude) will know from this what it can do. Claude Desktop will likely then call `list_resources` immediately to show the user available data. We should also supply a friendly description for the server/tool (if MCP allows that), so it might appear in the Claude UI as “LabArchives Browser” or similar.

- **Consent Flow (Architecture):** Claude Desktop’s integration mechanism implies the following user flow:

  1. User adds the MCP server config (pointing to our CLI) in Claude and restarts Claude.
  2. Claude launches the MCP server (probably on startup or when first needed) via the specified command. Our server starts, authenticates to LabArchives (if credentials provided), and waits.
  3. The user, in Claude’s interface, chooses to browse or insert data from LabArchives. When they do this, Claude sends a `resources/list` request. Our server returns a list of items (e.g. pages or notebooks).
  4. Claude shows these to the user (maybe as a list of files/tools). The user then selects a specific page or notebook – Claude then sends `resources/read` for that URI.
  5. Our server fetches the content and returns it. Claude may then show a snippet or summary to the user, asking “Allow Claude to use this content?” (This step is speculation based on how other tools work; likely the user confirms usage).
  6. Upon confirmation, the content is injected into the prompt context for the AI, and Claude can now answer user questions using that data.

  Throughout this, the architecture ensures the MCP server only responds to explicit requests, and Claude handles the user interaction and high-level coordination.

- **Example Interaction (for clarity):** Suppose a user asks Claude, *“Summarize the results of my experiment from last week (stored in LabArchives).”* Claude doesn’t have that context, so the user (or Claude via a plugin-like flow) will initiate using our MCP server:

  - Claude (MCP client) -&gt; LabArchives MCP Server: `resources/list` (maybe scoped to the specific notebook if configured).
  - Server -&gt; Claude: returns `[ { "uri": "labarchives://notebook42/page1001", "name": "Experiment Results 2025-07-12" }, { "uri": "labarchives://notebook42/page1002", "name": "Experiment Setup 2025-07-05" }, ... ]`.
  - User sees a list of pages (dates or titles) and picks "Experiment Results 2025-07-12".
  - Claude -&gt; Server: `resources/read` with URI for that page.
  - Server -&gt; Claude: returns the page content JSON (maybe as a stringified JSON or a structured object if Claude can handle that). This includes the text of observations, maybe a link to attached data.
  - Claude asks user for consent to use that data (Claude does this automatically since it’s an MCP security feature).
  - User consents.
  - The page content is now fed to Claude’s model, and the model proceeds to summarize it in natural language.
  - Meanwhile, every step is logged by the server (list call, read call, etc.).

**Note on JSON vs JSON-LD in architecture:** If we include JSON-LD, it might look like adding an `"@context": { ... }` in the returned JSON. Claude (or any client) will likely just treat it as additional text. The advantage is future-proofing (if an AI can utilize that context). But even without deep AI understanding, it doesn’t break anything. We might include a context URL that defines LabArchives objects (perhaps a small custom schema we host or just a descriptive mapping). For MVP, our architecture will allow adding this easily (since it’s just another field in the JSON output).

**Versioning & Future Hooks:** We include in the architecture some placeholders for future features:

- A version number for the server (e.g. “LabArchives MCP Server v0.1.0”) that can be reported. Possibly an MCP server can respond to some meta query about its version or we just log it. This helps with support and upgrades.
- The code is structured so that adding **Tools** for write-back later is possible. In MCP, “tools” are actions the AI can invoke (write operations would be tools). Architecturally, this might mean in the future we’ll add functions decorated with `@mcp.tool()` for actions like `create_entry(notebook, page, content)`. The current read-only design does not include tools, but we keep the architecture extensible. For instance, our LabArchives API client module will have methods like `create_entry(...)` ready (or at least stubs), and the overall server capability negotiation can easily include new capabilities when we add them.
- **Version History**: We anticipate needing to retrieve past versions of an entry. The architecture can handle this either as an extended resource (e.g., `labarchives://entry/{entryId}/v{versionNum}` might be a URI format to get a specific revision) or as a separate listing (like `resources/list` on a special “history” resource). We won’t implement it now, but by structuring data with IDs and perhaps noting the latest version number (the API does provide version number info), we can retrieve older content later.

In summary, the architecture leverages the standardized MCP client-server pattern, using the Python MCP SDK as the backbone for communication, and the LabArchives API as the data source. The data flows from LabArchives -&gt; MCP Server -&gt; LLM client in a secure, controlled manner. Each component (CLI interface, MCP logic, LabArchives API client) has a defined role, making the system easier to develop and reason about. This design will meet the MVP needs and provide a foundation for future expansion.

## Tooling and Libraries

The development will utilize a number of existing tools and libraries to speed up implementation and ensure reliability:

- **Programming Language:** Python (3.9+ recommended). Python was chosen for its rapid development capabilities and the availability of an official MCP SDK in Python. The target user (developers or researchers) are likely comfortable with Python, and it runs on all required platforms.

- **Model Context Protocol SDK (Python):** We will use the open-source **Python MCP SDK** provided by the Model Context Protocol project. This SDK abstracts much of the protocol handling (JSON-RPC session management, message formats, capability negotiation, etc.), allowing us to focus on defining our server’s functionality. For example, the SDK likely provides a `Server` or `FastMCP` class to create an MCP server, and decorators or methods to register resource handlers. By using the SDK, we ensure compliance with the MCP spec out-of-the-box and interoperability with clients like Claude. It also means less low-level coding (we don’t need to implement JSON-RPC from scratch). The SDK is MIT-licensed and widely adopted in the MCP community, making it a reliable choice. We will pin a specific version of the SDK (the latest stable) in our requirements.

- **HTTP Requests Library:** For communicating with LabArchives’ REST API, we will use a tried-and-tested HTTP client library. `requests` (Python Requests) is the likely choice, as it is simple and popular for REST calls. It will handle HTTPS, query parameters, and can easily parse responses (text or binary). If we need async support (depending on MCP’s threading model), we might consider `httpx` or async requests, but MVP can be synchronous since calls are user-initiated and relatively infrequent. The LabArchives API is blocking anyway (no streaming API), so synchronous requests are fine.

- **LabArchives API Wrapper (optional):** There is a small Python package `labarchives-py`. We will review it for reference. It provides a `Client` class that can make arbitrary API calls given the class and method names. However, it’s quite minimal and uses `requests` under the hood. We might choose not to add an extra dependency if it’s not robust or complete. Instead, we can implement the few needed API calls ourselves directly. If time is short, using it as a quick way to call, for example, `client.make_call('users', 'user_access_info', params)` to get a UID could save some effort. Since it’s MIT-licensed as well, we could vendor or depend on it if needed. This decision will be made during development based on ease and reliability.

- **JSON Processing:** Python’s built-in `json` library will be sufficient for constructing and serializing JSON data. We might also use **Pydantic** or Python dataclasses for defining structured outputs (the MCP SDK might integrate with Pydantic for validating structured data in responses). For instance, we could define a Pydantic model for an Entry or Page, and then return that from a resource handler; the SDK could transform it to JSON. This ensures our JSON is well-formed and documented via code. If using Pydantic is overkill for MVP, we will at least define clearly the dict schemas in code comments.

- **Logging Framework:** Python’s built-in `logging` library will be used to implement the logging features. We can configure a logger with different levels and handlers (console, file). This avoids any external logging dependency. We will ensure to format logs nicely (maybe include the level and timestamp by using `logging.basicConfig(format=..., level=...)`). If more advanced logging is needed (like rotating files or JSON logs), the `logging` module can be extended accordingly.

- **CLI Parsing:** Python’s `argparse` (from the standard library) will handle command-line arguments. It provides a straightforward way to define options like `--access-key`, `--token`, `--notebook`, etc., with help messages. This contributes to usability (the user can run `labarchives-mcp-server --help` to see usage instructions). We might also support configuration via environment variables (using `os.environ` in Python to fetch, say, `LABARCHIVES_AKID`, etc.). This dual approach is common: if env vars are present, they act as defaults that can be overridden by explicit CLI flags.

- **Docker:** While not a code library, Docker will be part of our tooling for deployment. We will write a simple `Dockerfile` (e.g., using an official Python base image). This will install our package and set the entrypoint to run the server. Docker usage ensures any dependencies (like the MCP SDK and requests) are installed in a consistent environment. The Docker container is especially useful for those who don’t want to manage Python environments or for running the server in an isolated manner. We may upload the image to a container registry (perhaps the MCP community’s Docker Hub namespace) for easy access. The Docker approach aligns with recommendations for MCP servers to avoid environment issues.

- **Version Control:** Git will be used for version control of the code (with a GitHub repository hosting the project). This isn’t directly user-facing, but it’s part of our development tooling. Issues and enhancements can be tracked on the repo, encouraging community engagement.

- **Testing Tools:** For development sanity, we will use some basic testing tools:

  - Python’s `unittest` or `pytest` for writing a few tests (e.g., a test for the authentication flow with dummy responses, or parsing a known LabArchives API XML snippet to JSON).
  - If possible, the MCP SDK might have a testing harness or we might use the MCP Inspector tool provided by Anthropic to simulate client calls to our server. This can help verify our MCP responses without needing to always use the actual Claude UI. The MCP Inspector is an interactive tool to connect to an MCP server and invoke calls, which will be very handy for debugging prior to integration.
  - Since this is an MVP in a week, testing will be pragmatic, focusing on core paths.

- **Documentation Tools:** We will write documentation in Markdown ([README.md](http://README.md) in the repo) for usage. Optionally, if needed, Sphinx or MkDocs could be used for more extensive docs, but likely overkill for MVP. A well-written README with examples is sufficient. We should also provide sample config for Claude Desktop (how to register the server in Claude’s config JSON), gleaned from docs or examples.

- **Libraries for Future (not necessarily in MVP):**

  - If we were to implement write-back or more complex features, we might consider libraries like `click` (for CLI if argparse becomes too limited), or `rich` (for nicer console output/logging). But MVP will keep things minimal.
  - For JSON-LD context, if we wanted to formally define a context, we could just hardcode a small context dict. If needed, a library like `pyld` (JSON-LD processor) could be used to validate it, but that’s likely unnecessary for now.

**Dependency Management:** We will list all dependencies in a `requirements.txt` or [setup.py](http://setup.py). Likely dependencies: `mcp` (the SDK, if named that way on pip), `requests`, possibly `pydantic` (if not already a dependency of the SDK), and maybe `labarchives-py` if we use it. The total dependency footprint is expected to be small. We’ll ensure that installing our package doesn’t pull in anything heavy or unnecessary.

By leveraging these tools and libraries, development is accelerated and the risk of low-level bugs is reduced. The official MCP SDK ensures protocol correctness, and using Python requests for the LabArchives API ensures we communicate reliably. The toolchain aligns with the goal of building a robust MVP quickly.

## CLI Interface Design

The CLI is the primary way users will configure and run the LabArchives MCP Server. Below is the design of the command-line interface, including supported commands, options, and usage examples:

- **Command Invocation:** The tool will be installed as an executable script named (for example) `labarchives-mcp`. After installation (via pip or Docker container entrypoint), the user should be able to run `labarchives-mcp [OPTIONS]`. This command will start the MCP server and keep it running until manually stopped. We are not planning multiple subcommands (like `init` or `run`) for MVP; a single entry point is sufficient. However, for clarity, we might accept an optional subcommand like `labarchives-mcp serve` (default) to explicitly start serving. The `--help` flag will show usage.

- **Authentication Options:**

  - `--access-key <ACCESS_KEY_ID>` or `-k <ID>`: Provide the LabArchives API Access Key ID. This is a required parameter if not set via environment.
  - `--access-secret <ACCESS_SECRET>` or `--access-password <PASSWORD>` or `-p <PW>`: Provide the corresponding secret/password or user token for the API. We will accept either terminology (“secret” for permanent API key secret, or an external app “password token” for user token) to avoid confusion. In documentation, we’ll clarify it’s the API authentication token (which could be the external app token).
  - `--username <USER_EMAIL>` (optional): If using a personal token that requires a username for login, the user can supply their LabArchives login email here. (If the Access Key is organization-specific and not tied to a user, this may not be needed. But to cover SSO cases, we include it.) Alternatively, we might infer that if a token looks like a personal token, we need a username. Accepting it explicitly is clearer.
  - **Environment Variables:** Instead of typing credentials every run, the tool will check environment variables: `LABARCHIVES_AKID` for the access key, `LABARCHIVES_SECRET` (or `LABARCHIVES_TOKEN`) for the password/token, and possibly `LABARCHIVES_USER` for the username. If those are set, the user can run the tool without `--access-key` flags each time. Command-line arguments will override env variables if both are present. This provides flexibility and is more secure (especially on multi-user systems) since environment variables are not listed in process arguments.

- **Scope and Filtering Options:**

  - `--notebook-id <ID>`: Limit context to a specific notebook by its ID. This ID would be the internal LabArchives notebook identifier (likely an integer or GUID). If a user knows the ID, they can use this.
  - `--notebook-name "<Name>"`: Alternatively, specify the notebook by name (if the name is unique for the user). If provided, the server on startup will attempt to find a notebook with that exact name (via an API call or by listing notebooks and matching). If found, it uses that notebook’s ID for scoping. If not found, it will exit with an error message.
  - `--folder-id <ID>` or `--folder-path "<Path>"`: (Optional for MVP) If we want to allow deeper scoping, these flags could specify a folder. For MVP, we might not implement folder-level filtering unless easily done; but we leave the design possibility. The folder path could be something like `"Project A/Experiment 1"` which the server would match under the specified notebook.
  - If multiple scope options are provided (e.g. notebook and folder), the server will apply both (folder within that notebook).
  - If no scope option is given, the default is all notebooks accessible by the credentials.

- **Output Format Options:**

  - `--json-ld` (flag): Enable JSON-LD context in the output. If this flag is present, the server will include an `@context` in JSON responses. Without it, it will output plain JSON. The default could be plain JSON for simplicity, requiring the user to opt-in to JSON-LD if they specifically want it. This keeps the default output slightly cleaner for general use.
  - We might not need a separate flag for “structured vs text” because by design we return structured JSON. However, if we find that the MCP client expects maybe a text blob, we might consider an option like `--mode text` vs `--mode structured`. Ideally, the SDK and Claude can handle structured JSON. If not, we could fall back to converting JSON to a pretty-printed string. For MVP, we assume structured is fine.

- **Logging and Verbosity Options:**

  - `--log-file <PATH>`: Path to a file to write logs to. If not provided, logging goes to stdout (or a default file). If provided, logs will be appended or rotated (simple append for MVP). Example: `--log-file /var/log/labarchives_mcp.log`. We will ensure that if the file/dir doesn’t exist or is not writable, the server warns and falls back to console logging.
  - `--verbose` or `-v`: Increase verbosity of logs (debug mode). This would turn on debug-level logging, which might include LabArchives API responses or other detailed info. Without `-v`, we default to info level (key events only). Possibly allow `-vv` for even more verbosity (though info/debug likely suffice).
  - `--quiet`: Opposite of verbose, only log warnings/errors. Useful if the user only cares about errors and not the details of every access. By default, we are not quiet because traceability is a core feature, but the option is there if needed.

- **General Options:**

  - `--help`: Show help summary of all these options.
  - `--version`: Show the version of the MCP server. It will print something like “LabArchives MCP Server version 0.1.0” and exit.
  - We might include a `--test` or `--check` mode: for instance, if the user runs `labarchives-mcp --check-connection`, it could attempt to authenticate and fetch a minimal piece of data (like list notebooks) and report success or failure, then exit. This could be useful for verifying credentials without launching the full server (especially since Claude might not give detailed error if credentials are wrong). However, due to time constraint, this is a nice-to-have. Alternatively, simply running the server will attempt auth and we will log if auth fails.

- **Usage Examples:** (to include in documentation and help message)

  - Run with permanent credentials:

    ```bash
    export LABARCHIVES_AKID=ABCDEFG12345  
    export LABARCHIVES_SECRET=MY_SECRET_PASSWORD  
    labarchives-mcp --notebook-name "Smith Lab Notebook" --log-file lab_mcp.log
    ```

    This example uses env vars for creds, restricts to a notebook by name, and logs to a file. The server would start, log in to LabArchives, find the notebook “Smith Lab Notebook”, and wait for Claude connections.

  - Run with personal token (SSO user):

    ```bash
    labarchives-mcp -k ABCDEFG12345 -p "X1Y2Z3TEMPORARYTOKEN" --username alice@university.edu -v
    ```

    This passes everything via CLI (not ideal for security, but possible). It enables verbose logging. The server on startup will use the provided token and username to obtain the user’s UID via the API, then proceed.

  - Running via Docker:
    If we publish a Docker image, usage might be:

    ```bash
    docker run --rm -it -e LABARCHIVES_AKID=ABCDEFG12345 -e LABARCHIVES_SECRET=MY_SECRET_PASSWORD ghcr.io/ourorg/labarchives-mcp:latest --json-ld
    ```

    Here we pass env vars into the container. Claude’s config would need to call Docker similarly (Claude can directly execute Docker as seen in other examples).

- **Interactive Behavior:** The CLI itself will generally not be interactive (no prompts) unless absolutely necessary (e.g., if no credentials provided at all, we might print an error and exit rather than prompt, to avoid hanging waiting for input, since often it will be launched by another app). We assume the user will provide the needed info via options. If we wanted to be user-friendly in manual mode, we could detect if running in a TTY and then prompt for missing password (masking input). But since most usage might be via config, this is optional. MVP can simply require all needed inputs or exit with usage info.

- **Feedback/Status Output:** When the server starts, it will output some informational messages to stdout (which also go to log):

  - Successful authentication (or if failed, an error and exit).
  - Number of notebooks found or the target notebook scope confirmed.
  - “MCP Server listening for client connections...” when ready. Possibly include the server name and that it’s connected to LabArchives.
  - We avoid overly verbose output in normal mode because the host (Claude) launching it might not show this to the user anyway. But if a user runs it manually, this gives assurance it’s working.

- **Shutdown:** The user can stop the server with Ctrl+C (SIGINT). We will handle graceful shutdown: closing any open sessions or file handles, and informing (via MCP protocol if needed) that the server is going offline. Claude Desktop likely will detect the closure. We will ensure that a second Ctrl+C will force exit if first doesn’t (typical Python behavior with KeyboardInterrupt is fine).

- **Error Messages:** If the user misconfigures something (e.g. typo in notebook name, invalid credentials), the CLI should output a clear error before exiting. For instance: “Error: Notebook 'X' not found. Available notebooks: ...” or “Authentication to LabArchives failed (check Access Key ID and token).” These messages will help the user correct the issue. We’ll also set appropriate exit codes (non-zero on failure).

- **CLI Parsing Example:** (For documentation)

  ```plaintext
  usage: labarchives-mcp [--access-key AKID] [--access-secret SECRET] [--username USER] 
                         [--notebook-id NID | --notebook-name NAME] [--json-ld] 
                         [--log-file FILE] [--verbose] [--quiet]
  
  Start the LabArchives MCP Server (read-only).
  
  Options:
    -k, --access-key AKID      LabArchives API Access Key ID (required if not set in environment)
    -p, --access-secret SECRET LabArchives API Access Password/Token (required if not set in environment)
    -u, --username USER        LabArchives username (email), needed if using a personal token
    -n, --notebook-name NAME   Restrict context to the notebook with this name
    --notebook-id NID          Restrict context to the notebook with this ID
    --json-ld                  Include JSON-LD @context in outputs for semantic clarity
    --log-file FILE            Log events to the specified file (in addition to stdout)
    -v, --verbose              Enable verbose logging (debug mode)
    --quiet                    Only log warnings and errors (suppress info logs)
    --version                  Show version information and exit
    -h, --help                 Show this help message and exit
  ```

  (The actual formatting in code may differ, but this captures the intent.)

- **Integration with Claude Desktop:** To use this CLI with Claude, the user will typically edit Claude’s configuration (usually `claude_desktop_config.json`) to add an entry under `"mcpServers"` – for example:

  ```json
  "mcpServers": {
      "labarchives": {
          "command": "labarchives-mcp",
          "args": ["--access-key", "ABCDEFG12345", "--access-secret", "SECRETXYZ", "--notebook-name", "My Notebook"]
      }
  }
  ```

  Claude will then run that command. (Alternatively, the user could wrap it in a script to source env vars). We will include such instructions in our README. Our CLI design ensures everything can be passed as arguments, making it easy to configure in this manner.

In summary, the CLI is designed to be simple and clear, covering the essential configuration needs. By following common conventions (like -h for help, -v for verbose) and providing safe ways to handle credentials, we make the tool accessible to both automation and manual use. The interface balances flexibility (many options) with security (env vars for secrets) and should meet the needs of the target user group.

## Development Milestones

**Week 1 – MVP Development Timeline:** *(The goal is to have a functional MVP by end of Week 1, given one developer or a small team working on it.)*

- **Day 1-2: Project Setup & Authentication Prototype**

  - *Initialize Repository:* Set up a GitHub repo (e.g., **labarchives-mcp-server**). Add basic project structure (README, license file, directories for code and tests). Decide on license (use MIT License to align with MCP SDK and encourage open collaboration).
  - *MCP SDK Integration:* Install and experiment with the Python MCP SDK. Create a minimal MCP server script that starts and prints “hello” or similar when a client connects. This is to verify environment setup and understand the SDK’s patterns (e.g., how to handle `resources/list`).
  - *LabArchives API Authentication:* Write a small Python script to test LabArchives API login. Using sample credentials (or a test account if available), attempt to call a simple API endpoint. Likely, use `requests` to call something like `/api/users/user_info` or `/api/notebooks/list`. If no test credentials, mock the expected XML/JSON response to ensure parsing logic works.
  - *Decide on approach:* Determine if we use the `labarchives-py` wrapper or direct HTTP calls. If direct, draft helper functions for login (get UID) and fetching notebooks.
  - *Success by end of Day 2:* Able to authenticate and retrieve a list of notebooks via API in a standalone test. Also, have a dummy MCP server running (though not connected to LabArchives yet).

- **Day 3: Core MCP Server Implementation**

  - *Resource Listing Implementation:* Code the `resources/list` handler. Connect it to the LabArchives API call for listing notebooks or pages. For now, perhaps implement listing notebooks if no scope, or listing pages if a notebook scope is provided (we might decide to always list pages of the chosen notebook for simplicity). Ensure the output format matches MCP spec (JSON with required fields). Test this function in isolation (e.g., by calling it with known data).
  - *Resource Reading Implementation:* Code the `resources/read` handler. This should take a URI, parse it, call LabArchives to get content, and return JSON. Focus on one level (likely pages): implement fetching entries from a page. For now, we can simplify content (e.g., if an entry has an attachment, just note “attachment omitted”). The key is returning some content to prove end-to-end.
  - *Data Structuring:* Create data models (could be simple classes or dict schemas) for Notebook, Page, Entry. Use these in the above handlers so the structure is consistent. Possibly use Pydantic to validate if time permits.
  - *Logging Setup:* Introduce the logging mechanism. At this stage, start logging major actions (just to console). For example, log “Fetched X notebooks” or “Read page 123 (title=XYZ)”. This will help during testing.
  - *Internal Testing:* Without Claude yet, simulate an MCP call. Possibly use the MCP Inspector or write a small client to call our server’s list and read functions directly (since they might just be normal Python functions when not in server context). Ensure that when given a sample page ID, the flow goes from LabArchives API -&gt; returns JSON.
  - *Success by end of Day 3:* The MCP server can list and read at least one layer of data when triggered (even if via a manual test harness). The interactions with LabArchives API for those functions are working (tested with real or dummy data). Basic logging is visible.

- **Day 4: CLI & Configuration, Refinements**

  - *CLI Argument Parsing:* Implement `argparse` with all planned options. Test that it correctly reads env vars and flags. For instance, simulate running with `--notebook-name` and ensure it resolves to an ID via an API call (create a function `resolve_notebook(name)` that lists notebooks and finds the ID). Handle errors if name not found.
  - *Scope Enforcement:* Use the scope info to filter results in list handler. If scoped to a notebook, ensure list doesn’t return notebooks or pages outside it. Possibly store a global or server state of allowed notebook IDs. The read handler should check if the requested resource’s notebook matches the allowed one. Add checks and tests for these conditions.
  - *JSON-LD Option:* If doing JSON-LD, decide on a context (maybe a simple one embedded). Implement that such that if flag is set, the output dict gets an `@context`. If not set, output without it. Test with flag on/off to see difference.
  - *Logging to File:* If time, implement file logging. At least ensure the logger can be configured via an option. Write logs for key events with timestamps.
  - *Documentation (ongoing):* By now, update the README with how to install (maybe pip install from source) and how to run (with examples as above). Write the usage examples and explain each option. Also document how to get LabArchives credentials (briefly, e.g., “Contact your institution’s LabArchives admin for an API access key, or generate a personal app token under User Profile &gt; Application Authentication”). This is important for user onboarding.
  - *Success by end of Day 4:* The server can be launched via CLI with various options, and it applies those settings (credential env vs args, scope filtering, etc.). Running `--help` shows the intended output. We have a nearly feature-complete server in standalone mode, lacking only integration testing with an MCP client.

- **Day 5: Integration Testing with Claude (or MCP Client)**

  - *Claude Desktop Integration:* Configure Claude Desktop on a test machine with the new MCP server. (If Claude Desktop is available to the developer – if not, use the MCP Inspector tool as substitute.) Start Claude and see if it launches our server. This will test that our command and arguments are correct (e.g., paths, etc.).
  - *Consent Flow Testing:* In Claude, try to list resources. Ideally, the server’s list handler is called and returns data, which Claude should display. Then try reading a resource (the user selects it). Check that Claude receives and (with user consent) displays or uses the content. At this point, we might discover formatting issues: perhaps Claude expects a certain structure or size limit. Tune the output if needed (e.g., maybe we decide to truncate extremely long content or split into multiple resources if a page is huge, to make user selection easier). We also might refine naming conventions (maybe include the notebook name in resource `name` field if multiple notebooks are listed).
  - *Performance Check:* If the lab notebook is large, measure how our server handles it. Perhaps simulate with a loop or real data. If listing all pages is slow due to many pages, consider paging or limiting (for MVP, maybe just log a warning if too many).
  - *Error Handling:* Induce an error to see how it behaves – e.g., run with a wrong token to ensure it fails gracefully with a message. Or stop network to see if a read times out and recovers. Fine-tune exception catching around API calls. Possibly set a timeout on `requests` calls so we don’t hang indefinitely on a network issue.
  - *Logging Review:* Check the logs produced during these tests. Ensure no sensitive info, and that they are helpful. Maybe adjust log levels or messages as needed.
  - *Success by end of Day 5:* The LabArchives MCP Server works end-to-end with an MCP client (Claude). We have verified that a user can list notebooks/pages and retrieve an entry’s content through the LLM interface. Any critical bugs found are fixed. The MVP is essentially functional now.

- **Day 6: Polish and Documentation**

  - *User Documentation:* Finalize README with steps to deploy. Possibly write a quick “Quick Start”: how to install via pip (or provide a requirements.txt and instruct to `pip install -r requirements.txt` if not packaged yet), how to set env vars, how to configure Claude Desktop. Include screenshots or code blocks as needed for clarity. Ensure all required context (like obtaining tokens) is mentioned.
  - *In-line Documentation:* Ensure all public functions have docstrings. Comment the tricky parts of the code (especially around parsing the LabArchives API responses). This will aid anyone reviewing or modifying the code.
  - *Milestone Tag:* Create a git tag/release `v0.1.0` signifying the MVP release. This can be used if packaging (like uploading to PyPI or Docker Hub).
  - *Community Engagement:* If time, publish the repository (if it was private during dev) and perhaps announce on the MCP community forum or to colleagues who will test it.
  - *Buffer:* Use any remaining time to address any minor enhancements or backlog items that were skipped (for example, if folder scope wasn’t done and it’s easy, implement it now; or if JSON-LD context is still pending, finalize it). Also, run through a final test of all CLI options (does `--quiet` truly quiet logs? does `--json-ld` actually add the context? etc.).

- **Day 7: Handover and Deployment**

  - Given the one-week target, by day 7 the focus is on deploying and user testing:

    - If the target lab team is separate from the developer, deliver the package to them. This might involve writing an email or brief guide tailored to them, referencing the README.
    - Assist with installation: for example, help them run `pip install` or provide a one-line Docker run command.
    - Observe (or gather feedback) from initial usage. If any showstopper bug appears (e.g., an encoding issue or an unexpected API difference), fix it quickly.
    - Ensure the solution fits in their workflow – e.g., maybe they want to run it on a lab server so multiple people’s Claude can connect (though MCP is generally 1:1 with client, but it could be run per user).

  - *Project Wrap-up:* Summarize what was built, and list out next steps (which are the roadmap items). This can be done as part of a final documentation section or a short internal report. It’s essentially preparing for the “beyond MVP” phase.

**Post-MVP (Future Roadmap):** Once the MVP is delivered, subsequent milestones would include:

- **Safe Write Mode (Planned Feature):** Introduce write-back capabilities in a controlled manner. This would likely be a **Phase 2** project. It involves:

  - Adding MCP *tools* for creating or updating entries. For example, a tool method `create_entry(notebook_id, page_id, content, entry_type)` could be defined. The server would advertise this capability. Claude (or other LLM) could then invoke it, but *only* after user review. Likely flow: the AI drafts an entry (or edit) and asks “Do you want to save this to LabArchives?” The user must confirm, then the server would call the LabArchives API to perform the write (POST/PUT request).
  - We will implement confirmation requirements: either rely on the LLM client’s built-in confirmations (Claude usually prompts user for tool usage), and/or in our server logic ensure we never write without a positive signal. For example, we might implement a “dry-run” mode where the server returns what it *would* do, and requires a second call to actually do it. However, since MCP is designed with human consent in mind, we can likely trust the workflow to handle it if clearly documented.
  - This mode should be off by default in any case for safety. Possibly requiring a special flag or config to enable “write mode,” so that by default the server is read-only (preventing accidental writes).
  - We would target initial writes like adding a new entry to a page (perhaps appending textual entries), or updating an existing text entry. More complex operations (deleting entries, uploading files) can come later.
  - For each write, we’d log the change and ideally the content that was written (for audit, maybe storing the content in logs or a diff).

- **Version History Retrieval:** Add support to fetch past versions of pages or entries:

  - Possibly a command or resource like `labarchives://entry/{entryId}/history` that lists version timestamps, and then a `read` on a specific version. If LabArchives API has an endpoint for this (they do store every version), we’d integrate that.
  - This would let an AI or user query “what changed on this page over time”. It’s a powerful feature for research provenance.
  - Implementation would require figuring out how LabArchives exposes revisions (maybe an API method returns all versions of an entry or page). We then present those as either a combined diff or separate entries.
  - This might be Phase 3, but it’s flagged as important for completeness.

- **Enhanced Search and Query Tools:** (Not mentioned in original requirements but a logical future step) Provide a way to search within LabArchives content via the MCP server. LabArchives might not have a great API search, but we could implement a simple local search on fetched data or use LabArchives’ reports if available. This would allow queries like “find entries mentioning X”. This would likely be implemented as an MCP *tool* (because it’s an operation returning a result, not a static resource).

- **Multi-Notebook or Multi-User Support:** In future, allow the server to handle multiple notebooks or even multiple user accounts at once. For instance, a lab PI might want to aggregate data from all team notebooks. This would involve handling multiple credentials/sessions. It’s complex and out of MVP scope, but possible down the line (especially if the tool is run as a shared service). For now, one instance = one user context.

- **Refinements in Output Formatting:** As we gather feedback, we might adjust the JSON structure or add options for formatting (like a plaintext summary of a page in addition to raw content, if that helps the LLM). We’ll consider compliance with any evolving MCP conventions on how data is presented to models for best results.

- **Performance Improvements:** If the MVP reveals any slow points (maybe listing 1000 pages is slow), we might introduce caching. For example, cache the list of notebooks on first call (since they don’t change often) or cache page content for a short period during a session to avoid repeated API calls if the user re-reads the same page. Any caching must be memory-only and respect user actions (maybe clear cache on any indication of update, etc.). For now, performance was acceptable if each call directly hits the API, but scaling up might need this.

- **Continuous Integration & Testing:** Set up CI (like GitHub Actions) to run tests on each commit, ensuring future changes don’t break existing functionality. Also possibly test against multiple Python versions.

- **Community Contributions:** Encourage others to contribute. For instance, others might add support for different output modes or help maintain it. Listing the project on the **MCP Marketplace** (a community site for MCP servers) could help. The team will consider doing that once the MVP is stable.

The above roadmap ensures that while the MVP is focused and delivered quickly, there is a clear path for the project’s evolution. By meeting the Week 1 milestones, we achieve a working foundation which can then be iterated on to add those more advanced capabilities.

## License and Deployment Notes

**License:** The LabArchives MCP Server will be released under the **MIT License** (an OSI-approved permissive license). This choice is intentional to maximize adoption and compatibility:

- The MIT license allows integration into other projects or internal tools without copyleft constraints, which is suitable for academic or enterprise environments that might want to customize the tool.
- It aligns with the licensing of the Model Context Protocol SDK (which is MIT) and the LabArchives API wrapper (also MIT), avoiding any license conflicts.
- We will include the full license text in the repository and inside the package distribution. All new contributions will be under the same license. We’ll also include a note in the README about the license and a disclaimer that the tool is not officially provided by LabArchives or Anthropic (to clarify it’s a community/open-source tool).

**Deployment Options:** Users will have multiple ways to deploy/run the server:

- **Python Package:** We will structure the code as a Python package (with a [setup.py](http://setup.py) or pyproject.toml). The easiest deployment is via pip. We intend to publish the package to PyPI (e.g., under the name `labarchives-mcp`). If publishing within one week is not feasible, users can still install from source:

  ```bash
  git clone https://github.com/ourorg/labarchives-mcp-server.git  
  pip install ./labarchives-mcp-server
  ```

  This will install all dependencies and the `labarchives-mcp` CLI entrypoint. In the repo, we’ll pin dependency versions known to work (e.g., `mcp==X.Y.Z` version).

- **Executable Script:** For users who prefer not to deal with Python environment, we might provide a single-file executable using a tool like PyInstaller. This could bundle the Python interpreter and our code into a binary for a specific OS. Given time constraints, this is optional, but it’s a way to make usage as simple as downloading an executable and running it. We’d have to create separate builds for Windows, Mac, Linux. This might be considered after the initial release if demand arises.

- **Docker Container:** We will create a Docker image to encapsulate the environment. The Dockerfile will likely use a lightweight Python base (e.g., python:3.11-slim). It will copy our code, install dependencies, and set the default entrypoint to `labarchives-mcp`. We’ll also allow overriding the command, so users can pass in credentials or options via Docker run. For example:

  ```bash
  docker run -d --name labarchives_mcp \
    -e LABARCHIVES_AKID=... -e LABARCHIVES_SECRET=... \
    -p 4000:4000 \ 
    ourorg/labarchives-mcp:latest
  ```

  We might not expose any port (since communication is local), so the `-p` is not needed unless we implement a network transport. In many cases, as shown earlier, the Claude config will directly call Docker to run the container with `-i` flag (interactive). We will test the container to ensure it runs properly (especially that it stays running and doesn’t exit immediately due to needing an interactive session – using `-i` ensures it stays up to receive JSON-RPC on stdin).

  We’ll host the image on Docker Hub or GitHub Container Registry for easy access. A link or pull command will be provided in the README.

- **Running as a Service:** If a lab wants this server running continuously (for multiple sessions), they can deploy it on a local server or workstation. It doesn’t consume much resources when idle. We will advise in docs that if running on a shared machine, to secure it (since if someone could connect to its MCP port or stdio, they could possibly read data). However, typically each user will run their own instance on their own machine with Claude Desktop.

- **Configuration Management:** Provide guidance on how to store the required credentials securely:

  - For example, they might put environment exports in their shell profile (not ideal if token changes often). Alternatively, they can create a small script that prompts for the token then launches the server (for those concerned about leaving token in plain text).
  - If using Docker, they might use Docker secrets or environment variables. We will include a note: *“Be cautious not to hard-code sensitive tokens in any shared config files or commit them to version control.”* This is a user education point, not a technical requirement, but worth mentioning.

- **Claude Desktop Setup:** As part of deployment notes, clearly explain how to integrate with Claude:

  - Edit the `claude_desktop_config.json` to include the new server. Provide an example snippet as in CLI design section.
  - If using the Docker method, the config’s command might be `docker` and args as in the Docker blog example (ensuring to include `-e` for env variables in args if not directly baked into image).
  - Mention that after editing config, Claude Desktop needs a restart. Also mention the user will see a new “hammer” or tool icon in the Claude UI (which is how Claude indicates MCP tools availability), and they may need to click it or look in a specific menu to use the LabArchives integration.

- **Consent and User Agreement:** Since the tool will be handling potentially sensitive data, make sure during deployment to highlight user consent:

  - The user is implicitly consenting to letting the LLM see any data this server provides. They should scope appropriately and supervise the LLM’s usage. Claude will double-check with them as well.
  - We might include a startup log or message like “Ensure you have permission to use these notebook contents with an AI model. Data accessed: \[Notebook XYZ\]”.

- **Maintenance and Updates:**

  - Outline how updates will be delivered (e.g., via pip update or pulling new Docker image). Because MCP and LabArchives might evolve, we should ensure users can update easily. Using pip (`pip install -U labarchives-mcp`) or pulling a new container tag is straightforward.
  - We will version our releases with semantic versioning. Minor updates for new features, patch for bug fixes, etc. The license and open-source nature mean users can also fork or modify if they need something urgently.

- **Support:** Provide contact info or link to an issues page for bug reports. Since this is likely internally driven, it might just be via the GitHub issues. If the target lab team has questions, they can reach out to the developer or maintainers.

- **Limitations:** Document any known limitations in deployment notes:

  - e.g., “This MVP does not support writing to LabArchives or accessing version history. Use of external tokens requires manual regeneration every hour (if your institution enforces that) – plan accordingly to refresh the token and restart the server for long sessions.”
  - Also, if the LabArchives API has rate limits, mention that heavy use might trigger those, and the server does not yet implement a sophisticated handling for it beyond basic waiting.
  - If any content types are not well-handled (maybe sketches or certain entry types might not render well in JSON), list them to manage expectations.

- **Security Considerations in Deployment:**

  - If deploying on a server, one might consider running the MCP server under a service account that has limited LabArchives access (maybe a dedicated API user). However, LabArchives likely ties API calls to user accounts, so typically the user’s own access is used.
  - We’ll note that stopping the server when not in use is wise, so no lingering process holds the token (especially if token is short-lived, it might expire anyway).
  - If multiple people use the same machine with Claude and our tool, each one would ideally run their own instance with their own token to avoid cross-access. (The config can be user-specific.)

Finally, deployment will be considered successful when a user can, with provided instructions:

1. Install the tool (via pip or Docker),
2. Provide their credentials safely,
3. Launch the server,
4. Configure Claude (or other MCP client) to connect,
5. And successfully retrieve data.

All of this within a day’s work at most for the user, which is in line with the goal of having a lab team spin this up quickly.

---

**References:** The development of this PRD and the proposed solution references Anthropic’s announcement of MCP and documentation on MCP’s design, ensuring our implementation aligns with the open standard. We also consulted LabArchives API usage examples to design the authentication and data retrieval processes. The Docker and community discussions on MCP servers influenced our thoughts on containerization and integration with Claude Desktop. All these inform a solution that is cutting-edge yet practical for immediate use.