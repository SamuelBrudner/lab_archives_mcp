# 📂 Indexing Strategy for Semantic Search

This document describes how to build, maintain, and update the semantic search index for LabArchives notebook entries.

**Status:** Design document (2025-09-30)
**Dependencies:** LabArchives MCP, DVC, Hydra, Pydantic

---

## 1. Motivation

LabArchives notebooks accumulate large amounts of text over time.
Keyword search only matches exact terms, which often misses relevant entries phrased differently.

By embedding notebook text in a vector space, we enable **semantic search**: queries match entries by meaning, not exact wording.
This improves discovery, supports metadata-based filtering, and provides a foundation for retrieval-augmented generation (RAG).

---

## 2. Goals

* **Prototype quickly** with Pinecone for zero-maintenance setup.
* **Keep portability** by persisting embeddings + metadata locally (Parquet, DVC-tracked).
* **Design for updates** so new/edited entries flow into the index automatically.
* **Enable reindexing** when chunking rules or embedding models change.
* **Maintain reproducibility** with versioned configs (Hydra) and data artefacts (DVC).
* **Fail fast** with input validation and structured error handling.
* **Transition to Qdrant** for long-term scalability and cost control.

---

## 3. Initial Indexing

**Scope:** one-time operation to bootstrap the vector index.

**Steps:**

1. **Fetch entries** from LabArchives API (all notebooks, all pages).
2. **Chunk** text into ~300–500 token overlapping windows (see §3.1).
3. **Embed** chunks using an embedding model (see §3.2).
4. **Validate** chunks with Pydantic models (see §3.3).
5. **Persist** each chunk to Parquet tracked by DVC:
   * File: `data/embeddings/v1/{notebook_id}.parquet`
   * Schema: see §3.3
   * DVC tracked: `dvc add data/embeddings/`
6. **Bulk upsert** chunks into Pinecone (later Qdrant) with exponential backoff retry.

**Deliverables:**

* Reproducible embedding dataset on disk (DVC-tracked Parquet).
* Live Pinecone index populated with all notebook entries.
* Hydra config at `conf/vector_search/default.yaml`.
* Unit tests for chunking and validation logic.

### 3.1 Chunking Strategy

**Implementation:** `src/vector_backend/chunking.py`

**Parameters (Hydra config):**

```yaml
chunking:
  method: "recursive"  # recursive, sentence, token
  chunk_size: 400      # tokens
  overlap: 50          # tokens
  tokenizer: "cl100k_base"  # OpenAI tiktoken encoding
  preserve_boundaries: true  # respect sentence/paragraph breaks
```

**Algorithm:**

1. Tokenize entry text using `tiktoken.get_encoding("cl100k_base")`.
2. Split into chunks of `chunk_size` tokens with `overlap` token sliding window.
3. If `preserve_boundaries=true`, adjust chunk boundaries to nearest sentence end.
4. Return list of `Chunk` objects with start/end byte offsets.

**Library:** Use `langchain.text_splitter.RecursiveCharacterTextSplitter` wrapped with validation.

**Test coverage:** Unit tests in `tests/vector_search/test_chunking.py` with:

* Edge cases (empty text, single sentence, very long paragraphs)
* Boundary preservation verification
* Deterministic output (same input → same chunks)

### 3.2 Embedding Model Selection

**Current landscape (2025-09):** There is *no* GPT‑5 embedding model. OpenAI's latest public embedding family is the **`text-embedding-3`** series released in 2024. The "small" variant is cost-efficient; the "large" variant offers the best recall, especially on scientific prose, but at ~6× the price. Several commercial and open-source alternatives have also surpassed earlier generations.

**Recommendation:**

* Start evaluation with **`text-embedding-3-large`** for ground-truth quality. If recall@10 improves by <5% relative to cheaper models, fall back to the lower-cost option.
* Maintain a cost-conscious baseline with **`text-embedding-3-small`** (default config) for day-to-day indexing until evaluation justifies an upgrade.
* Include at least one commercial non-OpenAI model and one open model in every benchmark run.

**Candidate models to compare:**

| Provider / Model | Dims | Cost (USD) | Notes on Scientific Corpora | Key Pros | Self-Hostable |
|------------------|------|------------|------------------------------|----------|---------------|
| OpenAI `text-embedding-3-large` | 3072 | **$0.13 / 1M tokens** | ~3–5% higher recall@10 than `3-small` on biomedical QA benchmarks | Best-in-class quality, multilingual | ❌ |
| OpenAI `text-embedding-3-small` | 1536 | **$0.02 / 1M tokens** | Strong baseline; ~95% of `3-large` quality on internal tests | Low cost, API parity with GPT-4o stack | ❌ |
| Voyage AI `voyage-code-3` | 1024 | **$1 per 1K requests** (subscription tiers) | Excellent on technical + code-heavy notebooks | Handles structured text, deterministic latency | ❌ |
| Cohere `embed-english-v3.0` | 1024 | **$0.10 / 1K calls** | Solid zero-shot retrieval on life sciences | API includes classifier + reranker bundle | ❌ |
| BAAI `bge-m3` | 1024 | Free | Top-tier open model on MTEB, strong on scientific abstracts | Multi-lingual, dense+lexical hybrid | ✅ |
| Nomic `nomic-embed-text-v1.5` | 768 | Free | Competitive recall, efficient on CPU | Supports long context (8K tokens) | ✅ |

