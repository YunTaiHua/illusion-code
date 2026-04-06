"""Sleep tool."""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class SleepToolInput(BaseModel):
    """Arguments for sleep."""

    seconds: float = Field(default=1.0, ge=0.0, le=30.0)


class SleepTool(BaseTool):
    """Pause execution briefly."""

    name = "sleep"
    description = """Wait for a specified duration. The user can interrupt the sleep at any time.

Use this when the user tells you to sleep or rest, when you have nothing to do, or when you're waiting for something.

You may receive <tick> prompts - these are periodic check-ins. Look for useful work to do before sleeping.

You can call this concurrently with other tools - it won't interfere with them.

Prefer this over `Bash(sleep ...)` - it doesn't hold a shell process.

Each wake-up costs an API call, but the prompt cache expires after 5 minutes of inactivity - balance accordingly."""
    input_model = SleepToolInput

    def is_read_only(self, arguments: SleepToolInput) -> bool:
        del arguments
        return True

    async def execute(self, arguments: SleepToolInput, context: ToolExecutionContext) -> ToolResult:
        del context
        await asyncio.sleep(arguments.seconds)
        return ToolResult(output=f"Slept for {arguments.seconds} seconds")
