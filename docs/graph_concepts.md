# Graph-Based State Management ("The Lab Brain")

`lab_archives_mcp` transforms the LabArchives ELN from a static repository into a dynamic "Lab Brain" by maintaining a persistent, graph-based context of the user's research activities. This allows AI assistants to reason about relationships between experiments, findings, and notebooks across multiple sessions.

## The "Lab Brain" Concept

Traditional ELN integrations are stateless: an assistant retrieves a page, answers a question, and forgets everything immediately. This prevents long-running investigations where an assistant needs to "remember" what it read yesterday or connect a finding in Notebook A to a protocol in Notebook B.

This MCP server solves this by maintaining a **Project Context**—a local, persistent knowledge graph that tracks:
1.  **What has been read** (Page visits)
2.  **What has been learned** (Logged findings)
3.  **How items are related** (Project, content-link, and provenance edges)

**Note**: Projects are explicit. Create one with `create_project()` before logging visits or findings so state is persisted in a single context. The MCP tool surface does not expose an implicit default-project creator; without an active project, page visits are ignored and findings return a `no_active_context` error.

## The Graph Model

The state is modeled as a directed graph using `networkx`, where nodes represent research entities and edges represent relationships.

### Nodes

| Node Type | Description | Properties |
| :--- | :--- | :--- |
| **Project** | The root of a research context. | `name`, `description`, `created_at` |
| **Notebook** | A LabArchives notebook referenced by the project. | `notebook_id` |
| **Page** | A LabArchives page that has been visited or created. | `page_id`, `title`, `notebook_id`, `page_url` |
| **Finding** | A key fact or insight logged by the user/agent. | `content`, `source_url`, `timestamp` |
| **Artifact** | Uploaded content associated with a page. | `entry_id`, `filename`, `file_size_bytes` |
| **Activity** | A recorded upload/provenance event. | `executed_at`, Git metadata, Python/environment metadata |
| **User** | The authenticated LabArchives user. | `uid` |
| **Software Agent** | The MCP server that executed the upload. | `identifier`, `server_version` |

### Edges

| Edge Type | Source | Target | Description |
| :--- | :--- | :--- | :--- |
| `uses_notebook` | Project | Notebook | Connects project to notebooks it references. |
| `contains` | Notebook | Page | Links a notebook to pages within it. |
| `visited` | Project | Page | Records that a page was accessed during this project. |
| `tracked` | Project | Activity / Artifact / Page | Marks provenance-bearing records as part of the project state. |
| `discovered` | Project | Finding | Connects findings logged during the project. |
| `evidence_from` | Page | Finding | Provenance link from a page to findings derived from it. |
| `contains_artifact` | Page | Artifact | Links a page to uploaded content recorded on that page. |
| `was_generated_by` | Page / Artifact | Activity | Records that an upload activity generated an entity. |
| `was_attributed_to` | Page / Artifact | User | Captures ownership / authorship provenance. |
| `was_associated_with` | Activity | User / Software Agent | Captures who ran an activity and which software executed it. |

## Agent Heuristics

The server exposes tools that leverage this graph to guide the AI assistant:

### `get_related_pages`
Finds pages related to the current page by traversing the active project graph and parsing links in the current page content:
- **Project siblings**: Other pages connected to the same active project.
- **Content links**: LabArchives page URLs detected inside page entries and persisted as direct `content_link` edges.
- **Graph neighbors**: Other direct page-to-page neighbors if graph edges exist.

The tool returns a paginated response with `items` and `meta` fields. `limit` defaults to `20`, `offset` defaults to `0`, and `meta.truncated` indicates whether more related pages are available.

### `trace_provenance`
Traces evidence for one entry by combining:
- Explicit `Derived From:` or `Source:` text patterns in the entry content.
- Sibling code-provenance metadata entries written by upload workflows.
- Project-graph `evidence_from` edges created when `log_finding(..., page_id=...)` links a finding back to a source page.

### `suggest_next_steps`
Provides lightweight guidance based on project state:
- **No context**: If no project is active, suggests creating one.
- **Cold start**: If the graph has no pages or findings, suggests using `search_labarchives` or `list_notebooks` to get started.
- **Active phase**: Returns stats (pages visited, findings logged) and generic suggestions for continuing work.

The tool provides information, not prescriptive workflow rules. It's designed as a dashboard for the AI to understand current state, not as a director telling it what to do.

## Persistence and Safety

The graph is serialized to JSON and stored locally in `~/.labarchives_state/session_state.json`. This ensures data sovereignty—the "brain" lives on your machine, not in the cloud—and allows the context to survive server restarts.

In `v0.4.0`, the same saved graph can also be exported as JSON-LD through the CLI and MCP server. See `docs/linked_data.md` for the export mapping.
