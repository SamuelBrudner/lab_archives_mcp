# Vector Backend Module

**Status:** Implemented path supports OpenAI embeddings, Pinecone indexing, and local Parquet persistence (2025-10-01)
**Tests:** Covered by `tests/unit/vector_backend/`, `tests/integration/vector_backend/`,
and the repository `pytest` suite.
**Documentation:** This file is the vector backend guide. MCP onboarding payload examples live in `docs/onboard_example.json`.

## Overview

The `vector_backend` package provides semantic search infrastructure for LabArchives notebooks. It is **independent of the MCP server** and can be used as a standalone library or service.

## Architecture

```python
src/vector_backend/
├── __init__.py          # Package exports
├── models.py            # Pydantic data models
├── chunking.py          # Text chunking strategies
├── embedding.py         # Embedding client (OpenAI; local models are an extension point)
├── config.py            # Hydra configuration management
└── index.py             # Vector index operations (Pinecone; Qdrant is an extension point)
```

## Key Components

### 1. **Models** (`models.py`)

Pydantic schemas with fail-fast validation:

- `ChunkMetadata` - Metadata for text chunks
- `EmbeddedChunk` - Chunk + embedding vector
- `SearchRequest` / `SearchResult` - Search I/O
- `IndexStats` - Index health metrics

### 2. **Chunking** (`chunking.py`)

Token-aware text splitting:

- Uses `tiktoken` for accurate token counting
- Configurable chunk size, overlap, boundary preservation
- Deterministic: same input → same output

### 3. **Embedding** (`embedding.py`)

Embedding client:

- OpenAI API with retry logic and batching
- Local models are an extension point; `LocalEmbedding` raises `NotImplementedError`
- Exponential backoff for rate limits

### 4. **Configuration** (`config.py`)

Hydra-based config management:

- All parameters in YAML: `conf/vector_search/default.yaml`
- Environment variable interpolation for secrets
- Type-safe loading with Pydantic validation

### 5. **Index** (`index.py`)

Vector index abstraction:

- Implemented Pinecone index and Qdrant interface placeholder
- Local persistence with Parquet + DVC tracking
- Bulk upsert, search, delete operations
- Version isolation for reproducible reindexing

## Installation

### Core dependencies (includes Pinecone)

```bash
pip install -e .
```

### Optional vector backend dependencies

```bash
pip install -e ".[vector]"
```

This installs optional dependencies for extension work. The current `QdrantIndex`
class raises `NotImplementedError` until that backend is implemented.

### Development dependencies

```bash
pip install -e ".[dev]"
```

## Configuration

### 1. Create config directory

```bash
mkdir -p conf/vector_search
```

The default config is already created at `conf/vector_search/default.yaml`.

### 2. Populate `conf/secrets.yml`

```bash
cp conf/secrets.example.yml conf/secrets.yml
$EDITOR conf/secrets.yml
```

Add your `OPENAI_API_KEY`, `PINECONE_API_KEY`, and optional `PINECONE_ENVIRONMENT` values in that file. At runtime the tooling reads `conf/secrets.yml` automatically (or from the path set via `LABARCHIVES_CONFIG_PATH`).

> Prefer storing keys in the secrets file instead of exporting shell variables so they are available to all workflows and MCP clients by default.

### 3. Initialize DVC for embeddings (optional)

```bash
# In project root
dvc init

# Configure remote storage (e.g., S3)
dvc remote add -d myremote s3://mybucket/embeddings

# Or use local remote for testing
dvc remote add -d localremote /tmp/dvc-storage

# LocalPersistence will auto-track files when enable_dvc=True
```

## Usage Examples

### Chunking text

```python
from vector_backend.chunking import chunk_text

text = "Your lab notebook entry here..."
chunks = chunk_text(text, chunk_size=400, overlap=50)

for chunk in chunks:
    print(f"Chunk {chunk.chunk_index}: {chunk.token_count} tokens")
    print(chunk.text[:100])
```

### Generating embeddings

```python
import asyncio
from vector_backend.embedding import EmbeddingConfig, create_embedding_client

config = EmbeddingConfig(
    model="openai/text-embedding-3-small",
    version="v1",
    dimensions=1536,
    api_key="sk-..."
)

client = create_embedding_client(config)
vector = asyncio.run(client.embed_single("Test text"))
print(f"Generated {len(vector)}-dimensional vector")
```

### Loading configuration

```python
from vector_backend.config import load_config

config = load_config("default")
print(config.embedding.model)
print(config.chunking.chunk_size)

# With overrides
config = load_config("default", overrides=["embedding.version=v2"])
```

### Local persistence with DVC

