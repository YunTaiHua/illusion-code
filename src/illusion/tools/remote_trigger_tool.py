"""
远程触发工具
============

本模块提供按需触发本地命名任务的功能。

主要组件：
    - RemoteTriggerTool: 立即运行注册 cron 任务的工具

使用示例：
    >>> from illusion.tools import RemoteTriggerTool
    >>> tool = RemoteTriggerTool()
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from pydantic import BaseModel, Field

from illusion.services.cron import get_cron_job
from illusion.sandbox import SandboxUnavailableError
from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult
from illusion.utils.shell import create_shell_subprocess


class RemoteTriggerToolInput(BaseModel):
    """远程触发参数。

    属性：
        name: Cron 任务名称
        timeout_seconds: 超时秒数
    """

    name: str = Field(description="Cron job name")
    timeout_seconds: int = Field(default=120, ge=1, le=600)


class RemoteTriggerTool(BaseTool):
    """立即运行已注册的任务。

    用于手动触发按需任务。
    """

    name = "remote_trigger"
    description = """Call the illusion.ai remote-trigger API. Use this instead of curl — the OAuth token is added automatically in-process and never exposed.

Actions:
- list: GET /v1/code/triggers
- get: GET /v1/code/triggers/{trigger_id}
- create: POST /v1/code/triggers (requires body)
- update: POST /v1/code/triggers/{trigger_id} (requires body, partial update)
- run: POST /v1/code/triggers/{trigger_id}/run

The response is the raw JSON from the API."""
    input_model = RemoteTriggerToolInput

    async def execute(
        self,
        arguments: RemoteTriggerToolInput,
        context: ToolExecutionContext,
    ) -> ToolResult:
        # 获取 cron 任务
        job = get_cron_job(arguments.name)
        if job is None:
            return ToolResult(output=f"Cron job not found: {arguments.name}", is_error=True)

        # 解析工作目录
        cwd = Path(job.get("cwd") or context.cwd).expanduser()
        try:
            # 创建 shell 子进程
            process = await create_shell_subprocess(
                str(job["command"]),
                cwd=cwd,
                stdin=asyncio.subprocess.DEVNULL,  # 防止 Windows 上的句柄继承死锁
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except SandboxUnavailableError as exc:
            return ToolResult(output=str(exc), is_error=True)

        try:
            # 等待命令完成
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=arguments.timeout_seconds,
            )
        except asyncio.TimeoutError:
            # 超时后终止进程
            process.kill()
            await process.wait()
            return ToolResult(
                output=f"Remote trigger timed out after {arguments.timeout_seconds} seconds",
                is_error=True,
            )

        # 收集输出
        parts = []
        if stdout:
            parts.append(stdout.decode("utf-8", errors="replace").rstrip())
        if stderr:
            parts.append(stderr.decode("utf-8", errors="replace").rstrip())
        body = "\n".join(part for part in parts if part).strip() or "(no output)"
        return ToolResult(
            output=f"Triggered {arguments.name}\n{body}",
            is_error=process.returncode != 0,
            metadata={"returncode": process.returncode},
        )
