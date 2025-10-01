---
title: 'LabArchives MCP Server: AI Integration for Electronic Lab Notebooks'
tags:
  - Python
  - electronic lab notebook
  - model context protocol
  - AI assistants
  - research data management
  - semantic search
authors:
  - name: Samuel N. Brudner
    orcid: 0000-0000-0000-0000
    affiliation: 1
affiliations:
 - name: Molecular, Cellular, and Developmental Biology, Yale University, USA
   index: 1
date: 30 September 2025
bibliography: paper.bib
---

# Summary

Electronic lab notebooks (ELNs) are essential tools for modern research data management, providing digital alternatives to traditional paper notebooks. However, researchers often struggle to efficiently search, retrieve, and integrate historical experimental data into ongoing analyses. `lab_archives_mcp` bridges this gap through two complementary components: (1) a Model Context Protocol (MCP) server that connects AI assistants to LabArchives—a widely adopted commercial ELN platform—and (2) a modular, backend-agnostic vector database framework for semantic search. This dual architecture enables researchers to conversationally query their lab notebooks, perform semantic searches across experimental records using configurable embedding models and vector indices, and seamlessly incorporate lab data into AI-assisted research workflows. The vector backend is designed as a standalone library, usable independently of the MCP server for custom search pipelines.

# Statement of Need

Research laboratories generate vast amounts of structured and unstructured data stored in ELNs. While ELNs excel at organizing and archiving experimental records, extracting insights from historical data remains challenging. Researchers typically rely on manual keyword searches or must reconstruct experimental contexts from memory. This friction becomes particularly acute when:

1. **Cross-referencing experiments**: Finding related protocols, reagents, or observations across multiple notebook pages
2. **Onboarding new lab members**: Searching for institutional knowledge buried in years of lab records
3. **Reproducing analyses**: Locating specific experimental parameters or conditions from past work
4. **Writing manuscripts**: Retrieving methodological details documented months or years earlier

Recent advances in large language models (LLMs) and AI assistants have demonstrated powerful capabilities for natural language interaction with structured data [@brown2020language; @openai2023gpt4]. However, ELN platforms have remained largely isolated from these AI tools, requiring researchers to manually copy-paste content between systems.

`lab_archives_mcp` addresses this gap by implementing a read-only MCP server [@anthropic2024mcp] that exposes LabArchives notebooks to AI assistants like Claude Desktop and Windsurf. The software enables researchers to:

- Query notebooks using natural language (e.g., "Which fly lines did I use in navigation experiments last summer?")
- Perform semantic searches across all notebook content using vector embeddings
- Navigate notebook hierarchies programmatically through structured API access
- Maintain reproducible research workflows with proper authentication and error handling

# Design and Implementation

## Architecture

`lab_archives_mcp` consists of four primary components:

1. **Authentication Layer** (`auth.py`): Implements HMAC-SHA512 request signing for the LabArchives REST API, OAuth-based user ID resolution, and secure credential management
2. **API Client** (`eln_client.py`): Provides async HTTP methods for listing notebooks, navigating page hierarchies, and reading entry content, with automatic XML→JSON transformation using Pydantic models [@pydantic]
3. **MCP Server** (`mcp_server.py`): Exposes notebook operations as MCP tools using the FastMCP framework [@fastmcp], enabling AI assistants to invoke API methods through natural language
4. **Vector Backend** (`vector_backend/`): A modular semantic search framework with configurable text chunking strategies, embedding model abstraction (OpenAI, extensible to local models), and backend-agnostic vector index operations supporting Pinecone [@pinecone] and Qdrant. This component is designed as a standalone library with Hydra-based configuration management [@hydra], enabling researchers to find conceptually related content beyond keyword matching and integrate semantic search into custom pipelines independent of the MCP server.

## Key Features

**Secure API Integration**: All requests are signed using LabArchives API credentials with HMAC-SHA512, ensuring secure access without exposing passwords. The authentication flow supports both temporary password tokens and OAuth-based UID resolution.

**Structured Data Access**: The software transforms LabArchives' XML API responses into validated JSON schemas using Pydantic, providing type-safe interfaces and comprehensive error handling. All API responses are normalized into consistent Python dataclasses.

**Reproducible Environments**: The project uses conda-lock to pin all dependencies, ensuring bit-for-bit reproducibility across development, testing, and production environments. This approach aligns with FAIR data principles [@wilkinson2016fair] for computational research.

**Modular Semantic Search Framework**: The vector backend provides a flexible, configuration-driven pipeline for semantic search with pluggable components—text chunking (token-aware with configurable overlap), embedding generation (OpenAI API with retry logic, extensible to sentence-transformers), and vector storage (Pinecone, Qdrant, or local Parquet). Researchers can search notebooks by concept rather than exact keywords; for example, querying "olfactory navigation behavior" retrieves relevant pages using terminology like "odor-guided flight" or "chemotaxis assays." The framework is usable as a standalone library for custom search implementations beyond the MCP integration.

**Experimental Upload Support**: An experimental upload API allows researchers to archive computational outputs (notebooks, figures, analysis scripts) directly to LabArchives with Git provenance metadata, supporting reproducible research workflows.

## Testing and Quality Assurance

The codebase maintains comprehensive test coverage with unit tests for all API methods, integration tests against live LabArchives instances (skipped in CI without credentials), and property-based tests using Hypothesis [@hypothesis] for numeric operations. Pre-commit hooks enforce code quality through Ruff linting, Black formatting, isort import sorting, and mypy type checking.

Continuous integration via GitHub Actions runs the test suite on macOS across Python 3.11 and 3.12. The package is developed and tested primarily on macOS, though the use of Conda for environment management and platform-agnostic dependencies should facilitate portability to Linux systems.

# Usage Example

After configuring LabArchives API credentials, researchers interact with their notebooks through AI assistants:

```
Researcher: "What protocols did I use for mosquito navigation experiments?"

Claude (via MCP): [calls list_labarchives_notebooks(), then
                   list_notebook_pages("Mosquito Navigation"), then
                   read_notebook_page(page_id="protocols")]

Claude: "Your Mosquito Navigation notebook contains three main protocols:
1. Wind tunnel setup with IR tracking
2. Odor delivery system calibration
3. Flight trajectory analysis pipeline
The most recent version was updated on August 15, 2025."
```

This conversational interface reduces the cognitive overhead of manual search and enables rapid knowledge retrieval.

# Comparison to Existing Tools

While commercial ELN platforms (LabArchives, Benchling, eLabFTW) provide web APIs, existing open-source tools have focused primarily on ELN data export [@elabjournalapi] or laboratory information management systems (LIMS) integration [@openlims]. To our knowledge, no publicly available tools expose commercial ELN platforms to AI assistants through standardized protocols like MCP.

The Model Context Protocol is a recently introduced standard for connecting AI systems to external data sources [@anthropic2024mcp]. `lab_archives_mcp` represents an early academic application of this protocol for research data management, demonstrating a reusable pattern for integrating institutional data systems with AI assistants through both standardized MCP interfaces and modular vector search infrastructure.

# Acknowledgements

This work was performed independently by the author, and validated against a LabArchives account at Yale University. The author thanks LabArchives for API documentation and technical support, and the FastMCP and Anthropic teams for the Model Context Protocol specification.

# References

[1] Anthropic, Inc. (2024). Model Context Protocol. https://www.anthropic.com/mcp
[2] LabArchives. (2024). LabArchives API Documentation. https://www.labarchives.com/api
