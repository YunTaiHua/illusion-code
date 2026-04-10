"""
停止任务辅助模块
================

本模块提供停止运行中任务的辅助函数。

使用示例：
    >>> from illusion.tasks.stop_task import stop_task
    >>> # 停止任务
    >>> await stop_task("task_id")
"""

from __future__ import annotations

from illusion.tasks.manager import get_task_manager
from illusion.tasks.types import TaskRecord


async def stop_task(task_id: str) -> TaskRecord:
    """通过默认任务管理器停止运行中的任务。"""
    return await get_task_manager().stop_task(task_id)