"""
本地 cron 任务开关工具
====================

本模块提供启用或禁用本地 cron 任务的功能。

主要组件：
    - CronToggleTool: 切换 cron 任务状态的工具

使用示例：
    >>> from illusion.tools import CronToggleTool
    >>> tool = CronToggleTool()
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from illusion.services.cron import set_job_enabled
from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class CronToggleToolInput(BaseModel):
    """Cron 切换参数。

    属性：
        name: Cron 任务名称
        enabled: true 启用，false 禁用
    """

    name: str = Field(description="Cron job name")
    enabled: bool = Field(description="True to enable, False to disable")


class CronToggleTool(BaseTool):
    """启用或禁用本地 cron 任务。

    通过名称启用或禁用本地 cron 任务。
    """

    name = "cron_toggle"
    description = "Enable or disable a local cron job by name."
    input_model = CronToggleToolInput

    async def execute(
        self,
        arguments: CronToggleToolInput,
        context: ToolExecutionContext,
    ) -> ToolResult:
        del context
        # 设置任务启用状态
        if not set_job_enabled(arguments.name, arguments.enabled):
            return ToolResult(
                output=f"Cron job not found: {arguments.name}",
                is_error=True,
            )
        state = "enabled" if arguments.enabled else "disabled"
        return ToolResult(output=f"Cron job '{arguments.name}' is now {state}")
