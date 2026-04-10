"""
本地 cron 任务删除工具
====================

本模块提供删除本地 cron 任务的功能。

主要组件：
    - CronDeleteTool: 删除 cron 任务的工具

使用示例：
    >>> from illusion.tools import CronDeleteTool
    >>> tool = CronDeleteTool()
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from illusion.services.cron import delete_cron_job
from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class CronDeleteToolInput(BaseModel):
    """Cron 删除参数。

    属性：
        name: Cron 任务名称
    """

    name: str = Field(description="Cron job name")


class CronDeleteTool(BaseTool):
    """删除本地 cron 任务。

    取消之前通过 CronCreate 安排的任务。
    """

    name = "cron_delete"
    description = """Cancel a cron job previously scheduled with CronCreate. Removes it from .illusion/scheduled_tasks.json (durable jobs) or the in-memory session store (session-only jobs)."""
    input_model = CronDeleteToolInput

    async def execute(
        self,
        arguments: CronDeleteToolInput,
        context: ToolExecutionContext,
    ) -> ToolResult:
        del context
        # 删除 cron 任务
        if not delete_cron_job(arguments.name):
            return ToolResult(output=f"Cron job not found: {arguments.name}", is_error=True)
        return ToolResult(output=f"Deleted cron job {arguments.name}")