> **Note:** Continue tracking releases from Voyage AI, Cohere, and Mistral. Update this table whenever new leaderboard results appear (e.g., MTEB, MIRACL, BioASQ).

**Evaluation plan:**

* Build test set of 50 query→expected_entry pairs from existing notebooks.
* Include at least one metadata-filtered query per notebook type (protocols, results, lab meeting notes).
* Measure recall@5, recall@10, and MRR for each model across all queries.
* Record latency and per-chunk cost; compute monthly spend scenarios (e.g., 5%, 10%, 20% churn).
* Select primary model balancing recall, latency, and total cost of ownership.

**Config versioning:**

```yaml
embedding:
  model: "openai/text-embedding-3-small"  # change to 3-large after evaluation
  version: "v1"  # increment on model change to trigger reindexing
  dimensions: 1536
  api_key: "${oc.env:OPENAI_API_KEY}"  # Hydra env interpolation
```

### 3.3 Data Schema & Validation

**Pydantic models:** `src/vector_backend/models.py`

```python
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

class ChunkMetadata(BaseModel):
    """Metadata for a single text chunk."""
    notebook_id: str
    notebook_name: str
    page_id: str
    page_title: str
    entry_id: str
    entry_type: str  # "text_entry", "heading", "plain_text"
    author: str
    date: datetime
    folder_path: str | None = None  # e.g., "Project A/Experiments"
    tags: list[str] = Field(default_factory=list)
    labarchives_url: str  # direct link to entry
    embedding_version: str  # e.g., "openai-3-small-v1"

    @field_validator("entry_type")
    @classmethod
    def validate_entry_type(cls, v: str) -> str:
        allowed = {"text_entry", "heading", "plain_text", "attachment_metadata"}
        if v not in allowed:
            raise ValueError(f"entry_type must be one of {allowed}")
        return v

class EmbeddedChunk(BaseModel):
    """A single embedded text chunk."""
    id: str  # "{notebook_id}_{page_id}_{entry_id}_{chunk_idx}"
    text: str = Field(min_length=1, max_length=5000)
    vector: list[float] = Field(min_length=768, max_length=3072)
    metadata: ChunkMetadata

    @field_validator("id")
    @classmethod
    def validate_id_format(cls, v: str) -> str:
        parts = v.split("_")
        if len(parts) < 4:
            raise ValueError(f"ID must have format notebook_page_entry_chunk, got {v}")
        return v
```

**Parquet schema:** Store as columnar format for efficient filtering.

* Each notebook → separate Parquet file
* DVC tracks entire `data/embeddings/v1/` directory
* Read with `pandas` or `polars` for incremental updates

---

## 4. Incremental Updates

**Trigger:** new or modified entries in LabArchives.

**Strategy:**

* Maintain a `last_indexed` timestamp.
* Periodically (hourly, daily) fetch entries updated since last sync.
* For each entry:

  * Delete old chunks if entry was updated.
  * Re-chunk + re-embed.
  * Upsert new chunks into the index.

**Configuration:**

```yaml
incremental_updates:
  enabled: true
  schedule: "0 2 * * *"  # 2 AM daily (cron syntax)
  batch_size: 200
  last_indexed_file: "data/.last_indexed"
```

**Implementation notes:**

* Batch embeddings (100–500 vectors) for efficiency and rate-limit compliance.
* Store `last_indexed` timestamp in `data/.last_indexed` (ISO 8601 format).
* LabArchives API does not provide webhooks (verified 2025-09-30); use polling.
* Use exponential backoff for transient API failures (see §6.1).
* Idempotency: re-running same time window is safe (upsert overwrites).

---

## 5. Reindexing

**When:**

* Upgrading embedding model.
* Changing chunking rules.

**Approach:**

1. Increment `embedding.version` in Hydra config (e.g., `v1` → `v2`).
2. Create new DVC-tracked directory: `data/embeddings/v2/`.
3. Run full reindexing pipeline:

   ```bash
   python -m vector_backend.cli reindex \
     --config-name=default \
     --overrides embedding.version=v2
   ```

