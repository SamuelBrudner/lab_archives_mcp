---
title: Integrating AI Assistants with Electronic Lab Notebooks using the LabArchives Model Context Protocol Server
authors:
  - name: Samuel N. Brudner
    orcid: 0000-0002-6043-9328
    affiliation: 1
affiliations:
  - name: Molecular, Cellular, and Developmental Biology, Yale University, USA
    index: 1
date: 30 September 2025
bibliography: paper.bib
---

# 1. Overview

Electronic lab notebooks (ELNs) are central to modern research data management, but their contents are often difficult to search and integrate with computational tools. At the same time, large language models (LLMs) and AI assistants have become powerful interfaces for querying structured and semi-structured data. These tools are limited by their access to relevant, private, domain information when formulating their responses. In most institutions, these two systems remain siloed: ELN records live in one platform, while AI assistants leverage knowledge that is baked-in during their training.

`lab_archives_mcp` addresses this gap by providing a Model Context Protocol (MCP) server that connects AI assistants to LabArchives, a widely used commercial ELN, together with a modular, backend-agnostic vector search framework. The MCP server exposes LabArchives notebooks, pages, and entries as typed tools that assistants can discover and invoke. The vector backend provides semantic search over notebook content using configurable text chunking, embedding models, and vector stores.

The intended users are wet-lab researchers, research data management (RDM) teams, and institutional platform engineers who want to make ELN content available to AI assistants without exporting or duplicating notebooks. The main contributions are (i) an MCP-based connector for LabArchives that can serve as a template for other ELNs and LIMS, and (ii) a reusable vector search backend that can be adopted independently of LabArchives for institutional retrieval-augmented generation (RAG) workflows.

We propose that **context engineering**—the deliberate structuring of information for AI systems—will play an increasingly important role in laboratory operations over the coming years. As AI capabilities advance, context-aware architectures have the potential to significantly accelerate research by reducing the cognitive overhead of literature review, experimental protocol retrieval, and provenance tracking, allowing researchers to focus on hypothesis generation and experimental design rather than information archaeology. This work explores these ideas by implementing persistent project contexts, modeling semantic relationships as graphs, and providing metacognitive heuristics that enable assistants to conduct multi-session research investigations.

# 2. Implementation and Architecture

`lab_archives_mcp` is organized into five primary components that separate authentication, API access, MCP integration, semantic search, and persistent state management. This modular structure is intended to support both direct reuse and adaptation to other ELNs.

1. **Authentication layer (`auth.py`)**
   - Implements HMAC-SHA512 request signing for the LabArchives REST API.
   - Manages secure credential loading from configuration files or environment variables.
   - Provides user ID (UID) resolution flows based on temporary password tokens or browser-based login.

2. **API client (`eln_client.py`)**
   - Wraps the LabArchives API using an async HTTP client.
   - Provides methods for listing notebooks, traversing page hierarchies, and reading entries.
   - Translates XML responses into validated JSON using Pydantic models, ensuring consistent schemas for notebooks, pages, and entries.

3. **MCP server (`mcp_server.py`)**
   - Exposes notebook operations as MCP tools using the FastMCP framework.
   - Publishes self-describing tool schemas so AI assistants can autonomously decide when and how to call them.
   - Groups tools into discovery (listing notebooks and pages), reading (retrieving entries), semantic search, and synchronization (index rebuild) operations.

4. **Vector backend (`vector_backend/`)**
   - Implements a configuration-driven pipeline for semantic search.
   - Supports pluggable text chunking strategies, embedding providers, and vector indices (including Pinecone, Qdrant, and local Parquet-based storage).
   - Uses Hydra-based configuration so that chunking parameters, model choices, and storage backends are declared in YAML rather than hard-coded, enabling reproducible and shareable search setups.

5. **State management layer (`state.py`)**
   - Maintains persistent project contexts that scope multi-session research work.
   - Models project state as a NetworkX graph, tracking relationships between pages, findings, and projects.
   - Provides AI-driven heuristics (`suggest_next_steps`) and graph navigation tools (`get_related_pages`, `trace_provenance`) that transform the server from a stateless API wrapper into a stateful research assistant.

The vector backend and state management layer are intentionally packaged as reusable components: institutions that do not use LabArchives can still adopt them for RAG pipelines and stateful agent architectures over other content sources.

## 2.1 Agent State Management and Project Contexts

Beyond basic API access and semantic search, `lab_archives_mcp` implements a persistent **state management layer** (`state.py`) that allows AI assistants to maintain long-running research contexts. This architecture is inspired by "beads" design patterns, where each project represents a scoped unit of work with its own memory.

