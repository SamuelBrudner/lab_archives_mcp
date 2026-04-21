# Response to Reviewers

Manuscript: "Integrating AI Assistants with Electronic Lab Notebooks using the LabArchives Model Context Protocol Server"

Revision date: 15 April 2026

The comments below are paraphrased from the April 2026 JORS revision tracker rather than reproduced verbatim. Each response identifies the manuscript section or repository file changed, or explains why no additional change was made.

## Editor Comments

### E1. Version, release, and citation metadata should be internally consistent

**Comment.** The manuscript and repository metadata should present one coherent citation and archive story, including the relationship between the reviewed Zenodo archive and the current source tree.

**Response.** Revised. The manuscript Availability section now distinguishes the reviewed JORS archive from the current source tree: `v0.3.2` is the archived JORS version with DOI <https://doi.org/10.5281/zenodo.17728440>, while `0.3.3` is described as a post-archive maintenance release dated 2025-12-16. The same distinction is recorded in `JORS_READY.md`, `README.md`, and `CITATION.cff`. The README citation block now cites the Zenodo DOI and `v0.3.2`; `CITATION.cff` describes the current `0.3.3` source tree but sets the preferred citation to the archived `0.3.2` record.

**Where changed.** `jors_metapaper.md`, section 4; `README.md`, "Versioning & Release Management" and "Citation"; `CITATION.cff`; `JORS_READY.md`.

### E2. Provide a response package that maps comments to revisions

**Comment.** The resubmission should include a point-by-point response and cover letter that allow editors to map each concern to the revised manuscript or repository.

**Response.** Completed. This file provides the point-by-point mapping, and `jors_cover_letter.md` summarizes the main changes for the editor. The response is organized around the tracked editor and reviewer concerns and names the revised sections and files for each item.

**Where changed.** `jors_response_to_reviewers.md`; `jors_cover_letter.md`.

## Reviewer Comments

### R1. Strengthen the research-software motivation and problem statement

**Comment.** The original paper read too much like product documentation and needed a clearer explanation of the research problem, intended users, and contribution.

**Response.** Revised. The Overview now motivates the work around the disconnect between ELN records and AI assistants, identifies wet-lab researchers, research data management teams, and institutional platform engineers as intended users, and states three concrete contributions: an MCP-based LabArchives connector, a reusable vector-search backend, and a graph-based state-management layer.

**Where changed.** `jors_metapaper.md`, section 1.

### R2. Compare the software to existing ELN, LIMS, and retrieval approaches without unsupported novelty claims

**Comment.** The manuscript should situate the package relative to existing ELN/LIMS APIs and RAG-style integration approaches, while avoiding overbroad novelty claims.

**Response.** Revised. The Reuse Potential section now explains that existing ELN APIs generally provide CRUD and keyword-search interfaces while leaving assistant tool schemas, semantic retrieval, and stateful context to downstream implementers. The wording was also made more conservative by removing the unsupported "first academic application" claim and describing the project as a concrete reusable pattern instead.

**Where changed.** `jors_metapaper.md`, sections 5.1 through 5.4.

### R3. Correct the architecture description and document the complete MCP tool surface

**Comment.** Reviewer 3 identified factual gaps in the architecture section, especially around the current tool names, stateful tools, and mutating write/provenance functionality.

**Response.** Revised. The Implementation and Architecture section now describes six components rather than five, adding a distinct upload and provenance layer. The MCP server description now lists the current tool categories and tool names, including discovery, reading, search, index management, project state, graph navigation, and optional writing/provenance tools. The upload section explicitly names `write_notebook_entry` and `upload_to_labarchives` and describes the provenance metadata captured with uploaded computational artifacts.

**Where changed.** `jors_metapaper.md`, section 2, especially the MCP server and upload/provenance component descriptions.

### R4. Add a figure that makes the architecture easier to inspect

**Comment.** The manuscript should include visual material so readers can understand the system architecture and component boundaries more quickly.

