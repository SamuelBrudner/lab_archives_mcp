"""Build-state tracking for vector index persistence.

Stores a compact record of the last successful "DB build" (indexing run)
so callers can decide to reuse the current artifacts or trigger a rebuild.

Use the path configured at VectorSearchConfig.incremental_updates.last_indexed_file
to store the record (defaults to "data/.last_indexed").
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vector_backend.config import VectorSearchConfig
from vector_backend.models import BuildRecord


def _safe_subset(config: VectorSearchConfig) -> dict[str, Any]:
    """Extract a deterministic, non-secret subset of configuration for hashing."""
    # Only include fields relevant to index structure and chunk/embedding behavior.
    return {
        "chunking": {
            "chunk_size": config.chunking.chunk_size,
            "overlap": config.chunking.overlap,
            "tokenizer": config.chunking.tokenizer,
            "preserve_boundaries": config.chunking.preserve_boundaries,
        },
        "embedding": {
            "model": config.embedding.model,
            "version": config.embedding.version,
            "dimensions": config.embedding.dimensions,
            "batch_size": config.embedding.batch_size,
        },
        "index": {
            "backend": config.index.backend,
            "index_name": config.index.index_name,
            "namespace": config.index.namespace,
            "environment": config.index.environment,
            "url": config.index.url,
        },
    }


def compute_config_fingerprint(config: VectorSearchConfig) -> str:
    """Compute a stable fingerprint for the current configuration.

    Returns a hex-encoded SHA256 hash of a canonical JSON representation
    of a secret-free subset of the configuration.
    """
    subset = _safe_subset(config)
    payload = json.dumps(subset, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def load_build_record(path: Path) -> BuildRecord | None:
    """Load build record from path if it exists, else return None."""
    try:
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return BuildRecord.model_validate(data)
    except Exception:
        return None


def save_build_record(path: Path, record: BuildRecord) -> None:
    """Persist build record to path (create parent directory if needed)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(record.model_dump_json(indent=2))


def should_rebuild(record: BuildRecord, current_fingerprint: str, embedding_version: str) -> bool:
    """Return True if a rebuild is recommended given the current configuration."""
    if record.config_fingerprint != current_fingerprint:
        return True
    if record.embedding_version != embedding_version:
        return True
    return False


def build_record_from_config(config: VectorSearchConfig) -> BuildRecord:
    """Create a BuildRecord for the provided configuration using current time."""
    return BuildRecord(
        built_at=datetime.now(UTC),
        embedding_version=config.embedding.version,
        config_fingerprint=compute_config_fingerprint(config),
        backend=config.index.backend,
        index_name=config.index.index_name,
        namespace=config.index.namespace,
    )
