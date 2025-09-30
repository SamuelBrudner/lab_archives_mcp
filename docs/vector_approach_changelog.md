# Vector Approach Document Improvements

**Date:** 2025-09-30
**Document:** `docs/vector_approach.md`

## Summary

Comprehensive revision to align with FAIR principles, academic biology development guidelines, and production readiness requirements.

## Major Additions

### 1. **Chunking Strategy (§3.1)**
- Concrete implementation specification with Hydra config parameters
- Algorithm details using `tiktoken` + `langchain.text_splitter`
- Test coverage requirements with edge cases
- Boundary preservation rules

### 2. **Embedding Model Selection (§3.2)**
- Comparison table: OpenAI vs. open-source models (`bge-large-en-v1.5`, `scibert`)
- Cost analysis, performance benchmarks, licensing considerations
- Evaluation plan with test set methodology
- Config versioning strategy for reindexing triggers

### 3. **Data Schema & Validation (§3.3)**
- Expanded Pydantic models: `ChunkMetadata` and `EmbeddedChunk`
- Added missing metadata fields: `folder_path`, `tags`, `labarchives_url`, `entry_type`
- Field validation with fail-fast error handling
- Parquet storage format with DVC tracking

### 4. **Error Handling & Reliability (§6.1)**
- Comprehensive failure modes table (7 scenarios)
- Dead-letter queue design for failed embeddings
- Exponential backoff retry logic
- Structured logging with metrics (p50/p95/p99 latencies)

### 5. **Cost & Scalability Analysis (§6.2)**
- Concrete assumptions: 10 notebooks, 5K entries → 10K chunks
- OpenAI embedding costs: **$0.08 initial, $0.004/month incremental**
- Pinecone costs: **~$5.20/month** for prototype
- Qdrant migration break-even: >50K chunks
- Storage optimization: 5:1 compression with gzip

### 6. **Evaluation & Validation (§7)**
- Success metrics: recall@5 (≥70%), recall@10 (≥85%), p95 latency (<500ms)
- Benchmark creation process (50 query→entry pairs)
- Continuous evaluation via GitHub Actions
- A/B comparison vs. TF-IDF baseline

### 7. **Testing Strategy (§7.1)**
- Coverage targets: 90% (pure functions), 70% (API integration), 80% (E2E)
- Test structure: `unit/`, `integration/`, `fixtures/`
- Property-based tests with `hypothesis`
- HTTP replay with `vcrpy`
- Performance benchmarks with `pytest-benchmark`
- Mutation testing with `mutmut`
- CI pipeline configuration

### 8. **Operational Improvements**
- Incremental update configuration with cron schedule
- LabArchives webhook status: **not available** (verified)
- Idempotency guarantees for incremental updates
- Reindexing workflow with versioned directories
- Rollback plan for failed model upgrades

### 9. **Roadmap Refinement**
- Concrete time estimates (weeks per phase)
- Phase 1-6 breakdown with specific deliverables
- Orchestration approach: GitHub Actions (not Celery)
- MCP tool specification: `search_notebooks(query, filters)`

## Alignment with Global Rules

✅ **FAIR Principles:** DVC tracking, versioned configs, reproducible pipeline
✅ **Modular Design:** Pydantic models, pure functions, separate chunking module
✅ **Config Management:** Hydra YAML with environment interpolation
✅ **Testing Discipline:** 90% coverage target, TDD approach, mutation tests
✅ **Fail Fast:** Pydantic validation, explicit error handling, structured logging
✅ **Documentation:** Concrete implementation paths, operator runbook references

## Outstanding Work

1. Create `conf/vector_search/default.yaml` with all parameters
2. Implement `src/labarchives_mcp/vector_search/` module structure
3. Build test set: `tests/fixtures/semantic_search_benchmark.json`
4. Set up DVC remote for embeddings storage
5. Configure GitHub Actions for weekly benchmark runs
6. Document operator runbook for production deployment

## Next Steps

1. **Prototype Phase 1:** Implement chunking + embedding modules
2. **Set up infrastructure:** DVC, Hydra configs, test fixtures
3. **Initial indexing:** Run on 1-2 test notebooks
4. **Evaluation:** Build benchmark, measure baseline recall
5. **Iterate:** Tune chunking parameters, compare embedding models
