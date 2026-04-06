"""Interactive permission prompt."""

from __future__ import annotations

from prompt_toolkit import PromptSession


async def ask_permission(tool_name: str, reason: str) -> bool:
    """Prompt the user to approve a mutating tool."""
    session = PromptSession()
    response = await session.prompt_async(
        f"Allow tool '{tool_name}'? [{reason}] [y/N]: "
    )
    return response.strip().lower() in {"y", "yes"}
