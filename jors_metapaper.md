---
title: Integrating AI Assistants with Electronic Lab Notebooks using the LabArchives Model Context Protocol Server
authors:
  - name: Samuel N. Brudner
    orcid: 0000-0002-6043-9328
    affiliation: 1
affiliations:
  - name: Molecular, Cellular, and Developmental Biology, Yale University, USA
    index: 1
date: 23 November 2025
abstract: >-
  Research labs increasingly rely on electronic lab notebooks (ELNs) such as LabArchives to manage experimental records, yet these systems remain largely siloed from modern AI assistants. Researchers still copy–paste protocols and results between ELNs and AI tools, and often fall back on brittle keyword search when trying to find historical experiments, parameters, or methods. lab_archives_mcp addresses this gap by (i) exposing LabArchives notebooks, pages, and entries as tools under the Model Context Protocol (MCP), and (ii) providing a configurable vector search backend for semantic retrieval over notebook content. Together, these components allow AI assistants to navigate notebooks, perform concept‑level search, maintain multi‑session project contexts, and archive computational outputs with rich provenance metadata, without duplicating ELN records outside institutional infrastructure.
bibliography: paper.bib
---

# 1. Overview

As AI capabilities advance, context-aware architectures have the potential to participate in scientific research as cognitive assistants. To be most helpful, these systems need information about the past and ongoing work of the lab. For this reason, **context engineering**—the deliberate structuring of information for AI systems—will become an increasingly important aspect of laboratory operations.

Electronic Lab Notebooks (ELNs) serve as central repositories for research data and laboratory records, while Large Language Models (LLMs) offer powerful interfaces for querying complex information. These systems are often disconnected: ELN records are siloed within their platforms, and LLMs are restricted to their pre-trained knowledge.

`lab_archives_mcp` addresses this gap by providing a Model Context Protocol (MCP) server that connects AI assistants to LabArchives, a widely used commercial ELN [@anthropic2024mcp]. The server exposes notebooks, pages, and entries as typed tools, provides a modular vector backend for semantic search, and maintains persistent project contexts with graph-based provenance tracking. LabArchives was selected as the integration target because it is a dominant platform in academic research with widespread institutional licensing (e.g., at Yale University, Cornell, Caltech), offers a comprehensive and documented API, and provides a hierarchical structure (Notebooks > Pages > Entries, with folder organization) that maps naturally to file-system-like navigation. The result is a system that allows AI assistants to navigate notebooks, perform concept-level search, maintain multi-session project contexts, and archive computational outputs with rich provenance metadata, without duplicating ELN records outside institutional infrastructure.

The intended users are wet-lab researchers, research data management teams, and institutional platform engineers who want to make ELN content available to AI assistants. The main contributions are (i) an MCP-based connector for LabArchives that can serve as a template for other ELNs and LIMS, (ii) a reusable vector search backend that can be adopted independently of LabArchives for institutional retrieval-augmented generation (RAG) workflows, and (iii) a graph-based state management layer that models research context as a persistent network of pages and findings.

# 2. Implementation and Architecture

`lab_archives_mcp` is organized into five primary components that separate authentication, API access, MCP integration, semantic search, and persistent state management. This modular structure is intended to support both direct reuse and adaptation to other ELNs.

```mermaid
graph LR
    Assistant[AI Assistant] <--> MCP[lab_archives_mcp\n(Auth + Client + Vector + State)]
    MCP <--> API[LabArchives API]
```

1. **Authentication layer (`auth.py`)**
   - Implements HMAC-SHA512 request signing for the LabArchives REST API [@labarchives].
   - Manages secure credential loading from configuration files or environment variables.
   - Provides user ID (UID) resolution flows based on temporary password tokens or browser-based login.

2. **API client (`eln_client.py`)**
   - Wraps the LabArchives API using an async HTTP client.
   - Provides methods for listing notebooks, traversing page hierarchies, and reading entries.
   - Translates XML responses into validated JSON using Pydantic models, ensuring consistent schemas for notebooks, pages, and entries [@pydantic].

3. **MCP server (`mcp_server.py`)**
   - Exposes notebook operations as MCP tools using the FastMCP framework [@fastmcp].
   - Publishes self-describing tool schemas so AI assistants can autonomously decide when and how to call them.
   - Groups tools into four main categories: **Discovery** (`list_notebooks`, `list_pages`), **Reading** (`read_page`), **Search** (`search_labarchives`), and **Index Management** (`sync_vector_index`). An experimental `upload_to_labarchives` tool enables upload of artefacts with provenance metadata.

