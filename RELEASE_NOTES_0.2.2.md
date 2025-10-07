# Release Notes v0.2.2

## Highlights

- Fix: Embedding client now uses httpx to call the OpenAI embeddings REST API, avoiding SDK import issues and stabilizing tests
- Build: Promote BuildRecord into shared semantic models; add robust build-state tests
- MCP: Sync planning MVP returns skip/incremental/rebuild without indexing side effects
- Search: Unique pages limited by `limit` with candidate oversampling
- Docs: Clarify indexing triggers, sync behavior, and search page limit semantics

## Changes

- fix(embedding): call OpenAI embeddings via httpx; add retry/backoff and dimension checks
- test(build-state): fingerprinting, persistence, rebuild logic
- feat(models): promote BuildRecord to `vector_backend.models`
- spec(search): enforce page-level dedup and limit behavior
- docs: update README and QUICKSTART to describe indexing & sync

## Compatibility

- No breaking changes
- Pinecone integration tests remain skipped unless `PINECONE_API_KEY` is provided

## Links

- Compare: <https://github.com/SamuelBrudner/lab_archives_mcp/compare/v0.2.1...v0.2.2>
- PR: <https://github.com/SamuelBrudner/lab_archives_mcp/pull/8>
