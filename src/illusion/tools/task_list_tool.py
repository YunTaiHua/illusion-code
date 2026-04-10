"""
任务列表工具
============

本模块提供列出所有后台任务的功能。

主要组件：
    - TaskListTool: 列出任务的工具

使用示例：
    >>> from illusion.tools import TaskListTool
    >>> tool = TaskListTool()
"""

from __future__ import annotations

from pydantic import BaseModel

from illusion.tasks.manager import get_task_manager
from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class TaskListToolInput(BaseModel):
    """任务列表参数。"""


class TaskListTool(BaseTool):
    """列出后台任务。

    用于查看所有任务的概要信息。
    """

    name = "task_list"
    description = """Use this tool to list all tasks in the task list.

## When to Use This Tool

- To see what tasks are available to work on (status: 'pending', no owner, not blocked)
- To check overall progress on the project
- To find tasks that are blocked and need dependencies resolved
- After completing a task, to check for newly unblocked work or claim the next available task
- **Prefer working on tasks in ID order** (lowest ID first) when multiple tasks are available, as earlier tasks often set up context for later ones

## Output

Returns a summary of each task:
- **id**: Task identifier (use with TaskGet, TaskUpdate)
- **subject**: Brief description of the task
- **status**: 'pending', 'in_progress', or 'completed'
- **owner**: Agent ID if assigned, empty if available
- **blockedBy**: List of open task IDs that must be resolved first (tasks with blockedBy cannot be claimed until dependencies resolve)

Use TaskGet with a specific task ID to view full details including description and comments.

## Teammate Workflow

When working as a teammate:
1. After completing your current task, call TaskList to find available work
2. Look for tasks with status 'pending', no owner, and empty blockedBy
3. **Prefer tasks in ID order** (lowest ID first) when multiple tasks are available, as earlier tasks often set up context for later ones
4. Claim an available task using TaskUpdate (set `owner` to your name), or wait for leader assignment
5. If blocked, focus on unblocking tasks or notify the team lead"""
    input_model = TaskListToolInput

    def is_read_only(self, arguments: TaskListToolInput) -> bool:
        del arguments
        return True

    async def execute(self, arguments: TaskListToolInput, context: ToolExecutionContext) -> ToolResult:
        del context
        # 获取所有任务
        tasks = get_task_manager().list_tasks()
        if not tasks:
            return ToolResult(output="(no tasks)")

        # 构建已完成任务 ID 集合用于依赖过滤
        completed_ids = {t.id for t in tasks if t.status == "completed"}

        # 格式化每个任务
        lines: list[str] = []
        for task in tasks:
            subject = task.subject or task.description
            owner = task.owner or ""
            # 过滤 blockedBy 只显示未解决的依赖
            active_blockers = [bid for bid in task.blocked_by if bid not in completed_ids]
            blocked_str = f" blockedBy={active_blockers}" if active_blockers else ""
            owner_str = f" owner={owner}" if owner else ""
            lines.append(f"id={task.id} status={task.status} subject={subject}{owner_str}{blocked_str}")

        return ToolResult(output="\n".join(lines))
