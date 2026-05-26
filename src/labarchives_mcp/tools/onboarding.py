"""Onboarding payload tool."""

from __future__ import annotations

from typing import Any

from .. import onboard
from .context import ToolContext
from .decorators import tool


async def get_onboard_payload(context: ToolContext, format: str = "json") -> dict[str, Any] | str:
    """Return the onboarding payload as JSON or Markdown."""
    service = onboard.OnboardService(
        auth_manager=context.auth_manager,
        notebook_client=context.notebook_client,
        version=context.server_version,
    )
    payload = await service.get_payload()
    if format.lower() == "markdown":
        return payload.markdown
    return payload.model_dump()


_get_onboard_payload = get_onboard_payload


def register_onboarding_tools(server: Any, context: ToolContext) -> None:
    """Register onboarding tools."""

    @tool(server)
    async def get_onboard_payload(format: str = "json") -> dict[str, Any] | str:
        """Return the onboarding payload (json or markdown)."""
        return await _get_onboard_payload(context, format=format)
