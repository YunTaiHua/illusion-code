"""
任务停止工具
============

本模块提供停止正在运行的后台任务的功能。

主要组件：
    - TaskStopTool: 停止后台任务的工具

使用示例：
    >>> from illusion.tools import TaskStopTool
    >>> tool = TaskStopTool()
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from illusion.tasks.manager import get_task_manager
from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class TaskStopToolInput(BaseModel):
    """任务停止参数。

    属性：
        task_id: 任务标识符
    """

    task_id: str = Field(description="Task identifier")


class TaskStopTool(BaseTool):
    """停止后台任务。

    用于终止长时间运行的任务。
    """

    name = "task_stop"
    description = """- Stops a running background task by its ID
- Takes a task_id parameter identifying the task to stop
- Returns a success or failure status
- Use this tool when you need to terminate a long-running task"""
    input_model = TaskStopToolInput

    async def execute(self, arguments: TaskStopToolInput, context: ToolExecutionContext) -> ToolResult:
        del context
        try:
            task = await get_task_manager().stop_task(arguments.task_id)
        except ValueError as exc:
            return ToolResult(output=str(exc), is_error=True)
        return ToolResult(output=f"Stopped task {task.id}")