- **Project contexts**: Researchers can create named projects (via `create_project`) that scope all subsequent interactions. Each project tracks visited pages, logged findings, and linked notebook IDs, providing the assistant with a coherent "workspace" for multi-session research tasks.
- **Persistence**: State is persisted to `~/.labarchives_state` as JSON, ensuring that findings and navigation history survive server restarts and are accessible across different working directories. This allows assistants to "remember" prior work and resume investigation seamlessly, even when switching between different codebases or projects.
- **Scoped memory**: All page visits (via `read_notebook_page`) and user-annotated findings (via `log_finding`) are automatically logged to the active project, creating an audit trail and enabling reflection on what has been explored.

This design transforms the MCP server from a stateless API wrapper into a **stateful research assistant** that can maintain continuity across complex, multi-day investigations.

## 2.2 Graph-Based Knowledge Navigation

To support semantic exploration of notebook content, `lab_archives_mcp` integrates **NetworkX** to model project contexts as directed graphs. Pages, findings, and projects are represented as nodes, with edges capturing relationships such as "visited during project" and "finding discovered on page."

- **Graph construction**: As the assistant reads pages and logs findings, the graph is incrementally updated and persisted alongside the project state.
- **Relational queries**: The `get_related_pages` tool leverages graph traversal to identify "sibling" pages (those sharing a common project node) and parses HTML content for explicit LabArchives links, surfacing connections that are not obvious from hierarchical navigation alone.
- **Provenance tracing**: The `trace_provenance` tool implements heuristics to identify the origin of specific entries, searching for "Derived From" patterns in content and inspecting metadata entries created by the `upload_to_labarchives` tool.

This graph-based approach enables the assistant to **navigate semantically** rather than purely hierarchically, discovering related content via shared context rather than relying solely on folder structure.

## 2.3 AI-Driven Research Heuristics

To guide assistants when they are uncertain what to do next, the MCP server includes a **suggest_next_steps** tool that analyzes the current project graph and proposes logical actions based on predefined heuristics:

- **Cold start**: If the project graph is empty or contains only the project node, the tool suggests initiating exploration via `search_labarchives` or `list_notebook_pages`.
- **Exploration phase**: If pages have been visited but few findings are logged, the tool recommends reading page content or using `get_related_pages` to discover connections.
- **Synthesis phase**: If multiple findings have been accumulated, the tool suggests synthesizing results or creating a summary page.
- **Dead end detection**: If the most recently visited page has no outgoing links or neighbors in the graph, the tool recommends backtracking or searching for related terms.

These heuristics provide a **"ready-to-work" scaffolding** that reduces the cognitive load on assistants when navigating complex, multi-notebook research contexts. Rather than relying solely on user prompts, the assistant can autonomously reflect on its current state and suggest productive next steps.

## 2.4 Onboarding and Agent Instruction

The MCP server includes an **onboarding payload system** (`onboard.py`) that generates structured instructions for AI assistants upon initialization. This payload describes:

- **When to use the server**: Scenarios such as "user mentions experiments, protocols, results" or "user wants to start a long-running research task."
- **Primary tools**: A curated list of tools (`create_project`, `search_labarchives`, `log_finding`, `suggest_next_steps`) with usage guidance, prioritizing semantic search as the default entry point.
- **Workflow hints**: Recommendations such as "Start a project context before conducting multi-session research" and "Use `suggest_next_steps` when uncertain how to proceed."

This onboarding layer ensures that assistants are **contextually aware** of the MCP server's capabilities from the outset, rather than treating it as an opaque API. Researchers can inspect the onboarding payload via `labarchives-mcp --print-onboard markdown`, making the server's behavior transparent and auditable.

# 3. Quality Control

The project employs both automated and manual quality control measures aimed at making the MCP server safe to reuse and extend.

- **Automated testing**
  - Unit tests cover core models, authentication logic, and vector backend components.
  - Integration tests exercise end-to-end workflows against a real LabArchives account when credentials are available, including listing notebooks, reading pages, and running semantic search.
  - An experimental upload tool is tested against small example notebooks to verify that provenance metadata is stored correctly.

- **Pre-commit checks and static analysis**
  - A pre-commit configuration runs Ruff, Black, isort, mypy, and docstring coverage checks on each commit.
  - Commitizen enforces conventional commit messages and release hygiene.

- **Continuous integration**
  - GitHub Actions execute the test suite on multiple operating systems and Python versions (currently Python 3.11+ on Linux and macOS).
  - CI jobs install the project via the pinned conda-lock environment to ensure tests run under the same dependency set as recommended for users.

In addition to automated checks, the MCP server has been tested against real LabArchives notebooks from an institutional account, verifying notebook listing, navigation, semantic search behaviour, and upload workflows.

# 4. Availability

- **Operating systems and languages**
  - Implemented in Python (3.11+), with automated testing on Linux and macOS.

- **Source code repository**
  - Public Git repository: <https://github.com/SamuelBrudner/lab_archives_mcp>
  - Default development branch: `main`

