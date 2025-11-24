# Graph-Based State Management ("The Lab Brain")

`lab_archives_mcp` transforms the LabArchives ELN from a static repository into a dynamic "Lab Brain" by maintaining a persistent, graph-based context of the user's research activities. This allows AI assistants to reason about relationships between experiments, findings, and notebooks across multiple sessions.

## The "Lab Brain" Concept

Traditional ELN integrations are stateless: an assistant retrieves a page, answers a question, and forgets everything immediately. This prevents long-running investigations where an assistant needs to "remember" what it read yesterday or connect a finding in Notebook A to a protocol in Notebook B.

This MCP server solves this by maintaining a **Project Context**—a local, persistent knowledge graph that tracks:
1.  **What has been read** (Page visits)
2.  **What has been learned** (Logged findings)
3.  **How items are related** (Semantic and structural links)

**Note**: Projects are explicit—create one with `create_project()` (or `create_default_context()` if you want a reusable default) before logging visits or findings so state is persisted in a single context. Without an active project, visits are ignored and findings will error.

## The Graph Model

The state is modeled as a directed graph using `networkx`, where nodes represent research entities and edges represent relationships.

### Nodes

| Node Type | Description | Properties |
| :--- | :--- | :--- |
| **Project** | The root of a research context. | `name`, `description`, `created_at` |
| **Finding** | A key fact or insight logged by the user/agent. | `content`, `source_url`, `timestamp` |
| **Page** | A LabArchives page that has been visited. | `page_id`, `title`, `notebook_id` |

### Edges

| Edge Type | Source | Target | Description |
| :--- | :--- | :--- | :--- |
| `uses_notebook` | Project | Notebook | Connects project to notebooks it references. |
| `contains` | Notebook | Page | Links a notebook to pages within it. |
| `visited` | Project | Page | Records that a page was accessed during this project. |
| `discovered` | Project | Finding | Connects findings logged during the project. |
| `evidence_from` | Page | Finding | Provenance link from a page to findings derived from it. |

## Agent Heuristics

The server exposes tools that leverage this graph to guide the AI assistant:

### `get_related_pages`
Finds pages related to the current page by traversing the graph:
- **Structural**: Pages in the same folder.
- **Temporal**: Pages visited in the same session.
- **Semantic**: Pages with high vector similarity (if vector search is enabled).

### `suggest_next_steps`
Provides lightweight guidance based on project state:
- **Cold start**: If the graph is empty (no pages or findings), suggests using `search_labarchives` or `list_notebooks` to get started.
- **Active phase**: Returns stats (pages visited, findings logged) and generic suggestions for continuing work.

The tool provides information, not prescriptive workflow rules. It's designed as a dashboard for the AI to understand current state, not as a director telling it what to do.

## Persistence

The graph is serialized to JSON and stored locally in `~/.labarchives_state/session_state.json`. This ensures data sovereignty—the "brain" lives on your machine, not in the cloud—and allows the context to survive server restarts.
