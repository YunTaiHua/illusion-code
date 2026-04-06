"""Task exports."""

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
