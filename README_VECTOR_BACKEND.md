# Vector Backend Module

**Status:** Initial scaffolding (2025-09-30)
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
- DVC-tracked local persistence (Parquet)
- Bulk upsert, search, delete operations

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

### 2. Set environment variables
```bash
export OPENAI_API_KEY="sk-..."
export PINECONE_API_KEY="..."
export PINECONE_ENVIRONMENT="us-east-1"
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
- [x] Test structure and fixtures
- [x] Documentation

### 🚧 In Progress
- [ ] Pinecone index integration
- [ ] Qdrant index integration
- [ ] Local persistence (Parquet + DVC)
- [ ] Integration tests with VCR.py
- [ ] Dead-letter queue for failed chunks

### 📋 Planned
- [ ] CLI for bulk indexing and reindexing
- [ ] Incremental update scheduler
- [ ] Evaluation benchmark
- [ ] MCP server integration (separate from this package)
- [ ] Production deployment guide

## Design Principles

Following the global development guidelines:

1. **FAIR** - DVC tracking, versioned configs, reproducible pipeline
2. **Modular** - Pure functions, protocol-based interfaces
3. **Config-driven** - Hydra YAML, no magic numbers
4. **Fail fast** - Pydantic validation, explicit error handling
5. **Tested** - 90% coverage target for pure functions
6. **Documented** - Docstrings, type hints, design docs

## Next Steps

1. **Phase 1 (current):** Implement Pinecone integration
2. **Phase 2:** Add local Parquet persistence with DVC
3. **Phase 3:** Build CLI for indexing operations
4. **Phase 4:** Create MCP tools that consume this backend
5. **Phase 5:** Production hardening and evaluation

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
