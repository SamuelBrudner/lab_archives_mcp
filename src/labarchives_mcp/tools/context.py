"""Shared dependencies for MCP tool handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import httpx

from ..auth import AuthenticationManager, Credentials
from ..eln_client import LabArchivesClient
from ..state import StateManager

if TYPE_CHECKING:
    from ..settings import Settings


class HttpxModule(Protocol):
    """Subset of the httpx module currently used by sync tooling."""

    AsyncClient: type[httpx.AsyncClient]


class ServiceModule(Protocol):
    """Temporary typed shape for legacy module injection before explicit factories."""

    httpx: HttpxModule
    AuthenticationManager: type[AuthenticationManager]
    LabArchivesClient: type[LabArchivesClient]


@dataclass(slots=True)
class ToolContext:
    """Runtime dependencies passed into importable MCP handlers."""

    credentials: Credentials
    auth_manager: AuthenticationManager
    notebook_client: LabArchivesClient
    state_manager: StateManager
    server_version: str
    service_module: ServiceModule
    settings: Settings | None = None