4. **Vector backend (`vector_backend/`)**
   - Implements a configuration-driven pipeline for semantic search.
   - Supports pluggable text chunking strategies, embedding providers, and vector indices (including Pinecone, Qdrant, and local Parquet-based storage).
   - Uses Hydra-based configuration so that chunking parameters, model choices, and storage backends are declared in YAML rather than hard-coded [@hydra].
   - The `sync_vector_index` tool uses a persisted build record to decide between skipping, incrementally updating, or fully rebuilding an index when embedding configurations or model versions change, enabling reproducible and efficient maintenance of large notebook indices.

5. **State management layer (`state.py`)**
   - Maintains persistent project contexts that scope multi-session research work.
   - Models project state as a NetworkX graph, tracking relationships between pages, findings, and projects, persisted by default to `~/.labarchives_state/session_state.json`.
   - Publishes MCP tools for project lifecycle (`create_project`, `list_projects`, `switch_project`, `delete_project`), evidence capture (`log_finding`, `get_current_context`), and graph navigation (`get_related_pages`, `trace_provenance`), transforming the server from a stateless API wrapper into a stateful research assistant.

6. **Upload and provenance layer (`models/upload.py`, `upload_to_labarchives`)**
   - Provides a high-level upload API for archiving computational artefacts (e.g. Jupyter notebooks, figures, scripts) directly into LabArchives pages.
   - Captures rich provenance metadata via Pydantic models, including Git commit SHA and branch, repository URL, execution timestamp, Python version, dependency versions, operating system, and optional host information.
   - Stores this metadata alongside the uploaded file in LabArchives, enabling durable links between notebook entries and the exact code and environment that produced them.

The vector backend and state management layer are intentionally packaged as reusable components: institutions that do not use LabArchives can still adopt them for RAG pipelines and stateful agent architectures over other content sources.

## 2.1 Agent State Management and Project Contexts

Beyond basic API access and semantic search, `lab_archives_mcp` implements a persistent **state management layer** (`state.py`) that allows AI assistants to maintain long-running research contexts. Similar approaches have been used in MCP servers dedicated to task management (e.g., the "Beads" system for agentic issue tracking [@beads]).

- **Project contexts**: Researchers can create named projects (via `create_project`) that scope all subsequent interactions. Each project tracks visited pages, logged findings, and linked notebook IDs, providing the assistant with a coherent "workspace" for multi-session research tasks.
- **Persistence**: State is persisted to `~/.labarchives_state` as JSON, ensuring that findings and navigation history survive server restarts and are accessible across different working directories. This allows assistants to "remember" prior work and resume investigation seamlessly, even when switching between different codebases or projects.
- **Scoped memory**: When an active project exists, page visits (via `read_notebook_page`) and user-annotated findings (via `log_finding`) are logged to it, creating an audit trail and enabling reflection on what has been explored. Without an active project, visits are silently ignored and findings will error.

This design transforms the MCP server from a stateless API wrapper into a **stateful research assistant** that can maintain continuity across complex, multi-day investigations.

## 2.2 Graph-Based Knowledge Navigation

To support semantic exploration of notebook content, `lab_archives_mcp` integrates **NetworkX** to model project contexts as directed graphs. Pages, findings, and projects are represented as nodes, with edges capturing relationships such as "visited during project" and "finding discovered on page."

- **Graph construction**: As the assistant reads pages and logs findings, the graph is incrementally updated and persisted alongside the project state.
- **Relational queries**: The `get_related_pages` tool leverages graph traversal to identify "sibling" pages (those sharing a common project node) and parses HTML content for explicit LabArchives links, surfacing connections that are not obvious from hierarchical navigation alone.
- **Provenance tracing**: The `trace_provenance` tool implements heuristics to identify the origin of specific entries, searching for "Derived From" patterns in content and inspecting metadata entries created by the `upload_to_labarchives` tool.

This graph-based approach enables the assistant to **navigate semantically** rather than purely hierarchically, discovering related content via shared context rather than relying solely on folder structure.

## 2.3 Onboarding and Agent Instruction

