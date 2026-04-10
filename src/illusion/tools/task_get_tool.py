"""
任务详情获取工具
================

本模块提供获取任务详细信息的功能，用于查看任务状态和依赖关系。

主要组件：
    - TaskGetTool: 获取任务详情的工具

使用示例：
    >>> from illusion.tools import TaskGetTool
    >>> tool = TaskGetTool()
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from illusion.tasks.manager import get_task_manager
from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class TaskGetToolInput(BaseModel):
    """任务查找参数。

    属性：
        task_id: 任务标识符
    """

    task_id: str = Field(description="Task identifier")


class TaskGetTool(BaseTool):
    """返回详细的任务状态。

    用于获取任务的完整描述和上下文。
    """

    name = "task_get"
    description = """Use this tool to retrieve a task by its ID from the task list.

## When to Use This Tool

- When you need the full description and context before starting work on a task
- To understand task dependencies (what it blocks, what blocks it)
- After being assigned a task, to get complete requirements

## Output

Returns full task details:
- **subject**: Task title
- **description**: Detailed requirements and context
- **status**: 'pending', 'in_progress', or 'completed'
- **blocks**: Tasks waiting on this one to complete
- **blockedBy**: Tasks that must complete before this one can start

## Tips

- After fetching a task, verify its blockedBy list is empty before beginning work.
- Use TaskList to see all tasks in summary form."""
    input_model = TaskGetToolInput

    def is_read_only(self, arguments: TaskGetToolInput) -> bool:
        del arguments
        return True

    async def execute(self, arguments: TaskGetToolInput, context: ToolExecutionContext) -> ToolResult:
        del context
        # 获取任务
        task = get_task_manager().get_task(arguments.task_id)
        if task is None:
            return ToolResult(output=f"No task found with ID: {arguments.task_id}", is_error=True)

        # 构建与参考格式匹配的结构化输出
        parts = [
            f"id: {task.id}",
            f"subject: {task.subject or task.description}",
        ]
        if task.description and task.subject:
            parts.append(f"description: {task.description}")
        parts.append(f"status: {task.status}")
        if task.owner:
            parts.append(f"owner: {task.owner}")
        if task.blocks:
            parts.append(f"blocks: {task.blocks}")
        if task.blocked_by:
            parts.append(f"blockedBy: {task.blocked_by}")
        if task.active_form:
            parts.append(f"activeForm: {task.active_form}")

        return ToolResult(output="\n".join(parts))
