"""
休眠工具
========

本模块提供暂停执行的功能。

主要组件：
    - SleepTool: 暂停执行的工具

使用示例：
    >>> from illusion.tools import SleepTool
    >>> tool = SleepTool()
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class SleepToolInput(BaseModel):
    """休眠参数。

    属性：
        seconds: 休眠秒数
    """

    seconds: float = Field(default=1.0, ge=0.0, le=30.0)


class SleepTool(BaseTool):
    """短暂暂停执行。

    用于等待指定时间后继续执行。
    """

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
        # 异步休眠
        await asyncio.sleep(arguments.seconds)
        return ToolResult(output=f"Slept for {arguments.seconds} seconds")