- **Archived version**
  - A versioned snapshot corresponding to the JORS submission will be archived on Zenodo and referenced here via its DOI.
  - The Git tag used for the submission will match the archived version.

- **License**
  - Distributed under the MIT License.

- **Support and contributions**
  - Issues and feature requests are tracked via the GitHub issue tracker.
  - Contribution guidelines, including development setup, testing, and release procedures, are documented in `CONTRIBUTING.md`.

# 5. Reuse Potential

The design of `lab_archives_mcp` prioritizes reuse at three levels: as a concrete connector for LabArchives, as a reference architecture for ELN/AI integration, and as a set of reusable agent design patterns.

- **Template for other ELN and LIMS systems**
  - The separation between authentication, API client, MCP server, vector backend, and state management allows developers to replace only the `eln_client.py` layer when targeting a different ELN or LIMS.
  - The same MCP tooling patterns (list resources, read pages, search, upload), state management layer (`state.py`), and graph-based navigation can be reused, facilitating consistent assistant behaviour across multiple systems.
  - Developers adapting this architecture to other systems (e.g. BioRAFT, Benchling, or eLabFTW) can preserve the project context abstraction and graph navigation logic while swapping out only the underlying API calls.

- **Standalone vector backend**
  - The vector backend can be used independently of LabArchives to build institutional RAG pipelines over other content types, such as lab wikis or institutional repositories.
  - Hydra-managed configuration makes it straightforward to tune chunking, embedding models, and storage backends for new domains without modifying code.

- **Reusable agent architecture patterns**
  - The **state management layer** (`state.py`) provides a general-purpose pattern for maintaining assistant memory across sessions, applicable to any MCP server that needs to track long-running tasks.
  - The **graph-based navigation** approach (using NetworkX to model semantic relationships) can be adapted to other domains where content relationships extend beyond hierarchical structure (e.g. citation networks, experimental lineages, or institutional knowledge graphs).
  - The **AI heuristics layer** (`suggest_next_steps`) demonstrates how MCP servers can provide metacognitive support to assistants, guiding them when uncertain. Similar heuristics could be implemented for other task domains (e.g. code review, literature surveys, or experimental design).
  - The **onboarding payload system** (`onboard.py`) offers a transparent, inspectable way to instruct assistants about server capabilities, reducing reliance on implicit prompt engineering.

- **Institutional deployment patterns**
  - Research data management teams can deploy the MCP server as part of an institutional AI assistant, exposing ELN content under existing authentication and logging policies.
  - The project documents multiple deployment options for the vector backend, including local Parquet persistence and self-hosted vector stores, allowing institutions to keep embeddings and metadata on-premise when required.
  - The state management layer operates entirely locally (`~/.labarchives_state` directory), ensuring that research context and findings remain under institutional control even when vector embeddings are delegated to third-party services. The use of a home-directory location allows researchers to access the same project contexts regardless of which repository or working directory they are in.

- **Limitations and constraints**
  - Full functionality requires access to the LabArchives API; institutions using other ELNs would need corresponding API access to build similar connectors.
  - When external vector stores (e.g. managed Pinecone or Qdrant instances) are used, embeddings and possibly derived text are stored on third-party infrastructure, introducing an additional data custody layer. Local and self-hosted options are provided for deployments that require stricter control.
  - The graph-based navigation and heuristics layers assume that assistants will engage in exploratory, multi-session research tasks; for simple, one-off queries, the overhead of project initialization may not be justified.

# 6. Illustrative Example

Once credentials are configured and the MCP server is registered with an AI assistant, researchers can query their notebooks conversationally. For example:

```text
Researcher: "What protocols did I use for mosquito navigation experiments?"

Assistant (via MCP): [calls semantic_search("mosquito navigation protocols"),
                     inspects the top results for the Mosquito Navigation notebook,
                     then read_notebook_page(page_id="protocols")]

Assistant: "Your Mosquito Navigation notebook contains three main protocols:
1. Wind tunnel setup with IR tracking
2. Odor delivery system calibration
3. Flight trajectory analysis pipeline
The most recent version was updated on August 15, 2025."
```

In this workflow, the assistant first uses semantic search to identify relevant notebook pages, then traverses their structure and aggregates content into a concise answer. Similar conversations can drive related queries (e.g. "Find experiments related to olfactory navigation behaviour") and upload new analysis artefacts with provenance metadata.

# 7. Funding and Acknowledgements

This work was performed independently by the author and tested against a LabArchives account at Yale University. The author thanks LabArchives for API documentation and technical support, and the FastMCP and Anthropic teams for the Model Context Protocol specification and reference implementations.

# 8. References

References are managed via the shared `paper.bib` file and are not duplicated here. The reference list for this metapaper should include works cited in the sections above, including the MCP specification, Hydra, Pydantic, FAIR principles, and any vector store or LLM providers referenced in the implementation and reuse discussions.
