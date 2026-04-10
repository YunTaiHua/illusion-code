"""
团队删除工具
============

本模块提供删除内存中团队的功能。

主要组件：
    - TeamDeleteTool: 删除团队的工areness

使用示例：
    >>> from illusion.tools import TeamDeleteTool
    >>> tool = TeamDeleteTool()
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from illusion.coordinator.coordinator_mode import get_team_registry
from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class TeamDeleteToolInput(BaseModel):
    """团队删除参数。

    属性：
        name: 团队名称
    """

    name: str = Field(description="Team name")


class TeamDeleteTool(BaseTool):
    """删除内存中团队。

    用于在 swarm 工作完成后清理团队和任务目录。
    """

    name = "team_delete"
    description = """# TeamDelete

Remove team and task directories when the swarm work is complete.

This operation:
- Removes the team directory (`~/.illusion/teams/{team-name}/`)
- Removes the task directory (`~/.illusion/tasks/{team-name}/`)
- Clears team context from the current session

**IMPORTANT**: TeamDelete will fail if the team still has active members. Gracefully terminate teammates first, then call TeamDelete after all teammates have shut down.

Use this when all teammates have finished their work and you want to clean up the team resources. The team name is automatically determined from the current session's team context.
"""
    input_model = TeamDeleteToolInput

    async def execute(self, arguments: TeamDeleteToolInput, context: ToolExecutionContext) -> ToolResult:
        del context
        try:
            get_team_registry().delete_team(arguments.name)
        except ValueError as exc:
            return ToolResult(output=str(exc), is_error=True)
        return ToolResult(output=f"Deleted team {arguments.name}")
