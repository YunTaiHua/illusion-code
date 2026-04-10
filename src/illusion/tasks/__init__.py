"""
任务模块导出
==========

本模块导出 tasks 子目录中的公共接口。

导出内容：
    - BackgroundTaskManager: 后台任务管理器
    - TaskRecord: 任务记录
    - TaskStatus: 任务状态类型
    - TaskType: 任务类型
    - get_task_manager: 获取任务管理器
    - spawn_local_agent_task: 启动本地 agent 任务
    - spawn_shell_task: 启动 shell 任务
    - stop_task: 停止任务
"""

from illusion.tasks.local_agent_task import spawn_local_agent_task
from illusion.tasks.local_shell_task import spawn_shell_task
from illusion.tasks.manager import BackgroundTaskManager, get_task_manager
from illusion.tasks.stop_task import stop_task
from illusion.tasks.types import TaskRecord, TaskStatus, TaskType

__all__ = [
    "BackgroundTaskManager",
    "TaskRecord",
    "TaskStatus",
    "TaskType",
    "get_task_manager",
    "spawn_local_agent_task",
    "spawn_shell_task",
    "stop_task",
]