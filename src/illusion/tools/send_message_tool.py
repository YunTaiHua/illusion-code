"""
发送消息工具
============

本模块提供向运行中的代理任务发送消息的功能。

主要组件：
    - SendMessageTool: 向代理发送消息的工具

使用示例：
    >>> from illusion.tools import SendMessageTool
    >>> tool = SendMessageTool()
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from illusion.swarm.registry import get_backend_registry
from illusion.swarm.types import TeammateMessage
from illusion.tasks.manager import get_task_manager
from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult

# 配置模块级日志记录器
logger = logging.getLogger(__name__)


class SendMessageToolInput(BaseModel):
    """发送消息参数。

    属性：
        task_id: 目标本地代理任务 ID 或 swarm agent_id (name@team)
        message: 写入任务 stdin 的消息
    """

    task_id: str = Field(description="Target local agent task id or swarm agent_id (name@team)")
    message: str = Field(description="Message to write to the task stdin")


class SendMessageTool(BaseTool):
    """向运行中的本地代理任务发送消息。

    用于与代理通信或发送继续指令。
    """

    name = "send_message"
    description = """# SendMessage

Send a message to another agent.

```json
{"to": "researcher", "summary": "assign task 1", "message": "start on task #1"}
```

| `to` | |
|---|---|
| `"researcher"` | Teammate by name |
| `"*"` | Broadcast to all teammates -- expensive (linear in team size), use only when everyone genuinely needs it |

Your plain text output is NOT visible to other agents -- to communicate, you MUST call this tool. Messages from teammates are delivered automatically; you don't check an inbox. Refer to teammates by name, never by UUID. When relaying, don't quote the original -- it's already rendered to the user.

## Protocol responses (legacy)

If you receive a JSON message with `type: "shutdown_request"` or `type: "plan_approval_request"`, respond with the matching `_response` type -- echo the `request_id`, set `approve` true/false:

```json
{"to": "team-lead", "message": {"type": "shutdown_response", "request_id": "...", "approve": true}}
{"to": "researcher", "message": {"type": "plan_approval_response", "request_id": "...", "approve": false, "feedback": "add error handling"}}
```

Approving shutdown terminates your process. Rejecting plan sends the teammate back to revise. Don't originate `shutdown_request` unless asked. Don't send structured JSON status messages -- use TaskUpdate.
"""
    input_model = SendMessageToolInput

    async def execute(self, arguments: SendMessageToolInput, context: ToolExecutionContext) -> ToolResult:
        del context
        # Swarm agents 使用 agent_id 格式 (name@team)；遗留任务使用纯 task ID
        if "@" in arguments.task_id:
            return await self._send_swarm_message(arguments.task_id, arguments.message)
        try:
            await get_task_manager().write_to_task(arguments.task_id, arguments.message)
        except ValueError as exc:
            return ToolResult(output=str(exc), is_error=True)
        return ToolResult(output=f"Sent message to task {arguments.task_id}")

    async def _send_swarm_message(self, agent_id: str, message: str) -> ToolResult:
        """通过后端将消息路由到 swarm 代理。"""
        registry = get_backend_registry()
        # 优先使用 in_process 后端进行基于邮箱的传递
        try:
            executor = registry.get_executor("in_process")
        except KeyError:
            try:
                executor = registry.get_executor("subprocess")
            except KeyError:
                executor = registry.get_executor()

        teammate_msg = TeammateMessage(text=message, from_agent="coordinator")
        try:
            await executor.send_message(agent_id, teammate_msg)
        except ValueError as exc:
            return ToolResult(output=str(exc), is_error=True)
        except Exception as exc:
            logger.error("Failed to send message to %s: %s", agent_id, exc)
            return ToolResult(output=str(exc), is_error=True)
        return ToolResult(output=f"Sent message to agent {agent_id}")