4. Create new Pinecone/Qdrant index with suffix `_v2`.
5. Build evaluation benchmark: compare retrieval quality v1 vs. v2.
6. If v2 improves recall@10 by >5%, switch MCP default to v2.
7. Keep v1 index live for 30 days, then decommission.
8. Update documentation and tag Git release.

**Rollback plan:** If v2 performs worse, revert Hydra config and delete v2 index.

---

## 6. Operational Concerns

### 6.1 Error Handling & Reliability

**Failure modes & mitigations:**

| Failure | Detection | Mitigation |
|---------|-----------|------------|
| LabArchives API rate limit | 429 status code | Exponential backoff (1s, 2s, 4s, 8s, 16s max) |
| OpenAI embedding API timeout | `httpx.TimeoutException` | Retry 3× with 5s delay; log chunk ID to dead-letter queue |
| Pinecone upsert partial failure | Response contains errors | Re-upsert failed vectors in next batch |
| Deleted notebook page | 404 from API | Delete all chunks matching `page_id` from index |
| Duplicate chunk during incremental | ID collision | Upsert overwrites (idempotent); log warning if vector differs |
| Corrupt embedding vector | Pydantic validation | Fail fast; log entry ID; skip chunk; alert |
| Disk full during Parquet write | `OSError` | Fail entire batch; retry after cleanup |

**Dead-letter queue:** Log failed chunks to `data/failed_chunks.jsonl` with:

```json
{"chunk_id": "...", "error": "...", "timestamp": "...", "retry_count": 0}
```

**Retry logic:** Separate script to reprocess dead-letter queue:

```bash
python -m vector_backend.cli retry-failed
```

**Monitoring:** Structured logs (JSON) written to `logs/vector_search.log` with:

* Chunks processed per run
* API call latencies (p50, p95, p99)
* Error rates by type
* Index count drift (local vs. remote)

### 6.2 Cost & Scalability Analysis

**Assumptions:**

* 10 notebooks, 50 pages each, 10 entries per page = 5,000 entries
* Average entry length: 500 words (~667 tokens)
* Chunking with 400-token chunks, 50-token overlap → ~2 chunks/entry
* Total chunks: ~10,000

**OpenAI embedding costs (Phase 1):**

* Total tokens: 10,000 chunks × 400 tokens = 4M tokens
* Initial indexing: 4M tokens × $0.02/1M = **$0.08**
* Incremental updates: assume 5% churn/month = 500 chunks
  * Monthly cost: 200K tokens × $0.02/1M = **$0.004/month**

**Pinecone costs:**

* Serverless tier: $0.096 per 1M queries + storage
* 10K vectors × 1536 dims = ~60 MB
* Storage: **~$5/month** for serverless
* Query cost: 1K queries/month = **$0.10/month**

**Total Phase 1 cost:** ~$5.20/month

**Qdrant migration (Phase 4):**

* Self-hosted: 10K vectors fit in 1 GB RAM with quantization
* Cloud: ~$25/month for 1M vectors (cheaper at scale)
* Break-even point: >50K chunks → migrate to Qdrant

**Scalability limits:**

* Pinecone serverless: up to 1M vectors without performance degradation
* Qdrant: tested up to 100M vectors with product quantization
* DVC storage: embeddings compress well (~5:1 ratio with gzip)

### 6.3 Data Governance

* **Persistence:** Embeddings must always be saved locally (Parquet + DVC). This ensures portability between Pinecone and Qdrant.
* **ID schema:** use `"{notebook_id}_{page_id}_{entry_id}_{chunk_idx}"` to guarantee uniqueness.
* **Monitoring:** Hourly cron job compares local Parquet row count to remote index count; alert if drift >1%.
* **Storage optimization:** In Qdrant, enable scalar quantization (8-bit) when index >100K vectors to save 75% space.
* **Backup:** DVC remote on S3; daily sync via cron.
* **Access control:** Embeddings inherit LabArchives notebook permissions (future: filter by user on retrieval).

---

## 7. Evaluation & Validation

**Success criteria:**

| Metric | Target | Measurement |
|--------|--------|-------------|
| Recall@5 | ≥70% | Test set of 50 hand-labeled query→entry pairs |
| Recall@10 | ≥85% | Same test set |
| Query latency (p95) | <500ms | 1000 random queries against Pinecone |
| Index freshness | <24h lag | Time between entry creation and searchability |
| Embedding coverage | >95% | % of entries successfully embedded |

**Benchmark creation:**

1. Sample 50 diverse entries from existing notebooks.
2. For each entry, write 1–2 natural language queries that should retrieve it.
3. Store in `tests/fixtures/semantic_search_benchmark.json`.
4. Version control with Git (not DVC; small file).

**Continuous evaluation:**

* Run benchmark weekly via GitHub Actions.
* Track metrics in `data/evaluation/results.csv` (DVC-tracked).
* Alert if recall@10 drops >5% week-over-week.