The MCP server includes an **onboarding payload system** (`onboard.py`) that generates structured instructions for AI assistants upon initialization. This payload describes:

- **When to use the server**: Scenarios such as "user mentions experiments, protocols, results" or "user wants to start a long-running research task."
- **Primary tools**: A curated list of tools (`create_project`, `search_labarchives`, `log_finding`) with usage guidance, prioritizing semantic search as the default entry point.
- **Workflow hints**: Recommendations such as "Use semantic search as your primary entry point."

This onboarding layer ensures that assistants are **contextually aware** of the MCP server's capabilities from the outset, rather than treating it as an opaque API. Researchers can inspect the onboarding payload via `labarchives-mcp --print-onboard markdown`, making the server's behavior transparent and auditable.

## 2.4 Security and Governance Controls

To support deployment in institutional environments with strict data governance requirements, the server implements several layers of security control beyond basic authentication:

- **Namespace Isolation**: When using shared vector stores (e.g., Pinecone or Qdrant), the server supports strict namespace isolation. Embeddings are scoped to specific tenants or notebooks, preventing cross-user data leakage.
- **Write Control**: The upload functionality can be globally disabled via the `LABARCHIVES_ENABLE_UPLOAD=false` environment variable, allowing administrators to deploy read-only instances for safety.
- **Data Sovereignty**: The vector backend supports a **local Parquet** storage option. When combined with locally hosted embedding models, this ensures that research data never leaves the institution's infrastructure, keeping all vector embeddings and metadata on-premise (e.g., on a secure research file server) rather than sending data to third-party cloud services.
- **Credential Scoping**: Access to the LabArchives API is scoped via standard API keys and user IDs, ensuring that the MCP server operates with the exact permissions of the authenticated user.

# 3. Quality Control

The project employs both automated and manual quality control measures aimed at making the MCP server safe to reuse and extend.

The automated test suite includes unit tests for authentication, notebook navigation, and vector‑backend components, as well as integration tests that exercise full workflows (listing notebooks, reading pages, running semantic search, and performing uploads) against a live LabArchives account when credentials are available. It also covers the new state management layer (project creation/switching, graph persistence, related-page heuristics, and next-step heuristics). Continuous integration via GitHub Actions runs these tests on Linux and macOS for Python 3.11+, installing the project via the pinned conda‑lock environment so that tests exercise the same dependency set recommended for users.

In addition to automated checks, the MCP server has been tested against real LabArchives notebooks from an institutional account, verifying notebook listing, navigation, semantic search behaviour, and upload workflows.

# 4. Availability

- **Operating systems and languages**
  - Implemented in Python (3.11+), with automated testing on Linux and macOS.

- **Source code repository**
  - Public Git repository: <https://github.com/SamuelBrudner/lab_archives_mcp>
  - Default development branch: `main`

- **Archived version**
  - Zenodo: <https://doi.org/10.5281/zenodo.17728480>
  - Git tag: `v0.3.1`

- **License**
  - Distributed under the MIT License.

- **Support and contributions**
  - Issues and feature requests are tracked via the GitHub issue tracker.
  - Contribution guidelines, including development setup, testing, and release procedures, are documented in `CONTRIBUTING.md`.

# 5. Reuse Potential

The design of `lab_archives_mcp` prioritizes reuse at three levels: as a concrete connector for LabArchives, as a reference architecture for ELN/AI integration, and as a set of reusable agent design patterns.

## 5.1 Comparison to existing solutions

While LabArchives and other ELN platforms expose REST APIs for CRUD operations, these interfaces typically rely on keyword search and leave indexing, semantic retrieval, and AI integration as downstream implementation details. Existing open‑source tools focus on exporting ELN data or integrating ELNs into LIMS workflows rather than exposing them directly to AI assistants. In contrast, `lab_archives_mcp` provides an MCP‑native connector that publishes LabArchives notebooks, pages, and entries as typed tools discoverable by AI assistants, together with a configuration‑driven semantic search backend. To our knowledge, this represents one of the first academic applications of the Model Context Protocol to research data management and offers a reusable pattern for bringing institutional ELNs and AI assistants into a single architecture.

## 5.2 Template for other ELN and LIMS systems

