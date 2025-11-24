# Graph-Based State Management ("The Lab Brain")

`lab_archives_mcp` transforms the LabArchives ELN from a static repository into a dynamic "Lab Brain" by maintaining a persistent, graph-based context of the user's research activities. This allows AI assistants to reason about relationships between experiments, findings, and notebooks across multiple sessions.

## The "Lab Brain" Concept

Traditional ELN integrations are stateless: an assistant retrieves a page, answers a question, and forgets everything immediately. This prevents long-running investigations where an assistant needs to "remember" what it read yesterday or connect a finding in Notebook A to a protocol in Notebook B.

This MCP server solves this by maintaining a **Project Context**—a local, persistent knowledge graph that tracks:
1.  **What has been read** (Page visits)
2.  **What has been learned** (Logged findings)
3.  **How items are related** (Semantic and structural links)

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
| `HAS_FINDING` | Project | Finding | Connects a finding to the active project. |
| `VISITED` | Project | Page | Records that a page was read during this project. |
| `LINKED_TO` | Finding | Page | (Optional) Provenance link from a finding to its source page. |

## Agent Heuristics

The server exposes tools that leverage this graph to guide the AI assistant:

### `suggest_next_steps`
Analyzes the current graph topology to recommend actions:
- **Cold Start**: If the graph is empty, suggests searching for key terms in the project description.
- **Exploration**: If many pages are visited but few findings logged, suggests synthesizing information.
- **Convergence**: If many findings are logged, suggests formulating a hypothesis or experiment.

### `get_related_pages`
Finds pages related to the current page by traversing the graph:
- **Structural**: Pages in the same folder.
- **Temporal**: Pages visited in the same session.
- **Semantic**: Pages with high vector similarity (if vector search is enabled).

## Persistence

The graph is serialized to JSON and stored locally in `~/.labarchives_state/session_state.json`. This ensures data sovereignty—the "brain" lives on your machine, not in the cloud—and allows the context to survive server restarts.