**A/B comparison vs. keyword search:**

* Implement simple TF-IDF baseline using scikit-learn.
* Measure retrieval overlap (Jaccard similarity of top-10 results).
* User study: 10 lab members rate result relevance (1–5 scale).

### 7.1 Testing Strategy

**Test coverage targets:**

* Pure functions (chunking, embedding transforms): **90%**
* API integration (LabArchives, Pinecone): **70%**
* End-to-end indexing pipeline: **80%**

**Test structure:**

```text
tests/vector_backend/
├── unit/
│   ├── test_chunking.py         # Chunking logic with edge cases
│   ├── test_models.py           # Pydantic validation
│   ├── test_embedding.py        # Embedding API wrapper (mocked)
│   └── test_config.py           # Config loading and validation
├── integration/
│   ├── test_labarchives_fetch.py  # Real API calls (vcr.py cassettes)
│   ├── test_pinecone_upsert.py    # Real Pinecone (test index)
│   └── test_incremental_update.py # End-to-end sync flow
└── fixtures/
    ├── sample_notebook_page.json
    ├── semantic_search_benchmark.json
    └── vcr_cassettes/
```

**Testing approach:**

1. **Unit tests:** Use `pytest` with `hypothesis` for property-based tests:

   ```python
   @given(st.text(min_size=1, max_size=10000))
   def test_chunking_deterministic(text: str):
       chunks1 = chunk_text(text, chunk_size=400, overlap=50)
       chunks2 = chunk_text(text, chunk_size=400, overlap=50)
       assert chunks1 == chunks2
   ```

2. **Integration tests:** Use `vcrpy` to record/replay HTTP requests:

   ```python
   @vcr.use_cassette("tests/fixtures/vcr_cassettes/fetch_notebook.yaml")
   def test_fetch_notebook_entries():
       client = LabArchivesClient()
       entries = client.fetch_entries(notebook_id="123")
       assert len(entries) > 0
   ```

3. **Performance tests:** Use `pytest-benchmark`:

   ```python
   def test_chunking_performance(benchmark):
       text = "lorem ipsum" * 10000
       result = benchmark(chunk_text, text, chunk_size=400)
       assert benchmark.stats.stats.mean < 0.1  # <100ms
   ```

4. **Mutation testing:** Run `mutmut` on critical chunking/validation logic:

   ```bash
   mutmut run --paths-to-mutate=src/vector_backend/chunking.py
   ```

**CI pipeline (GitHub Actions):**

```yaml
name: Vector Search Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: mamba-org/setup-micromamba@v1
        with:
          environment-file: environment.yml
      - run: pre-commit run --all-files
      - run: pytest tests/vector_backend/ -v --cov --cov-report=xml
      - run: pytest tests/vector_backend/integration/ --benchmark-only
      - uses: codecov/codecov-action@v3

**Mocking strategy:
* Mock OpenAI API with `respx` for deterministic embedding vectors.
* Mock Pinecone with in-memory index for fast tests.
* Use real LabArchives API in CI with dedicated test notebook (cleaned up after runs).

## 8. roadmap

{{ ... }}
* One-time bulk indexing script.
* Pinecone integration.
* Manual trigger for incremental updates.
* Hydra config + Pydantic validation.
* DVC tracking for embeddings.

**Phase 2 (1 week):** Automation
* Cron job for nightly incremental updates.
* Error handling + dead-letter queue.
* Monitoring dashboard (Grafana or simple HTML).

**Phase 3 (1 week):** Evaluation
* Build benchmark test set.
* Measure baseline performance.
* Document retrieval quality.

**Phase 4 (2 weeks):** Advanced features
* Metadata filters (notebook, date range, author).
* MCP tool: `search_notebooks(query, filters)`.
* Reindexing pipeline with version management.

**Phase 5 (2 weeks):** Production hardening
* Compare alternative embedding models.
* Implement quantization for Qdrant migration.
* Load testing (10K+ queries).
* Documentation: operator runbook.

**Phase 6 (ongoing):** Scaling
* Migrate to Qdrant when >50K chunks.
* Integrate with broader ILWS knowledge infrastructure.
* Add hybrid search (semantic + keyword).

**Orchestration approach:**
* Use GitHub Actions for scheduled reindexing (not Celery; simpler for now).
* MCP tool for on-demand reindexing: `reindex_notebooks(notebook_ids=None)`.
* External orchestrator (Airflow/Prefect) only if workflow complexity grows.

---

## 9. Expected Outcomes

* ✅ Days: working semantic search prototype (Pinecone).
* 🔄 Weeks: portable design, nightly incremental updates.
* 🚀 Months: scalable, filter-rich Qdrant index integrated into broader ILWS knowledge infrastructure.

---
