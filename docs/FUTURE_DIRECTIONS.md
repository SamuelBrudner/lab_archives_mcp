# Future Directions

Optional enhancements to consider based on actual usage patterns and requirements.

## Vector Backend Enhancements

### ✅ DVC Integration (COMPLETED - 2025-10-01)
Implemented via TDD with 8 passing integration tests.

**Features:**
- Automatic DVC initialization when `enable_dvc=True`
- Parquet files tracked with `.dvc` files committed to git
- Version isolation (separate directories per embedding version)
- Graceful degradation if DVC not installed
- Works with pre-existing DVC repos

**Usage:**
```python
persistence = LocalPersistence(
    base_path=Path("data/embeddings"),
    version="v1",
    enable_dvc=True
)
```

See `README_VECTOR_BACKEND.md` for full workflow.

---

### Performance Optimization
- Benchmark embedding batch sizes for large-scale indexing (100+ notebooks)
- Profile chunking performance on very large pages (>50k tokens)
- Optimize Parquet compression settings based on actual storage usage

**Value:** Faster indexing for power users with large notebook collections.
**Effort:** Medium - requires profiling tools and test datasets.
**Decision criteria:** Implement when users report slow indexing (>30min for typical notebook).

---

### Production Hardening (Remaining)

**Structured Logging**
- Replace print statements with structured logging (JSON format)
- Add correlation IDs for request tracing
- Configurable log levels per component

**Value:** Better debugging and monitoring in production deployments.
**Effort:** Medium - consistent logging across codebase.
**Decision criteria:** Implement when deploying as shared service (concurrent write safety is now complete).

**Retry Logic Abstraction**
- Extract retry patterns to utility module if used in 3+ places
- Add exponential backoff configuration

**Value:** Reduces code duplication, easier to tune retry behavior.
**Effort:** Low - refactoring existing code.
**Decision criteria:** Implement when adding more API clients with retry needs.

**Connection Pooling**
- Evaluate httpx connection pool tuning for concurrent usage
- Add connection limits and timeout configuration

**Value:** Better resource utilization under high load.
**Effort:** Low - configuration changes.
**Decision criteria:** Implement when concurrent indexing/search becomes common.

---

## CLI Enhancements

### Search Command
Add `labarchives-mcp search` command for direct semantic search:
```bash
labarchives-mcp search "olfactory navigation behavior" --limit 10
```

**Value:** Enables command-line semantic search without MCP client.
**Effort:** Low - wrapper around existing search API.
**Decision criteria:** Implement when users request CLI-only workflows.

---

### Local Persistence Management
Add commands to manage local embeddings:
```bash
labarchives-mcp list-embeddings       # Show indexed notebooks
labarchives-mcp export-embeddings     # Export to portable format
labarchives-mcp import-embeddings     # Import from another system
```

**Value:** Better control over local persistence storage.
**Effort:** Low - thin layer over LocalPersistence API.
**Decision criteria:** Implement when users need to migrate embeddings between systems.

---

## Integration Features

### Local Embedding Models
- Add sentence-transformers support for offline embeddings
- Remove OpenAI API dependency for air-gapped deployments

**Value:** Enables semantic search in secure/offline environments.
**Effort:** Medium - model selection and integration.
**Decision criteria:** Implement when institutions require air-gapped deployments.

---

### Additional Vector Stores
- Chroma support (lightweight SQLite-based)
- Weaviate support (GraphQL API)

**Value:** More deployment options for different scale/complexity needs.
**Effort:** Medium - backend adapter implementation.
**Decision criteria:** Implement when users request specific vector store.

---

## Testing Improvements

### Coverage Measurement
- Run coverage analysis on vector backend
- Target: 90%+ for pure functions, 70%+ overall
- Add coverage CI job

**Value:** Quantifies test quality, finds untested code paths.
**Effort:** Low - add coverage tooling.
**Decision criteria:** Implement before next major release.

---

## Documentation

### Vector Backend Tutorial
- Standalone tutorial for using vector backend as library
- Example: custom indexing pipeline
- Integration patterns

**Value:** Enables researchers to use vector backend independently of MCP.
**Effort:** Medium - comprehensive examples needed.
**Decision criteria:** Implement when 3+ external users request it.

---

## Decision Framework

**Priority levels:**
1. **High:** Requested by multiple users, clear value proposition
2. **Medium:** Nice-to-have, implement when convenient
3. **Low:** Speculative, defer until proven need

**Implementation approach:**
- Follow TDD for all new features
- Maintain minimal design - no features until required
- Document decision criteria for each enhancement
- Revisit quarterly based on actual usage patterns