```python
from pathlib import Path
from vector_backend.index import LocalPersistence

# Initialize persistence with DVC tracking
persistence = LocalPersistence(
    base_path=Path("data/embeddings"),
    version="v1",
    enable_dvc=True  # Automatically track with DVC
)

# Save chunks (auto-tracked if DVC enabled)
path = persistence.save_chunks("notebook_001", embedded_chunks)
print(f"Saved to {path} (DVC tracked: {persistence.is_dvc_enabled})")

# Load chunks
loaded_chunks = persistence.load_chunks("notebook_001")

# List all indexed notebooks
notebook_ids = persistence.list_notebooks()
```

**DVC Workflow:**

1. LocalPersistence automatically initializes DVC in the embeddings directory
2. Parquet files are tracked via `.dvc` files committed to git
3. Large embeddings live in DVC remote storage (S3, GCS, etc.)
4. Team members run `dvc pull` to download embeddings
5. Reproducible: version bump + reindex creates new tracked snapshots

**Concurrency Support:**
LocalPersistence is **safe for concurrent writes** using per-notebook file locking:

- **Multiple processes writing different notebooks**: Fully concurrent (separate locks)
- **Multiple processes writing same notebook**: Serialized via 30s timeout locks
- **Read operations**: Always safe, no locking overhead
- **DVC initialization**: Protected by lock to prevent race conditions

For high-throughput multi-user scenarios (>100 concurrent writers), Pinecone is the implemented managed-index path. Qdrant remains planned work in this repository.

## Testing

### Run all tests

```bash
pytest tests/unit/vector_backend tests/integration/vector_backend -v
```

### Run with coverage

```bash
pytest tests/unit/vector_backend tests/integration/vector_backend --cov=vector_backend --cov-report=html
```

### Run property-based tests

```bash
pytest tests/unit/vector_backend/test_chunking.py -v --hypothesis-show-statistics
```

### Run benchmarks

```bash
pytest tests/unit/vector_backend/test_chunking.py --benchmark-only
```

## Implementation Status

Implemented in this repository:

- Pydantic schemas for chunks, embeddings, search requests, search results, and build records
- Token-aware chunking with tests
- OpenAI embedding client
- Hydra configuration at `conf/vector_search/default.yaml`
- Pinecone index integration
- LabArchives notebook indexing
- Local Parquet persistence with optional DVC tracking
- MCP `sync_vector_index` planning and execution

Declared but not implemented:

- `QdrantIndex`
- `LocalEmbedding`

## Build Records

To avoid unnecessary re-indexing runs, the backend can persist a small "build record"
describing the last successful indexing build. The record includes:

- `built_at` (timestamp)
- `embedding_version` (from config)
- `config_fingerprint` (hash over relevant config keys)
- `backend`, `index_name`, `namespace`

By default, the path is controlled by `incremental_updates.last_indexed_file`
in `conf/vector_search/default.yaml` (defaults to `data/.last_indexed`).

The script `scripts/index_real_notebook.py` reads the record on startup and:

- Skips rebuild if the fingerprint and `embedding_version` match
- Otherwise performs a rebuild and writes a new record

This logic lives in `vector_backend.build_state` and the persisted schema
is defined as `vector_backend.models.BuildRecord`. For MCP usage, sync planning
is provided by `vector_backend.sync.plan_sync()` and incremental selection by
`vector_backend.sync.select_incremental_entries()`.

## MCP Sync

The MCP server exposes a `sync_vector_index` tool to coordinate indexing runs.

- Reads `conf/vector_search/default.yaml` (via `load_config`) and the persisted
  build record at `incremental_updates.last_indexed_file`.
- Decides one of:
  - `skip` (config + embedding match and within max-age)
  - `incremental` (stale by age threshold; process only changed entries)
  - `rebuild` (config/embedding changed or forced)
- Supports `dry_run=true` to return a plan without side effects.
- Execution requires a `notebook_id` scope; otherwise the tool returns the plan only.
  - Incremental: only changed entries since `built_at` are embedded and upserted
  - Rebuild: all pages in the notebook are re-indexed

Example call (from an MCP client):

```python
sync_vector_index {"force": false, "dry_run": true, "max_age_hours": 24}
```

Response (example):

```json
{
  "action": "incremental",
  "reason": "stale",
  "built_at": "2025-10-01T12:00:00+00:00",
  "dry_run": true
}
```

## Related Documentation

- **Setup:** `docs/QUICKSTART.md`
- **Pinecone configuration:** `docs/PINECONE_SETUP.md`
- **MCP integration:** `src/labarchives_mcp/`
- **Vector backend code:** `src/vector_backend/`
- **Tests:** `tests/unit/vector_backend/` and `tests/integration/vector_backend/`

## License

MIT License — see `LICENSE`
