"""
后台任务创建工具
================

本模块提供创建后台任务的功能，用于任务进度跟踪和状态管理。

主要组件：
    - TaskCreateTool: 创建后台任务的工具

使用示例：
    >>> from illusion.tools import TaskCreateTool
    >>> tool = TaskCreateTool()
"""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from illusion.tasks.manager import get_task_manager
from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class TaskCreateToolInput(BaseModel):
    """任务创建参数。

    属性：
        subject: 简短、可操作的任务标题（祈使形式）
        description: 需要完成的内容
        activeForm: 进行时显示的现在进行时形式
    """

    subject: str = Field(description="A brief, actionable title in imperative form (e.g., 'Fix authentication bug in login flow')")
    description: str = Field(description="What needs to be done")
    activeForm: str | None = Field(
        default=None,
        description="Present continuous form shown in spinner when in_progress (e.g., 'Fixing authentication bug')",
    )


class TaskCreateTool(BaseTool):
    """创建后台任务。

    用于创建结构化的任务列表来跟踪当前编码会话的进度。
    """

    name = "task_create"
    description = """Use this tool to create a structured task list for your current coding session. This helps you track progress, organize complex tasks, and demonstrate thoroughness to the user.
It also helps the user understand the progress of the task and overall progress of their requests.

## When to Use This Tool

Use this tool proactively in these scenarios:

- Complex multi-step tasks - When a task requires 3 or more distinct steps or actions
- Non-trivial and complex tasks - Tasks that require careful planning or multiple operations
- Plan mode - When using plan mode, create a task list to track the work
- User explicitly requests todo list - When the user directly asks you to use the todo list
- User provides multiple tasks - When users provide a list of things to be done (numbered or comma-separated)
- After receiving new instructions - Immediately capture user requirements as tasks
- When you start working on a task - Mark it as in_progress BEFORE beginning work
- After completing a task - Mark it as completed and add any new follow-up tasks discovered during implementation

## When NOT to Use This Tool

Skip using this tool when:
- There is only a single, straightforward task
- The task is trivial and tracking it provides no organizational benefit
- The task can be completed in less than 3 trivial steps
- The task is purely conversational or informational

NOTE that you should not use this tool if there is only one trivial task to do. In this case you are better off just doing the task directly.

## Task Fields

- **subject**: A brief, actionable title in imperative form (e.g., "Fix authentication bug in login flow")
- **description**: What needs to be done
- **activeForm** (optional): Present continuous form shown in the spinner when the task is in_progress (e.g., "Fixing authentication bug"). If omitted, the spinner shows the subject instead.

All tasks are created with status `pending`.

## Tips

- Create tasks with clear, specific subjects that describe the outcome
- After creating tasks, use TaskUpdate to set up dependencies (blocks/blockedBy) if needed
- Check TaskList first to avoid creating duplicate tasks"""
    input_model = TaskCreateToolInput

    async def execute(self, arguments: TaskCreateToolInput, context: ToolExecutionContext) -> ToolResult:
        del context
        # 获取任务管理器并创建任务
        manager = get_task_manager()
        task = manager.create_pending_task(
            subject=arguments.subject,
            description=arguments.description,
            active_form=arguments.activeForm,
        )
        return ToolResult(output=f"Created task {task.id}\nsubject: {task.subject}")
