# Response to Reviewers

Manuscript: "Integrating AI Assistants with Electronic Lab Notebooks using the LabArchives Model Context Protocol Server"

Revision date: 27 May 2026

This document is organised by reviewer. Reviewer 1's structural comments are addressed first, then Reviewer 2's items, then Reviewer 3's compulsory and minor items. Each entry quotes the reviewer's concern, states whether the manuscript or repository was changed, and identifies the manuscript sections that contain the change. Items where no new content was added carry a `Not changed` label and a justification.

---

## Additional engineering improvements

Between the original submission and this resubmission the codebase was substantially refactored. These changes are not responses to specific reviewer comments; they improve modularity and testability and are described in CHANGELOG v0.5.0 and v0.5.1. The 823-line `StateManager` god object has been decomposed into a `state/` subpackage with six focused services: `ProjectService` for project lifecycle, `KnowledgeGraph` for visit and finding nodes, `ProvenanceService` for upload provenance entries, `GraphValidationService` for graph health checks, `StateRepository` for on-disk persistence, and a `StateManager` facade that coordinates them. The ~1100-line `mcp_server.py` bootstrap function has been split into a 155-line entry point and a `tools/` subpackage with thirteen modules: six tool-category modules (`discovery`, `search`, `write`, `project`, `provenance`, `onboarding`) plus seven shared-infrastructure modules (`registry`, `context`, `decorators`, `utils`, `resources`, `validation`, `vector_runtime`). `VectorIndex` is now a `typing.Protocol` enabling swappable backends without inheritance. Tool responses use `TypedDict` definitions for static-analysis-friendly typing. `AuthenticationManager.build_auth_params()` is now a public API. These improvements are reflected in the revised Implementation and Architecture section (Section 2).

---

## Reviewer 1

### R1.1 Research motivation

> "The paper does not clearly articulate a formal research problem or gap beyond general ELN--AI disconnection."

Section 1 has been restructured into Section 1.1 ("Motivation and objectives") to make the gap and the package's targets explicit. The revised framing is concrete: ELNs hold the dated, signed record of experiments that institutions treat as authoritative for compliance and intellectual-property purposes, but general-purpose AI clients ship without provider-specific connectors. Without a typed, authenticated interface, researchers either accept hallucinated answers about their own experiments or paste notebook material into prompts by hand and break the institutional audit trail. Section 1.1 cites @kwok2018eln for the ELN landscape, names three operational objectives (O1, O2, O3) that the package targets, and traces a direct line from problem statement to objectives to implementation.

### R1.2 Research questions and objectives

> "The contribution is framed as software development rather than addressing defined research questions."

JORS metapapers describe research software rather than research questions in the empirical-paper sense, so this concern was treated as a request for explicit objectives. Section 1.1 now states three objectives (O1, O2, O3) that the software targets: (O1) expose LabArchives notebooks, pages, entries, and write operations to MCP-compatible AI clients without weakening the platform's existing access controls; (O2) provide concept-level semantic search using a configuration-driven vector backend; and (O3) maintain persistent, graph-structured project state with explicit provenance. The "main contributions" sentence now maps each contribution to one of these objectives.

### R1.3 Related work section

> "The paper lacks a structured comparison with existing ELN integrations, RAG systems, or AI--LIMS frameworks."

A new Section 1.2 ("Related work") has been added with five new citations covering the three buckets the reviewer named: open-source ELNs and the broader ELN landscape (`carpi2017elabftw`, `kwok2018eln`), retrieval-augmented generation methodology (`lewis2020rag`), and LLM tool-use frameworks for scientific work (`bran2024chemcrow`, `boiko2023coscientist`). The section explains how `lab_archives_mcp` differs from those systems: it targets the general-purpose MCP boundary rather than a single LLM harness, and it is built around an existing institutional ELN deployment rather than a bespoke automation stack. The corresponding entries were added to `paper.bib`.

### R1.4 Graphical presentation

> "There are no architecture diagrams, workflow diagrams, or system overview figures to support the technical description."

Revised. The repository ships a Mermaid source plus rendered SVG and PNG assets at `docs/figures/architecture.{mmd,svg,png}`. Figure 1 in the paper renders the PNG and shows the MCP client, FastMCP server tool layer, LabArchives API, local project state, embedding provider, and vector backend data flow.

### R1.5 Research implications

> "The broader scientific, methodological, or institutional implications are not analyzed."

Section 8 (Conclusion) has been expanded with an "implications" paragraph that names three application areas: research data management (typed tool boundary extends AI access without weakening institutional access models), methodology (the layered architecture is reusable for other ELN/LIMS targets and for RAG workflows), and institutional deployment (the explicit data-residency description in Section 2.4 supports mapping the package onto institutional data-governance policies). The same section reuses citations from the new Related Work subsection.

