"""Unit tests for sync planning and incremental selection.

Covers:
- Sync decision outcomes based on BuildRecord, config fingerprint, and age
- Incremental entry filtering based on built_at timestamp
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from vector_backend.build_state import build_record_from_config, compute_config_fingerprint
from vector_backend.chunking import ChunkingConfig
from vector_backend.config import IncrementalUpdateConfig, IndexConfig, VectorSearchConfig
from vector_backend.embedding import EmbeddingConfig
from vector_backend.sync import plan_sync, select_incremental_entries


def _config() -> VectorSearchConfig:
    return VectorSearchConfig(
        chunking=ChunkingConfig(),
        embedding=EmbeddingConfig(
            model="openai/text-embedding-3-small", version="v1", dimensions=1536
        ),
        index=IndexConfig(backend="pinecone", index_name="idx", environment="us-east-1"),
        incremental_updates=IncrementalUpdateConfig(),
    )


class TestPlanSync:
    def test_no_record_triggers_rebuild(self) -> None:
        cfg = _config()
        fp = compute_config_fingerprint(cfg)
        decision = plan_sync(None, fp, cfg.embedding.version)
        assert decision["action"] == "rebuild"
        assert decision["reason"] == "no_record"

    def test_force_overrides_skip(self) -> None:
        cfg = _config()
        record = build_record_from_config(cfg)
        fp = compute_config_fingerprint(cfg)
        decision = plan_sync(record, fp, cfg.embedding.version, force=True)
        assert decision["action"] == "rebuild"
        assert decision["reason"] == "force"

    def test_match_skips_by_default(self) -> None:
        cfg = _config()
        record = build_record_from_config(cfg)
        fp = compute_config_fingerprint(cfg)
        decision = plan_sync(record, fp, cfg.embedding.version)
        assert decision["action"] == "skip"
        assert decision["reason"] == "up_to_date"

    def test_stale_triggers_incremental(self) -> None:
        cfg = _config()
        record = build_record_from_config(cfg)
        # backdate built_at by 2 days
        record.built_at = datetime.now(UTC) - timedelta(hours=48)
        fp = compute_config_fingerprint(cfg)
        decision = plan_sync(record, fp, cfg.embedding.version, max_age_hours=24)
        assert decision["action"] == "incremental"
        assert decision["reason"] == "stale"

    def test_config_change_triggers_rebuild(self) -> None:
        cfg = _config()
        record = build_record_from_config(cfg)
        changed = _config()
        changed.chunking = ChunkingConfig(chunk_size=999)
        fp_changed = compute_config_fingerprint(changed)
        decision = plan_sync(record, fp_changed, cfg.embedding.version)
        assert decision["action"] == "rebuild"
        assert decision["reason"] in ("config_changed", "embedding_changed")

    def test_embedding_version_change_triggers_rebuild(self) -> None:
        cfg = _config()
        record = build_record_from_config(cfg)
        fp = compute_config_fingerprint(cfg)
        decision = plan_sync(record, fp, "v2")
        assert decision["action"] == "rebuild"
        assert decision["reason"] == "embedding_changed"


class TestIncrementalSelection:
    def test_selects_entries_after_built_at(self) -> None:
        built_at = datetime(2025, 10, 1, 12, 0, 0, tzinfo=UTC)
        entries: list[dict[str, object]] = [
            {
                "eid": "1",
                "created_at": "2025-09-30T10:00:00Z",
                "updated_at": "2025-10-01T11:59:59Z",
            },
            {
                "eid": "2",
                "created_at": "2025-10-01T12:00:01Z",
                "updated_at": "2025-10-01T12:00:01Z",
            },
            {"eid": "3", "created_at": "2025-10-02T00:00:00Z"},
        ]
        selected = select_incremental_entries(entries, built_at)
        # eid 2 and 3 are after built_at; eid 1 is not
        assert [e["eid"] for e in selected] == ["2", "3"]

    def test_robust_to_missing_or_invalid_dates(self) -> None:
        built_at = datetime(2025, 10, 1, 12, 0, 0, tzinfo=UTC)
        entries: list[dict[str, object]] = [
            {"eid": "1", "created_at": None, "updated_at": None},
            {"eid": "2", "created_at": "not-a-date"},
            {"eid": "3", "updated_at": "2025-10-01T12:00:01Z"},
        ]
        # Only eid 3 is valid and after built_at
        selected = select_incremental_entries(entries, built_at)
        assert [e["eid"] for e in selected] == ["3"]
