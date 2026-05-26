"""Typed adapters for FastMCP decorators."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar, cast

F = TypeVar("F", bound=Callable[..., Any])


def tool(server: Any) -> Callable[[F], F]:
    """Return ``server.tool()`` with the wrapped function type preserved."""
    return cast(Callable[[F], F], server.tool())


def resource(server: Any, uri: str) -> Callable[[F], F]:
    """Return ``server.resource(uri)`` with the wrapped function type preserved."""
    return cast(Callable[[F], F], server.resource(uri))