### R1.6 Conclusions section

> "The paper ends without a structured conclusion summarizing contributions and limitations."

Section 8 (Conclusion) now summarizes the package's contributions, explicit implications, and three numbered limitations (L1 LabArchives-specific API boundary, L2 dependence on managed embedding and vector services, L3 absence of a controlled user study, noted as outside the scope of a software metapaper).

### R1.7 References

> "Only a small number of references are provided, mostly software citations, and formatting is inconsistent."

The bibliography has been revised to 16 entries with five peer-reviewed additions (`carpi2017elabftw`, `kwok2018eln`, `lewis2020rag`, `boiko2023coscientist`, `bran2024chemcrow`) and targeted software/API references that are cited in the manuscript. One stale field was also corrected: the `hydra` entry previously carried the Pydantic Zenodo DOI (`10.5281/zenodo.3551468`), which was removed because Hydra does not publish under that DOI. Remaining `@misc` entries (vendor APIs, the MCP specification) retain `note={Accessed: ...}` lines because they are URL-only references rather than archived publications; this is the standard `@misc` form and was kept for consistency with how those resources were originally cited.

### R1.8 Evaluation, benchmarking, and user study

> "No empirical evaluation, benchmarking, user study, or performance metrics are provided to assess effectiveness."

The response has two parts: one on performance metrics and one on a user study. On performance metrics: Section 3 (Quality Control) now reports a reproducible in-process microbenchmark (`scripts/benchmark_internal.py`) with measured median (p95) latencies on an Apple M2 Pro running macOS 26.0.1 and Python 3.11: 0.28 ms (0.32 ms) for `clean_html`, 1.4 ms (2.1 ms) for `StateManager.log_visit`, 2.9 ms (3.7 ms) for `StateManager.log_finding` (with disk persistence), and 4.6 ms (4.9 ms) for `export_project_context` JSON-LD serialization over 40 iterations on a 200-visit project graph. End-to-end tool latency on network-bound calls is dominated by the external services (LabArchives API, OpenAI embeddings, Pinecone), so the in-process number bounds the package's own contribution at sub-5 ms per call and indicates that the MCP layer does not add meaningful overhead relative to those services. On a user study: a controlled human-subjects evaluation of task completion and error rates with and without the MCP layer is a valuable next step, but a JORS Software Metapaper describes a software artefact rather than a controlled study with human subjects. Such an evaluation would require its own IRB protocol, recruitment, and analysis, and would fit better as a separate research article. Section 8 acknowledges the absence of such a study as a stated limitation (L3) of the present validation.

### R1.9 Primarily descriptive

> "The manuscript reads largely as documentation rather than a research-oriented software paper."

`Not changed` (justification). The JORS Software Metapapers template (Overview / Implementation and Architecture / Quality Control / Availability / Reuse) is designed for software-artefact reporting, so a degree of descriptive content seems expected. The manuscript has nonetheless been strengthened along the dimensions that distinguish a research-software paper from documentation: explicit motivation and objectives (Section 1.1), structured related work (Section 1.2), measured quality-control numbers and an in-process benchmark (Section 3), and explicit implications and limitations (Section 8).

---

## Reviewer 2

### R2.1 Architecture figure

> One component/data-flow diagram, Mermaid or SVG, committed to repo, rendered in paper. Layers: MCP client <-> server tools <-> LabArchives API <-> vector backend. Cap at two figures total.

Revised. The repository now includes a Mermaid source file plus rendered SVG and PNG assets at `docs/figures/architecture.*`. Figure 1 in the paper renders the PNG and shows the MCP client, FastMCP server tool layer, LabArchives API, local project state, embedding provider, and vector backend data flow. No second figure was added. This also addresses Reviewer 3's architecture-figure request.

### R2.2 Minor quality control

> Add: test coverage % (pytest-cov + Codecov badge), integration test description (what they exercise -- live API or recorded fixtures), error-handling strategy (fail-loud, schema validation points), search-result validation method, manual-testing protocol on real notebooks. Numbers, not adjectives.

Revised. The paper Quality Control section now reports the measured local command, 262 passing non-integration tests, one skipped test (the `rdflib`-gated linked-data case), six deselected integration tests, and 81% line coverage. It states that the six Pinecone integration tests are live, credential-gated tests rather than recorded fixtures, lists the operations they exercise, and records the local skip result when `PINECONE_API_KEY` was absent. The same section now describes schema validation, write-path failures, LabArchives fault translation, search-result reconstruction and deduplication, and the six-check manual testing protocol.

### R2.3 Reuse section

