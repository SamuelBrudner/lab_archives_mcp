"""Onboarding payload tool."""

from __future__ import annotations

from typing import Any

from .. import onboard
from ..schemas.tool_responses import OnboardPayloadResponse
from .context import ToolContext
from .decorators import register_context_tool


async def get_onboard_payload(
    context: ToolContext, format: str = "json"
) -> OnboardPayloadResponse | str:
    """Return the onboarding payload as JSON or Markdown."""
    service = onboard.OnboardService(
        auth_manager=context.auth_manager,
        notebook_client=context.notebook_client,
        version=context.server_version,
    )
    payload = await service.get_payload()
    if format.lower() == "markdown":
        return payload.markdown
    return payload.as_dict()


def register_onboarding_tools(server: Any, context: ToolContext) -> None:
    """Register onboarding tools."""
    register_context_tool(server, context, get_onboard_payload)
