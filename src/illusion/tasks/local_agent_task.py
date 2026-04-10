"""
本地 Agent 任务外观模块
==================

本模块提供本地 agent 子进程任务的简单接口。

使用示例：
    >>> from illusion.tasks.local_agent_task import spawn_local_agent_task
    >>> # 启动本地 agent 任务
    >>> record = await spawn_local_agent_task(
    ...     prompt="帮我写一个 Hello World 程序",
    ...     description="编写程序",
    ...     cwd="."
    ... )
"""

from __future__ import annotations

from pathlib import Path

from illusion.tasks.manager import get_task_manager
from illusion.tasks.types import TaskRecord


async def spawn_local_agent_task(
    *,
    prompt: str,
    description: str,
    cwd: str | Path,
    model: str | None = None,
    api_key: str | None = None,
    command: str | None = None,
) -> TaskRecord:
    """启动本地 agent 子进程任务。"""
    return await get_task_manager().create_agent_task(
        prompt=prompt,
        description=description,
        cwd=cwd,
        model=model,
        api_key=api_key,
        command=command,
    )