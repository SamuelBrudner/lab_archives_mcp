"""Typed adapters for FastMCP decorators."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from inspect import signature
from typing import Any, TypeVar, cast

from .context import ToolContext

F = TypeVar("F", bound=Callable[..., Any])


def tool(server: Any) -> Callable[[F], F]:
    """Return ``server.tool()`` with the wrapped function type preserved."""
    return cast(Callable[[F], F], server.tool())


def resource(server: Any, uri: str) -> Callable[[F], F]:
    """Return ``server.resource(uri)`` with the wrapped function type preserved."""
    return cast(Callable[[F], F], server.resource(uri))


def register_context_tool(
    server: Any,
    context: ToolContext,
    handler: Callable[..., Awaitable[Any]],
) -> Callable[..., Awaitable[Any]]:
    """Register a context-first async handler as a FastMCP tool."""
    handler_signature = signature(handler)
    parameters = list(handler_signature.parameters.values())
    if not parameters or parameters[0].name != "context":
        raise ValueError(f"{handler.__name__} must accept context as its first parameter")

    @wraps(handler)
    async def bound_handler(*args: Any, **kwargs: Any) -> Any:
        return await handler(context, *args, **kwargs)

    cast(Any, bound_handler).__signature__ = handler_signature.replace(
        parameters=parameters[1:]
    )
    return tool(server)(bound_handler)