> New section, three short subsections: (a) other applications (other ELN-like stores, provenance-tracked uploads from pipelines), (b) extension points (new MCP tools, swap vector backend), (c) integration (any MCP-compatible client; example with Claude). Concrete, no speculation.

Revised. The paper Reuse section now has exactly three subsections: Other applications, Extension points, and Integration. It names `eln_client.py`, the MCP tool layer, the `VectorIndex` interface, the current `QdrantIndex` and `LocalEmbedding` placeholders, and the Claude Desktop configuration in `docs/agent_configuration.md`.

### R2.4 Input and output example fidelity

> Replace any example not produced by the actual software with a real captured transcript. Verify by re-running.

Revised. The fabricated conversational example was removed from the paper and README. The replacement transcript was captured by re-running the registered `write_notebook_entry` MCP tool in a local smoke harness with LabArchives network calls replaced by test doubles, yielding the shown `page_tree_id`, `entry_id`, URL, timestamp, and `part_type` response.

### R2.5 Abstract rewrite

> Formal, sober. Include one copy-pasteable example invocation (MCP tool call with arguments and abbreviated response). Cut adjectives.

Revised. The abstract now states what the package exposes, defines MCP, and includes a one-line JSON `write_notebook_entry` invocation with an abbreviated response. Promotional and chatbot-style phrasing was removed from the manuscript.

### R2.6 Support mechanisms

> One paragraph: GitHub Issues URL, maintainer contact, response-time expectation, contribution-guide link.

Revised. The paper Availability section now includes one support paragraph with the GitHub Issues URL, maintainer email, 14-day response target for actionable issues, and the `CONTRIBUTING.md` link.

## Reviewer 3

### R3.1 Version mismatch

> README BibTeX v0.2.4 -> v0.3.2. Grep repo for "0.2.4"; reconcile every occurrence. Confirm Zenodo, paper, README, CITATION.cff, codemeta.json, pyproject.toml all agree.

Revised. The repository uses a three-DOI citation policy across README, paper Availability, `CITATION.cff`, `codemeta.json`, and `pyproject.toml`: the Zenodo concept DOI `10.5281/zenodo.17728440` identifies the software family; the JORS resubmission archive is `v0.5.1` at version DOI `10.5281/zenodo.20421457`; and the original submission archive `v0.3.2` at version DOI `10.5281/zenodo.17772522` is retained for historical traceability only. The README BibTeX entry, DOI badge, `CITATION.cff` preferred-citation, and `codemeta.json` all reflect the resubmission archive version. The remaining `0.2.4` strings are the historical `CHANGELOG.md` heading and the `notebook_shim` dependency version in `conda-lock.yml`.

### R3.2 Write and provenance tool surface

> Add a fifth MCP tool category -- "write & provenance" -- listing `write_notebook_entry` and `upload_to_labarchives` with one-sentence descriptions matching the docstrings. No over-description.

Revised. The paper Implementation and Architecture section and README Available Tools section now group the MCP tools into five user-facing categories and add `write & provenance` as the fifth category. The descriptions state that `write_notebook_entry` writes a rich text entry to a LabArchives page and that `upload_to_labarchives` uploads a file with code provenance metadata, matching the tool docstrings without adding new capabilities.

### R3.3 Architecture figure

This concern is addressed under R2.1 above.

### R3.4 Minor data residency

> One paragraph stating exactly what leaves the institution for Pinecone and Qdrant: vectors only, or vectors plus chunk text -- verify in code -- plus which metadata fields, and what stays local.

Revised. The security and governance text now states that OpenAI receives chunk text and query text for embeddings, Pinecone receives embedding vectors plus chunk text and the specific metadata fields stored in `PineconeIndex.upsert`, and Qdrant receives no data in the current release because `QdrantIndex` raises `NotImplementedError`. It also states that local Parquet persistence stores text, vectors, and metadata on disk, while credentials and project graph state remain local unless copied elsewhere. The vector-backend docs describe Qdrant and local embeddings as extension points only.

### R3.5 Minor sample data reference

> Cite `notebooks/`, `docs/onboard_example.json`, `conf/secrets.example.yml`, and README schema examples in the Sample Data section.

Revised. The paper now has a Sample Data section naming `notebooks/`, `docs/onboard_example.json`, `conf/secrets.example.yml`, and the README Tool Schemas examples. It states that these assets support smoke testing and contract inspection without exposing private ELN records.

### R3.6 Minor MCP one-liner

> First mention of MCP gets one defining sentence for non-specialists.

Revised. The README first mention now defines MCP as an open protocol that lets AI clients call external tools and data sources through structured requests. The paper abstract also defines MCP on first use.
