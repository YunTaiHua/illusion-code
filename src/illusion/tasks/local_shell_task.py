"""
本地 Shell 任务外观模块
=====================

本模块提供本地 shell 任务的简单接口。

使用示例：
    >>> from illusion.tasks.local_shell_task import spawn_shell_task
    >>> # 启动本地 shell 任务
    >>> record = await spawn_shell_task("ls -la", "列出文件", ".")
"""

from __future__ import annotations

from pathlib import Path

from illusion.tasks.manager import get_task_manager
from illusion.tasks.types import TaskRecord


async def spawn_shell_task(command: str, description: str, cwd: str | Path) -> TaskRecord:
    """启动本地 shell 任务。"""
    return await get_task_manager().create_shell_task(
        command=command,
        description=description,
        cwd=cwd,
    )