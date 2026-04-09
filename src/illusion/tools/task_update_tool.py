"""Tool for updating background task metadata."""

from __future__ import annotations

from pydantic import BaseModel, Field

from illusion.tasks.manager import get_task_manager
from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class TaskUpdateToolInput(BaseModel):
    """Arguments for task updates."""

    task_id: str = Field(description="Task identifier")
    subject: str | None = Field(default=None, description="New subject for the task")
    description: str | None = Field(default=None, description="Updated task description")
    active_form: str | None = Field(
        default=None,
        description="Present continuous form shown in spinner when in_progress (e.g., 'Running tests')",
    )
    status: str | None = Field(default=None, description="New task status (pending, in_progress, completed, deleted)")
    owner: str | None = Field(default=None, description="New owner for the task")
    progress: int | None = Field(default=None, ge=0, le=100, description="Progress percentage")
    status_note: str | None = Field(default=None, description="Short human-readable task note")
    metadata: dict | None = Field(
        default=None,
        description="Metadata keys to merge into the task (set a key to null to delete it)",
    )
    add_blocks: list[str] | None = Field(
        default=None,
        description="Task IDs that cannot start until this one completes",
    )
    add_blocked_by: list[str] | None = Field(
        default=None,
        description="Task IDs that must complete before this one can start",
    )


class TaskUpdateTool(BaseTool):
    """Update task metadata for progress tracking."""

    name = "task_update"
    description = """Use this tool to update a task in the task list.

## When to Use This Tool

**Mark tasks as resolved:**
- When you have completed the work described in a task
- When a task is no longer needed or has been superseded
- IMPORTANT: Always mark your assigned tasks as resolved when you finish them
- After resolving, call TaskList to find your next task

- ONLY mark a task as completed when you have FULLY accomplished it
- If you encounter errors, blockers, or cannot finish, keep the task as in_progress
- When blocked, create a new task describing what needs to be resolved
- Never mark a task as completed if:
  - Tests are failing
  - Implementation is partial
  - You encountered unresolved errors
  - You couldn't find necessary files or dependencies

**Delete tasks:**
- When a task is no longer relevant or was created in error
- Setting status to `deleted` permanently removes the task

**Update task details:**
- When requirements change or become clearer
- When establishing dependencies between tasks

## Fields You Can Update

- **status**: The task status (see Status Workflow below)
- **subject**: Change the task title (imperative form, e.g., "Run tests")
- **description**: Change the task description
- **activeForm**: Present continuous form shown in spinner when in_progress (e.g., "Running tests")
- **owner**: Change the task owner (agent name)
- **metadata**: Merge metadata keys into the task (set a key to null to delete it)
- **addBlocks**: Mark tasks that cannot start until this one completes
- **addBlockedBy**: Mark tasks that must complete before this one can start

## Status Workflow

Status progresses: `pending` -> `in_progress` -> `completed`

Use `deleted` to permanently remove a task.

## Staleness

Make sure to read a task's latest state using `TaskGet` before updating it.

## Examples

Mark task as in progress when starting work:
```json
{"taskId": "1", "status": "in_progress"}
```

Mark task as completed after finishing work:
```json
{"taskId": "1", "status": "completed"}
```

Delete a task:
```json
{"taskId": "1", "status": "deleted"}
```

Claim a task by setting owner:
```json
{"taskId": "1", "owner": "my-name"}
```

Set up task dependencies:
```json
{"taskId": "2", "addBlockedBy": ["1"]}
```"""
    input_model = TaskUpdateToolInput

    async def execute(
        self,
        arguments: TaskUpdateToolInput,
        context: ToolExecutionContext,
    ) -> ToolResult:
        del context
        try:
            task = get_task_manager().update_task(
                arguments.task_id,
                subject=arguments.subject,
                description=arguments.description,
                active_form=arguments.active_form,
                status=arguments.status,
                owner=arguments.owner,
                progress=arguments.progress,
                status_note=arguments.status_note,
                metadata=arguments.metadata,
                add_blocks=arguments.add_blocks,
                add_blocked_by=arguments.add_blocked_by,
            )
        except ValueError as exc:
            message = str(exc)
            if message.startswith("No task found with ID:"):
                return ToolResult(
                    output=(
                        f"Ignored stale task_update for missing task {arguments.task_id}. "
                        "Run task_list to refresh IDs before updating."
                    ),
                    is_error=False,
                )
            return ToolResult(output=message, is_error=True)

        if arguments.status == "deleted":
            return ToolResult(output=f"Deleted task {task.id}")

        parts = [f"Updated task {task.id}"]
        if arguments.subject:
            parts.append(f"subject={task.subject}")
        if arguments.description:
            parts.append(f"description={task.description}")
        if arguments.active_form:
            parts.append(f"activeForm={task.active_form}")
        if arguments.status:
            parts.append(f"status={task.status}")
        if arguments.owner:
            parts.append(f"owner={task.owner}")
        if arguments.progress is not None:
            parts.append(f"progress={task.metadata.get('progress', '')}%")
        if arguments.status_note:
            parts.append(f"note={task.metadata.get('status_note', '')}")
        if arguments.add_blocks:
            parts.append(f"blocks={task.blocks}")
        if arguments.add_blocked_by:
            parts.append(f"blockedBy={task.blocked_by}")
        return ToolResult(output=" ".join(parts))
