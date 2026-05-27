"""Disk persistence for session state."""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import ValidationError

from ..settings import default_state_dir
from .constants import GRAPH_SCHEMA_VERSION
from .exceptions import StateLoadError, StateSaveError
from .models import SessionState


class StateRepository:
    """Loads, migrates, and saves session state on disk."""

    def __init__(self, storage_dir: Path | str | None = None) -> None:
        if storage_dir is None:
            storage_dir = default_state_dir()
        self.storage_dir = Path(storage_dir)
        self.state_file = self.storage_dir / "session_state.json"

    def load(self) -> SessionState:
        """Load state from disk or create fresh."""
        if not self.state_file.exists():
            return SessionState(active_context_id=None, contexts={})

        try:
            with open(self.state_file, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise TypeError("State file must contain a JSON object")
            migrated = self.migrate_state_dict(data)
            return SessionState.model_validate(migrated)
        except (OSError, json.JSONDecodeError, TypeError, ValidationError, ValueError) as exc:
            backup_path = self.state_file.with_suffix(".json.bak")
            try:
                shutil.copy(self.state_file, backup_path)
                logger.warning(f"Corrupted state backed up to {backup_path}")
            except OSError as backup_err:
                logger.error(f"Failed to backup unreadable state: {backup_err}")

            raise StateLoadError(f"Failed to load state from {self.state_file}") from exc

    def save(self, state: SessionState) -> None:
        """Persist current state to disk using atomic write pattern."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Write to temp file first
        temp_file = self.state_file.with_suffix(".tmp")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(state.model_dump_json(indent=2))
                f.flush()
                os.fsync(f.fileno())

            # Atomic rename
            temp_file.replace(self.state_file)
        except (OSError, TypeError, ValueError) as exc:
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except OSError as cleanup_err:
                logger.error(f"Failed to remove temporary state file {temp_file}: {cleanup_err}")
            raise StateSaveError(f"Failed to save state to {self.state_file}") from exc

    def migrate_state_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Ensure graph data carries schema version and baseline metadata."""
        contexts = data.get("contexts") or {}
        now = time.time()

        if not isinstance(contexts, dict):
            return data

        for ctx in contexts.values():
            if not isinstance(ctx, dict):
                continue
            graph_data = ctx.get("graph_data") or {}
            ctx["graph_data"] = self.migrate_graph_data(graph_data, now)

        data["contexts"] = contexts
        return data

    def migrate_graph_data(
        self, graph_data: dict[str, Any], default_ts: float | None = None
    ) -> dict[str, Any]:
        """Backfill schema_version and timing metadata for nodes/edges."""
        ts = default_ts or time.time()
        graph_data = graph_data or {}

        nodes = graph_data.get("nodes") or []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node.setdefault("first_seen", ts)
            node.setdefault("last_seen", ts)

        links = graph_data.get("links") or []
        for edge in links:
            if not isinstance(edge, dict):
                continue
            edge.setdefault("created_at", ts)
            edge.setdefault("last_seen", ts)

        meta = graph_data.get("graph")
        if not isinstance(meta, dict):
            meta = {}
        meta.setdefault("schema_version", GRAPH_SCHEMA_VERSION)

        graph_data["nodes"] = nodes
        graph_data["links"] = links
        graph_data["graph"] = meta
        graph_data.setdefault("directed", True)
        graph_data.setdefault("multigraph", False)
        return graph_data
