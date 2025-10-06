"""Unit tests for vector_backend.build_state functionality.

Covers:
- Stable config fingerprint computation
- BuildRecord creation, persistence, and loading
- Rebuild decision logic
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from vector_backend.build_state import (
    build_record_from_config,
    compute_config_fingerprint,
    load_build_record,
    save_build_record,
    should_rebuild,
)
from vector_backend.chunking import ChunkingConfig
from vector_backend.config import IncrementalUpdateConfig, IndexConfig, VectorSearchConfig
from vector_backend.embedding import EmbeddingConfig
from vector_backend.models import BuildRecord


def make_config(
    *,
    chunk_size: int = 400,
    overlap: int = 50,
    tokenizer: str = "cl100k_base",
    preserve_boundaries: bool = True,
    embedding_model: str = "openai/text-embedding-3-small",
    embedding_version: str = "v1",
    dimensions: int = 1536,
    batch_size: int = 100,
    backend: str = "pinecone",
    index_name: str = "labarchives-semantic-search",
    namespace: str | None = None,
) -> VectorSearchConfig:
    """Helper to construct a valid VectorSearchConfig for tests."""

    chunking = ChunkingConfig(
        chunk_size=chunk_size,
        overlap=overlap,
        tokenizer=tokenizer,
        preserve_boundaries=preserve_boundaries,
    )
    embedding = EmbeddingConfig(
        model=embedding_model,
        version=embedding_version,
        dimensions=dimensions,
        batch_size=batch_size,
        api_key="dummy",  # should not influence fingerprint
    )
    index = IndexConfig(
        backend=backend,
        index_name=index_name,
        namespace=namespace,
        api_key="pc-xyz",  # should not influence fingerprint
        environment="us-east-1",
        url=None,
    )
    inc = IncrementalUpdateConfig(
        enabled=True, schedule="0 2 * * *", batch_size=200, last_indexed_file="data/.last_indexed"
    )
    return VectorSearchConfig(
        chunking=chunking, embedding=embedding, index=index, incremental_updates=inc
    )


class TestConfigFingerprint:
    def test_fingerprint_stable_and_secret_free(self) -> None:
        cfg1 = make_config()
        cfg2 = make_config()
        fp1 = compute_config_fingerprint(cfg1)
        fp2 = compute_config_fingerprint(cfg2)
        assert fp1 == fp2, "Same config should yield identical fingerprint"

        # Changing a secret (API keys) must NOT change the fingerprint
        cfg3 = make_config()
        cfg3.embedding.api_key = "different"
        cfg3.index.api_key = "other"
        fp3 = compute_config_fingerprint(cfg3)
        assert fp3 == fp1, "Secrets must be excluded from fingerprint"

        # Changing a relevant config field MUST change the fingerprint
        cfg4 = make_config(chunk_size=800)
        fp4 = compute_config_fingerprint(cfg4)
        assert fp4 != fp1, "Chunking changes must affect fingerprint"

    def test_fingerprint_changes_with_backend_details(self) -> None:
        base = make_config(backend="pinecone", index_name="idx-a", namespace=None)
        fp_base = compute_config_fingerprint(base)

        # Changing backend or index metadata should affect the fingerprint
        fp_ns = compute_config_fingerprint(make_config(namespace="ns-1"))
        fp_idx = compute_config_fingerprint(make_config(index_name="idx-b"))
        fp_backend = compute_config_fingerprint(make_config(backend="qdrant"))

        assert fp_ns != fp_base
        assert fp_idx != fp_base
        assert fp_backend != fp_base


class TestBuildRecordPersistence:
    def test_roundtrip_save_and_load(self, tmp_path: Path) -> None:
        cfg = make_config()
        record = build_record_from_config(cfg)

        path = tmp_path / ".last_indexed"
        save_build_record(path, record)

        loaded = load_build_record(path)
        assert isinstance(loaded, BuildRecord)
        assert loaded.model_dump() == record.model_dump()

    def test_load_missing_returns_none(self, tmp_path: Path) -> None:
        path = tmp_path / "does_not_exist.json"
        assert load_build_record(path) is None

    def test_load_invalid_json_returns_none(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("{not: valid json]")
        assert load_build_record(path) is None


class TestRebuildDecision:
    def test_should_rebuild_conditions(self) -> None:
        cfg = make_config()
        record = build_record_from_config(cfg)

        fp = compute_config_fingerprint(cfg)
        assert not should_rebuild(record, fp, cfg.embedding.version)

        # Different fingerprint triggers rebuild
        other_fp = compute_config_fingerprint(make_config(chunk_size=999))
        assert should_rebuild(record, other_fp, cfg.embedding.version)

        # Different embedding version triggers rebuild
        assert should_rebuild(record, fp, "v2")

    def test_build_record_from_config_fields(self) -> None:
        cfg = make_config(backend="pinecone", index_name="foo", namespace="bar")
        record = build_record_from_config(cfg)

        assert isinstance(record, BuildRecord)
        assert record.embedding_version == cfg.embedding.version
        assert record.backend == cfg.index.backend
        assert record.index_name == cfg.index.index_name
        assert record.namespace == cfg.index.namespace
        assert record.config_fingerprint == compute_config_fingerprint(cfg)

        # built_at should be recent (± 10 seconds)
        now = datetime.now(UTC)
        assert abs((now - record.built_at).total_seconds()) < 10
