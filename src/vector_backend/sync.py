"""Sync planning and incremental selection helpers for MCP integration.

These pure functions make it easy to TDD the MCP sync behavior:
- Decide whether to skip, do incremental, or rebuild
- Select only changed entries since the last successful build
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, TypedDict

from vector_backend.build_state import should_rebuild
from vector_backend.models import BuildRecord


class SyncDecision(TypedDict):
    action: str  # "skip" | "incremental" | "rebuild"
    reason: str
    built_at: str | None


def plan_sync(
    record: BuildRecord | None,
    current_fingerprint: str,
    embedding_version: str,
    *,
    force: bool = False,
    max_age_hours: int | None = None,
    now: datetime | None = None,
) -> SyncDecision:
    """Return a sync plan based on build record and current configuration.

    Args:
        record: Previously saved BuildRecord (or None)
        current_fingerprint: Current config fingerprint
        embedding_version: Current embedding version
        force: Force a rebuild regardless of record
        max_age_hours: If set and record is older than this, do incremental
        now: Testing hook; defaults to datetime.now(UTC)

    Returns:
        SyncDecision with action and reason
    """
    if force:
        return {
            "action": "rebuild",
            "reason": "force",
            "built_at": record.built_at.isoformat() if record else None,
        }

    if record is None:
        return {"action": "rebuild", "reason": "no_record", "built_at": None}

    if should_rebuild(record, current_fingerprint, embedding_version):
        # Attempt to be explicit about the reason
        if record.config_fingerprint != current_fingerprint:
            reason = "config_changed"
        elif record.embedding_version != embedding_version:
            reason = "embedding_changed"
        else:
            reason = "stale_config"
        return {"action": "rebuild", "reason": reason, "built_at": record.built_at.isoformat()}

    # Record matches configuration
    if max_age_hours is not None:
        now_dt = now or datetime.now(UTC)
        if (now_dt - record.built_at) > timedelta(hours=max_age_hours):
            return {
                "action": "incremental",
                "reason": "stale",
                "built_at": record.built_at.isoformat(),
            }
    return {
        "action": "skip",
        "reason": "up_to_date",
        "built_at": record.built_at.isoformat(),
    }


def _parse_when(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        # Accept Z suffix
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def select_incremental_entries(
    entries: list[dict[str, Any]], built_after: datetime
) -> list[dict[str, Any]]:
    """Return entries whose created_at or updated_at are strictly after built_after.

    Entries with missing or invalid timestamps are excluded (conservative default
    to avoid unnecessary re-indexing).
    """
    selected: list[dict[str, Any]] = []
    for e in entries:
        updated = _parse_when(e.get("updated_at"))
        created = _parse_when(e.get("created_at"))
        if (updated and updated > built_after) or (created and created > built_after):
            selected.append(e)
    return selected
