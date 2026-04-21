# Semantic Governance

This document defines the governance rules for semantic search, embedding, and
graph-derived context in `lab_archives_mcp`. It is intended for operators who
connect LabArchives content to vector indexes, embedding providers, or AI
assistants.

## Scope

Semantic governance applies when notebook content, derived chunks, embeddings,
metadata, graph state, or retrieval results leave the immediate LabArchives API
response path. This includes:

- building or refreshing vector indexes;
- storing local Parquet/DVC embedding artifacts;
- sending text to an embedding provider;
- querying external vector stores such as Pinecone;
- using project graph state for related-page discovery or provenance tracing.

The MCP server does not replace institutional review, IRB, data-use, or
LabArchives access policies. Deployments must apply the stricter rule whenever
institutional policy and this document differ.

## Data Classification

Treat all notebook text, entry metadata, uploaded-file provenance, and graph
state as research data. Before enabling semantic indexing, classify notebooks
using the institution's data policy.

| Data class | Examples | Semantic indexing rule |
| --- | --- | --- |
| Public or approved open data | Published protocols, public training material | May use configured local or external backends. |
| Internal research data | Routine experiments, non-sensitive lab notes | Prefer local or institution-approved backends; external services require local approval. |
| Restricted research data | Human subject data, clinical data, controlled-access datasets, confidential collaborations | Do not send text, embeddings, or derived metadata to external services unless explicitly approved. |
| Secrets and credentials | API keys, passwords, tokens, private certificates | Must never be indexed, embedded, logged, or uploaded as provenance metadata. |

Notebook owners are responsible for excluding content that is not approved for
semantic processing. Operators should document which notebooks and folders are
in scope for each index.

## Semantic Index Contract

Every semantic index must have an explicit contract recorded with the deployment
configuration:

- source scope: notebook IDs, page folders, and excluded paths;
- embedding model and version;
- chunking configuration and overlap;
- local persistence path and DVC remote, if used;
- vector store backend and region;
- retention period for local artifacts and remote vectors;
- reviewer or steward who approved the configuration.

Changing any field that affects chunk text, embedding vectors, or access
boundaries requires a new embedding version and a full reindex. Keep older index
versions only for the documented rollback period, then delete them from local
storage and remote vector stores.

## Access Control

Semantic retrieval must not broaden access beyond the authenticated LabArchives
user. The server and any vector backend should be configured so retrieved
results are limited to content the requesting user is allowed to read.

Required controls:

- run the MCP server with the least-privileged LabArchives account suitable for
  the workflow;
- keep `conf/secrets.yml` and environment variables out of version control;
- disable upload tools in read-only deployments with
  `LABARCHIVES_ENABLE_UPLOAD=false`;
- avoid shared vector indexes that combine notebooks with different access
  groups unless retrieval filters enforce those boundaries;
- log operational events without writing notebook text or credentials to logs.

If a deployment cannot enforce user-specific retrieval permissions, use a
separate index per access group or keep semantic search disabled for restricted
content.

## Provider Selection

Local and on-premise backends are preferred for restricted or unpublished
research data. External embedding APIs and hosted vector stores may be used only
after reviewing provider terms, data retention, model-training policy, region,
and institutional requirements.

At minimum, record the following for each external provider:

- service name and configured region;
- data sent to the provider, such as raw text, embeddings, or metadata;
- whether provider logs or stores submitted content;
- whether submitted content may be used for model training;
- incident response contact and deletion procedure.

Do not assume embeddings are anonymized. They are derived from notebook content
and must be governed with the same care as the source material.

## Provenance and Auditability

Semantic results should remain traceable to the source notebook entry. Preserve
the chunk metadata required by `vector_backend.models.ChunkMetadata`, including
notebook ID, page ID, entry ID, entry type, author, date, LabArchives URL, and
embedding version.

Operational records should capture:

- index build time and code version;
- embedding model and chunking settings;
- number of pages, entries, and chunks processed;
- skipped entries and validation failures;
- deletes or reindex operations caused by source changes;
- approval or review reference for restricted deployments.

These records may contain sensitive metadata. Store them with the same access
controls as the semantic index.

## Retention and Deletion

Semantic artifacts must follow the retention policy of the source notebooks.
When a notebook, page, or entry is deleted or removed from semantic scope,
delete the corresponding local chunks, DVC-tracked artifacts, and remote vectors.

Recommended defaults:

- retain previous embedding versions for no more than 30 days after a successful
  migration;
- keep failed-chunk records only as long as needed for repair;
- rotate logs before they accumulate sensitive metadata beyond operational need;
- verify remote vector counts against local persistence after delete and reindex
  operations.

Backups and DVC remotes are part of the governed data footprint. Deleting local
files is not sufficient if the same artifacts were pushed to remote storage.

## Operational Review

Review semantic governance before first deployment, before adding a new notebook
scope, before switching providers, and before enabling write-capable tools for
agents. A review should confirm:

- the indexed notebooks are approved for semantic processing;
- provider and storage choices match the data classification;
- access boundaries are enforced by credentials, index separation, or filters;
- secrets are stored only in approved configuration channels;
- rollback and deletion procedures have been tested;
- users understand that retrieved passages and embeddings are governed research
  artifacts.

Document the review outcome in the deployment runbook or institutional change
record rather than in source-controlled secrets files.
