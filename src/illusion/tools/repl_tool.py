"""
最小 REPL shell 执行工具
=======================

本模块提供在类 REPL 环境中执行 shell 命令的功能。

主要组件：
    - ReplTool: REPL 风格的 shell 执行工具

使用示例：
    >>> from illusion.tools import ReplTool
    >>> tool = ReplTool()
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from pydantic import BaseModel, Field

from illusion.sandbox import SandboxUnavailableError
from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult
from illusion.utils.shell import create_shell_subprocess


class ReplToolInput(BaseModel):
    """REPL 工具参数。

    属性：
        command: 要执行的 shell 命令
        cwd: 可选的工作目录覆盖
        timeout_seconds: 超时秒数（1-600）
    """

    command: str = Field(description="Shell command to execute")
    cwd: str | None = Field(default=None, description="Working directory override")
    timeout_seconds: int = Field(default=120, ge=1, le=600)


class ReplTool(BaseTool):
    """使用类 REPL 的执行界面执行 shell 命令。

    用于在交互式环境中执行命令。
    """

    name = "repl"
    description = "Run shell commands using a REPL-style execution surface."
    input_model = ReplToolInput

    async def execute(self, arguments: ReplToolInput, context: ToolExecutionContext) -> ToolResult:
        # 解析工作目录
        cwd = Path(arguments.cwd).expanduser() if arguments.cwd else context.cwd
        try:
            # 创建 shell 子进程
            process = await create_shell_subprocess(
                arguments.command,
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
                output=f"Command timed out after {arguments.timeout_seconds} seconds",
                is_error=True,
            )

        # 收集输出
        parts = []
        if stdout:
            parts.append(stdout.decode("utf-8", errors="replace").rstrip())
        if stderr:
            parts.append(stderr.decode("utf-8", errors="replace").rstrip())

        text = "\n".join(part for part in parts if part).strip()
        if not text:
            text = "(no output)"

        # 截断过长的输出
        if len(text) > 12000:
            text = f"{text[:12000]}\n...[truncated]..."

        return ToolResult(
            output=text,
            is_error=process.returncode != 0,
            metadata={"returncode": process.returncode},
        )
