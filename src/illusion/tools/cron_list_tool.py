"""
本地 cron 任务列表工具
====================

本模块提供列出本地 cron 任务的功能。

主要组件：
    - CronListTool: 列出 cron 任务的工具

使用示例：
    >>> from illusion.tools import CronListTool
    >>> tool = CronListTool()
"""

from __future__ import annotations

from pydantic import BaseModel

from illusion.services.cron import load_cron_jobs
from illusion.services.cron_scheduler import is_scheduler_running
from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class CronListToolInput(BaseModel):
    """Cron 列表参数。"""


class CronListTool(BaseTool):
    """列出本地 cron 任务。

    列出通过 CronCreate 安排的所有 cron 任务，包括持久化和会话级别的任务。
    """

    name = "cron_list"
    description = """List all cron jobs scheduled via CronCreate, both durable (.illusion/scheduled_tasks.json) and session-only."""
    input_model = CronListToolInput

    def is_read_only(self, arguments: CronListToolInput) -> bool:
        del arguments
        return True

    async def execute(
        self,
        arguments: CronListToolInput,
        context: ToolExecutionContext,
    ) -> ToolResult:
        del arguments, context
        # 加载所有 cron 任务
        jobs = load_cron_jobs()
        if not jobs:
            return ToolResult(output="No cron jobs configured.")

        # 检查调度器状态
        scheduler = "running" if is_scheduler_running() else "stopped"
        lines = [f"Scheduler: {scheduler}", ""]

        # 格式化每个任务
        for job in jobs:
            enabled = "on" if job.get("enabled", True) else "off"
            last_run = job.get("last_run", "never")
            if last_run != "never":
                last_run = last_run[:19]
            next_run = job.get("next_run", "n/a")
            if next_run != "n/a":
                next_run = next_run[:19]
            last_status = job.get("last_status", "")
            status_str = f" ({last_status})" if last_status else ""
            lines.append(
                f"[{enabled}] {job['name']}  {job.get('schedule', '?')}\n"
                f"     cmd: {job['command']}\n"
                f"     last: {last_run}{status_str}  next: {next_run}"
            )
        return ToolResult(output="\n".join(lines))
