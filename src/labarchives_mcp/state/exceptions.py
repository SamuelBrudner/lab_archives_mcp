"""State-specific exception types."""


class StatePersistenceError(RuntimeError):
    """Base exception for persistent state load/save failures."""


class StateLoadError(StatePersistenceError):
    """Raised when an existing state file cannot be loaded safely."""


class StateSaveError(StatePersistenceError):
    """Raised when state cannot be persisted to disk."""


class GraphUpdateError(RuntimeError):
    """Raised when a project graph mutation cannot be completed."""