- The separation between authentication, API client, MCP server, vector backend, and state management allows developers to replace only the `eln_client.py` layer when targeting a different ELN or LIMS.
- The same MCP tooling patterns (list resources, read pages, search, upload), state management layer (`state.py`), and graph-based navigation can be reused, facilitating consistent assistant behaviour across multiple systems.
- Developers adapting this architecture to other systems (e.g. BioRAFT, Benchling, or eLabFTW) can preserve the project context abstraction and graph navigation logic while swapping out only the underlying API calls.

## 5.3 Standalone vector backend

- The vector backend can be used independently of LabArchives to build institutional RAG pipelines over other content types, such as lab wikis or institutional repositories.
- Hydra-managed configuration makes it straightforward to tune chunking, embedding models, and storage backends for new domains without modifying code.

## 5.4 Reusable agent architecture patterns

- The **state management layer** (`state.py`) provides a general-purpose pattern for maintaining assistant memory across sessions, applicable to any MCP server that needs to track long-running tasks.
- The **graph-based navigation** approach (using NetworkX to model semantic relationships) can be adapted to other domains where content relationships extend beyond hierarchical structure (e.g. citation networks, experimental lineages, or institutional knowledge graphs).
- The **onboarding payload system** (`onboard.py`) offers a transparent, inspectable way to instruct assistants about server capabilities, reducing reliance on implicit prompt engineering.

## 5.5 Institutional deployment patterns

- Research data management teams can deploy the MCP server as part of an institutional AI assistant, exposing ELN content under existing authentication and logging policies.
- The project documents multiple deployment options for the vector backend, including local Parquet persistence and self-hosted vector stores, allowing institutions to keep embeddings and metadata on-premise when required.
- The state management layer operates entirely locally (`~/.labarchives_state` directory), ensuring that research context and findings remain under institutional control even when vector embeddings are delegated to third-party services. The use of a home-directory location allows researchers to access the same project contexts regardless of which repository or working directory they are in.

## 5.6 Limitations and constraints

- Full functionality requires access to the LabArchives API; institutions using other ELNs would need corresponding API access to build similar connectors.
- When external vector stores (e.g. managed Pinecone or Qdrant instances) are used, embeddings and possibly derived text are stored on third-party infrastructure, introducing an additional data custody layer. Local and self-hosted options are provided for deployments that require stricter control.
- The graph-based navigation and heuristics layers assume that assistants will engage in exploratory, multi-session research tasks; for simple, one-off queries, the overhead may not be justified.

# 6. Illustrative Example

Once credentials are configured and the MCP server is registered with an AI assistant, researchers can query their notebooks conversationally. For example:

```text
Researcher: "I'm starting a new analysis of the mosquito wind tunnel data. Create a project for this."

Assistant: [calls create_project(name="Mosquito Analysis", description="Wind tunnel data analysis")]
"Project 'Mosquito Analysis' created. I'm ready to help."

Researcher: "Find the calibration protocols we used last summer."

Assistant: [calls search_labarchives("wind tunnel calibration protocol summer 2024")]
[calls read_notebook_page(page_id="12345")]
"I found the 'Wind Tunnel Calibration (Aug 2024)' page. It details the IR tracking setup."

Researcher: "Log that as a key finding, and check if there are any related experiment runs linked to it."

Assistant: [calls log_finding(content="Calibration protocol from Aug 2024 uses IR tracking", page_id="12345")]
[calls get_related_pages(page_id="12345")]
"Finding logged. I also found three linked experiment pages: 'Run 14', 'Run 15', and 'Run 16' that cite this calibration."
```

In this workflow, the assistant explicitly manages the research context by creating a project, then uses semantic search to find entry points. By logging findings and traversing the graph, it builds a persistent model of the investigation that can be resumed in future sessions. Similar conversations can drive related queries (e.g. "Find experiments related to olfactory navigation behaviour") and upload new analysis artefacts with provenance metadata.

# 7. Funding and Acknowledgements

This work was performed independently by the author and tested against a LabArchives account at Yale University. The author thanks LabArchives for API documentation and technical support, and the FastMCP and Anthropic teams for the Model Context Protocol specification and reference implementations.

# 8. References

References are managed via the shared `paper.bib` file and are not duplicated here. The reference list for this metapaper should include works cited in the sections above, including the MCP specification, Hydra, Pydantic, FAIR principles, and any vector store or LLM providers referenced in the implementation and reuse discussions.
