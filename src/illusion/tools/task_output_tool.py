"""
任务输出读取工具
================

本模块提供读取后台任务输出的功能。

主要组件：
    - TaskOutputTool: 读取任务输出日志的工具

使用示例：
    >>> from illusion.tools import TaskOutputTool
    >>> tool = TaskOutputTool()
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from illusion.tasks.manager import get_task_manager
from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class TaskOutputToolInput(BaseModel):
    """任务输出获取参数。

    属性：
        task_id: 任务标识符
        max_bytes: 最大返回字节数
    """

    task_id: str = Field(description="Task identifier")
    max_bytes: int = Field(default=12000, ge=1, le=100000)


class TaskOutputTool(BaseTool):
    """读取后台任务的输出。

    用于查看后台任务的输出日志。
    """

    name = "task_output"
    description = "Read the output log for a background task."
    input_model = TaskOutputToolInput

    def is_read_only(self, arguments: TaskOutputToolInput) -> bool:
        del arguments
        return True

    async def execute(self, arguments: TaskOutputToolInput, context: ToolExecutionContext) -> ToolResult:
        del context
        try:
            output = get_task_manager().read_task_output(arguments.task_id, max_bytes=arguments.max_bytes)
        except ValueError as exc:
            return ToolResult(output=str(exc), is_error=True)
        return ToolResult(output=output or "(no output)")
