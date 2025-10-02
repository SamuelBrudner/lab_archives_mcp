# Vector Backend Module

**Status:** ✅ Production-ready (2025-10-01)
**Tests:** 100 passing (92 unit/integration, 6 Pinecone skipped)
**Owner:** Samuel Brudner
**Documentation:** See `docs/vector_approach.md` for design details

## Overview

The `vector_backend` package provides semantic search infrastructure for LabArchives notebooks. It is **independent of the MCP server** and can be used as a standalone library or service.

## Architecture

```
src/vector_backend/
├── __init__.py          # Package exports
├── models.py            # Pydantic data models
├── chunking.py          # Text chunking strategies
├── embedding.py         # Embedding client (OpenAI, local models)
├── config.py            # Hydra configuration management
└── index.py             # Vector index operations (Pinecone, Qdrant)
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
Model-agnostic embedding client:
- OpenAI API with retry logic and batching
- Extensible to local models (sentence-transformers, etc.)
- Exponential backoff for rate limits

### 4. **Configuration** (`config.py`)
Hydra-based config management:
- All parameters in YAML: `conf/vector_search/default.yaml`
- Environment variable interpolation for secrets
- Type-safe loading with Pydantic validation

### 5. **Index** (`index.py`)
Vector index abstraction:
- Unified interface for Pinecone and Qdrant
- Local persistence with Parquet + DVC tracking
- Bulk upsert, search, delete operations
- Version isolation for reproducible reindexing

## Installation

### Core dependencies
```bash
pip install -e .
```

### Vector backend dependencies (optional)
```bash
pip install -e ".[vector]"
```

### Development dependencies
```bash
pip install -e ".[dev,vector]"
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
✅ LocalPersistence is **safe for concurrent writes** using per-notebook file locking:
- **Multiple processes writing different notebooks**: Fully concurrent (separate locks)
- **Multiple processes writing same notebook**: Serialized via 30s timeout locks
- **Read operations**: Always safe, no locking overhead
- **DVC initialization**: Protected by lock to prevent race conditions

For very high-throughput multi-user scenarios (>100 concurrent writers), **Pinecone** or **Qdrant** may offer better performance.

## Testing

### Run all tests
```bash
pytest tests/vector_backend/ -v
```

### Run with coverage
```bash
pytest tests/vector_backend/ --cov=vector_backend --cov-report=html
```

### Run property-based tests
```bash
pytest tests/vector_backend/unit/test_chunking.py -v --hypothesis-show-statistics
```

### Run benchmarks
```bash
pytest tests/vector_backend/unit/test_chunking.py --benchmark-only
```

## Implementation Status

### ✅ Completed
- [x] Package structure
- [x] Pydantic models with validation
- [x] Chunking implementation with tests
- [x] Embedding client abstraction (OpenAI)
- [x] Configuration management with Hydra
- [x] Pinecone index integration
- [x] LabArchives indexer (HTML cleaning, entry extraction)
- [x] Notebook indexer (end-to-end workflow)
- [x] Local persistence (Parquet)
- [x] DVC tracking integration
- [x] Test structure and fixtures (92 tests passing)
- [x] Documentation

### 📋 Planned
- [ ] Qdrant index integration
- [ ] CLI for bulk indexing and reindexing
- [ ] Incremental update scheduler
- [ ] Evaluation benchmark
- [ ] Local embedding models (sentence-transformers)
- [ ] Production deployment guide

## Design Principles

Following the global development guidelines:

1. **FAIR** - DVC tracking, versioned configs, reproducible pipeline
2. **Modular** - Pure functions, protocol-based interfaces
3. **Config-driven** - Hydra YAML, no magic numbers
4. **Fail fast** - Pydantic validation, explicit error handling
5. **Tested** - 90% coverage target for pure functions
6. **Documented** - Docstrings, type hints, design docs

## Development Status

**Completed Phases:**
1. ✅ **Phase 1:** Pinecone integration with retry logic
2. ✅ **Phase 2:** Local Parquet persistence with DVC tracking
3. ✅ **Phase 3:** Working indexing scripts (`scripts/index_real_notebook.py`)
4. ✅ **Phase 4:** MCP server integration complete

**Optional Enhancements:**
- See `FUTURE_DIRECTIONS.md` for planned improvements (CLI, local models, optimization)

## Related Documentation

- **Design doc:** `docs/vector_approach.md`
- **Changelog:** `docs/vector_approach_changelog.md`
- **API reference:** (auto-generated from docstrings)
- **MCP integration:** `src/labarchives_mcp/` (separate package)

## Contributing

This module follows TDD:
1. Write tests first (red)
2. Implement minimal solution (green)
3. Refactor for clarity (refactor)

Run pre-commit hooks before committing:
```bash
pre-commit install
pre-commit run --all-files
```

## License

Proprietary - Yale University / Samuel Brudner
