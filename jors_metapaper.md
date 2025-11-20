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

# 2. Implementation and Architecture

`lab_archives_mcp` is organized into four primary components that separate authentication, API access, MCP integration, and semantic search. This modular structure is intended to support both direct reuse and adaptation to other ELNs.

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

The vector backend is intentionally packaged as a standalone component: institutions that do not use LabArchives can still adopt it for RAG pipelines over other content (e.g. institutional repositories or lab wikis), while reusing the same configuration patterns that power the LabArchives integration.

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

The design of `lab_archives_mcp` prioritizes reuse at two levels: as a concrete connector for LabArchives, and as a reference architecture for ELN/AI integration more broadly.

- **Template for other ELN and LIMS systems**
  - The separation between authentication, API client, MCP server, and vector backend allows developers to replace only the `eln_client.py` layer when targeting a different ELN or LIMS.
  - The same MCP tooling patterns (list resources, read pages, search, upload) can be reused, facilitating consistent assistant behaviour across multiple systems.

- **Standalone vector backend**
  - The vector backend can be used independently of LabArchives to build institutional RAG pipelines over other content types, such as lab wikis or institutional repositories.
  - Hydra-managed configuration makes it straightforward to tune chunking, embedding models, and storage backends for new domains without modifying code.

- **Institutional deployment patterns**
  - Research data management teams can deploy the MCP server as part of an institutional AI assistant, exposing ELN content under existing authentication and logging policies.
  - The project documents multiple deployment options for the vector backend, including local Parquet persistence and self-hosted vector stores, allowing institutions to keep embeddings and metadata on-premise when required.

- **Limitations and constraints**
  - Full functionality requires access to the LabArchives API; institutions using other ELNs would need corresponding API access to build similar connectors.
  - When external vector stores (e.g. managed Pinecone or Qdrant instances) are used, embeddings and possibly derived text are stored on third-party infrastructure, introducing an additional data custody layer. Local and self-hosted options are provided for deployments that require stricter control.

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