**Response.** Revised. The manuscript now includes an architecture figure showing the AI assistant, `lab_archives_mcp` components, and the LabArchives API, with an explanatory caption. A separate workflow figure was not added in this conservative revision because the architecture figure, expanded component list, and illustrative example together cover the main data flow without adding another asset to maintain.

**Where changed.** `jors_metapaper.md`, section 2; figure asset in `docs/figures/architecture.png` with source in `docs/figures/architecture.mmd`.

### R5. Expand quality-control claims with test scope, CI behavior, and validation evidence

**Comment.** The manuscript should give enough detail for readers to assess the trustworthiness of the software, including automated tests, integration tests, and validation behavior.

**Response.** Revised. The Quality Control section now identifies the main unit-test areas, including authentication, notebook navigation, upload validation, state persistence, graph traversal, pagination, and vector-backend components. It also describes credential-gated integration tests for live LabArchives workflows, CI execution on Linux and macOS for Python 3.11+, and the local revision validation result. The manuscript now states that `pytest -q` completed with 217 passing tests and six credential-gated Pinecone smoke tests skipped during the revision. Runtime validation behavior is described through Pydantic request models, missing-file and empty-content checks, bounded pagination, and translated API faults.

**Where changed.** `jors_metapaper.md`, section 3; `.github/workflows/tests.yml`.

### R6. Avoid overstating coverage reporting

**Comment.** Coverage evidence should be stated accurately and should not imply a public or complete coverage metric that the repository does not guarantee.

**Response.** Addressed conservatively. The CI workflow generates `coverage.xml` for the unit-test job and attempts Codecov upload on Ubuntu with Python 3.11 when a token is available, but the manuscript does not claim a specific public coverage percentage. No coverage badge or numeric coverage claim was added because that would overstate the currently guaranteed evidence. Instead, the revised Quality Control section focuses on test scope, CI behavior, and observed local test results.

**Where changed.** `jors_metapaper.md`, section 3; `.github/workflows/tests.yml`.

### R7. Clarify sample assets, support mechanisms, and reuse pathways

**Comment.** The manuscript should make reuse easier to assess by naming available example assets, support mechanisms, and adaptation paths.

**Response.** Revised. The Quality Control section now names lightweight example assets that can support smoke testing without exposing private ELN content, including `docs/onboard_example.json`, `notebooks/test.ipynb`, and configuration templates under `conf/`. The Availability and Reuse Potential sections now identify GitHub issues, `CONTRIBUTING.md`, `docs/agent_configuration.md`, and the onboarding payload example as support and reuse resources. The manuscript also clarifies how the architecture can be adapted to other ELNs or LIMS by replacing the API-client layer while preserving MCP tool patterns, state management, graph navigation, and the vector backend.

**Where changed.** `jors_metapaper.md`, sections 3, 4, 5.2, 5.3, 5.4, and 5.6.

### R8. Discuss privacy, data residency, and managed vector services

**Comment.** The manuscript should distinguish local or self-hosted deployment from managed embedding and vector-search services, especially for ELN-derived data.

**Response.** Revised. A new security and governance subsection now discusses namespace isolation, write control, data sovereignty, and credential scoping. It explicitly distinguishes a local Parquet index with local embeddings, which keeps notebook text, embeddings, and project state under institutional control, from managed embedding or vector-store services such as Pinecone and Qdrant, which may receive notebook-derived text, embeddings, metadata, or both depending on configuration. The limitations section also identifies external vector stores as an additional data-custody layer.

**Where changed.** `jors_metapaper.md`, sections 2.4, 5.5, and 5.6; `docs/semantic_governance.md`.

### R9. Add broader implications, limitations, and a structured conclusion

**Comment.** The paper should end with a clearer statement of contributions, implications, and constraints rather than stopping after examples and acknowledgements.

**Response.** Revised. The manuscript now includes a Conclusion section that summarizes the software as a modular bridge between ELNs and AI assistants, emphasizes that it complements rather than replaces institutional ELN infrastructure, and states the key limitations: dependence on LabArchives API access and the privacy implications of optional managed embedding and vector services.

**Where changed.** `jors_metapaper.md`, section 7.
