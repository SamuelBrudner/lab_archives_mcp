# Description

- Promote BuildRecord into shared semantic models (`vector_backend.models.BuildRecord`)
- Add comprehensive tests for build state (fingerprint, persistence, rebuild logic)
- Fix embedding client: call OpenAI embeddings via httpx instead of SDK to avoid import issues; stabilize tests
- MCP sync tool groundwork: planning-only MVP returns skip/incremental/rebuild plans
- Search tool: deduplicate by page with candidate oversampling; allow page limit
- Documentation updates for indexing/sync behavior and search page limits

Motivation

- Ensure the CLI’s build record feature is fully tested and modeled in the core semantic layer
- Stabilize test suite and avoid slow/fragile SDK imports during unit tests
- Clarify when notebooks are indexed and how sync is controlled (rebuild vs incremental)
- Enable page-level result limits and dedup for practical MCP usage

Type of Change

- Bug fix (embedding import issues leading to failing tests)
- Test improvement (build-state, sync planning, spec fixtures)
- Documentation update
- Code refactoring (model promotion)

Implementation

- `OpenAIEmbedding`: replaced SDK with direct httpx POST to `/v1/embeddings` + retries/backoff and dimension checks
- BuildRecord moved to `vector_backend.models`; `build_state` imports updated
- MCP sync tool returns structured plans; indexing execution remains TODO (tracked)
- Search tool enforces unique pages up to limit

Testing

- Unit tests pass locally
- Integration tests for Pinecone are skipped unless keys are set
- Manual checks: pre-commit hooks, full pytest run

Checklist

- [x] My code follows the project's code style guidelines
- [x] I have run `pre-commit run --all-files` and fixed all issues
- [x] I have added tests that prove my fix is effective or that my feature works
- [x] New and existing unit tests pass locally
- [x] I have updated the documentation accordingly
- [x] My commits follow the Conventional Commits specification
- [x] I have added my changes to the CHANGELOG under v0.2.2

Breaking Changes

- None
