"""
Protocol 协议模块
==============

本模块定义 React 终端前后端通信的结构化协议模型。

主要功能：
    - 前端请求模型（FrontendRequest）
    - 后端事件模型（BackendEvent）
    - 转录项模型（TranscriptItem）
    - 任务快照模型（TaskSnapshot）

类说明：
    - FrontendRequest: 前端请求模型
    - BackendEvent: 后端事件模型
    - TranscriptItem: 转录项模型
    - TaskSnapshot: 任务快照模型

使用示例：
    >>> from illusion.ui.protocol import FrontendRequest, BackendEvent, TranscriptItem
    >>> 
    >>> # 创建前端请求
    >>> request = FrontendRequest(type="submit_line", line="帮我写一个程序")
    >>> 
    >>> # 创建后端事件
    >>> event = BackendEvent.ready(state, tasks, commands)
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from illusion.state.app_state import AppState
from illusion.bridge.manager import BridgeSessionRecord
from illusion.mcp.types import McpConnectionStatus
from illusion.tasks.types import TaskRecord


class FrontendRequest(BaseModel):
    """前端请求模型。

    表示从 React 前端发送到 Python 后端的请求。

    Attributes:
        type: 请求类型
        line: 提交的行内容
        command: 命令名称
        command: 命令值
        request_id: 请求 ID
        allowed: 是否允许
        always_allow: 是否总是允许
        tool_name: 工具名称
        answer: 用户答案
    """

    type: Literal[
        "submit_line",
        "stop",
        "permission_response",
        "question_response",
        "list_sessions",
        "select_command",
        "apply_select_command",
        "shutdown",
    ]
    line: str | None = None
    command: str | None = None
    value: str | None = None
    request_id: str | None = None
    allowed: bool | None = None
    always_allow: bool | None = None
    tool_name: str | None = None
    answer: str | None = None


class TranscriptItem(BaseModel):
    """转录项模型。

    表示前端呈现的一行转录内容。

    Attributes:
        role: 角色（system/user/assistant/tool/tool_result/log）
        text: 文本内容
        tool_name: 工具名称
        tool_input: 工具输入参数
        is_error: 是否为错误
    """

    role: Literal["system", "user", "assistant", "tool", "tool_result", "log"]
    text: str
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    is_error: bool | None = None


class TaskSnapshot(BaseModel):
    """任务快照模型。

    UI安全的任务表示形式。

    Attributes:
        id: 任务 ID
        type: 任务类型
        status: 任务状态
        description: 任务描述
        metadata: 元数据字典
    """

    id: str
    type: str
    status: str
    description: str
    metadata: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def from_record(cls, record: TaskRecord) -> "TaskSnapshot":
        """从任务记录创建任务快照。

        Args:
            record: 任务记录

        Returns:
            TaskSnapshot: 任务快照
        """
        return cls(
            id=record.id,
            type=record.type,
            status=record.status,
            description=record.description,
            metadata=dict(record.metadata),
        )


class BackendEvent(BaseModel):
    """后端事件模型。

    表示从 Python 后端发送到 React 前端的事件。

    Attributes:
        type: 事件类型
        select_options: 选择选项列表
        message: 消息文本
        item: 转录项
        state: 状态字典
        tasks: 任务快照列表
        mcp_servers: MCP 服务器状态列表
        bridge_sessions: 桥接会话列表
        commands: 命令列表
        modal: 模态对话框配置
        tool_name: 工具名称
        tool_input: 工具输入参数
        tool_output: 工具输出
        is_error: 是否为错误
        phase: 当前会话阶段
        tool_count: 工具链中的工具数量
        todo_items: 待办事项列表
        todo_markdown: 待办事项 Markdown
        plan_mode: 计划模式
        swarm_teammates: Swarm 队友列表
        swarm_notifications: Swarm 通知列表
    """

    type: Literal[
        "ready",
        "state_snapshot",
        "tasks_snapshot",
        "transcript_item",
        "assistant_delta",
        "assistant_complete",
        "line_complete",
        "tool_started",
        "tool_completed",
        "tool_chain_started",
        "tool_chain_completed",
        "clear_transcript",
        "modal_request",
        "select_request",
        "todo_update",
        "plan_mode_change",
        "swarm_status",
        "error",
        "shutdown",
    ]
    select_options: list[dict[str, Any]] | None = None
    message: str | None = None
    item: TranscriptItem | None = None
    state: dict[str, Any] | None = None
    tasks: list[TaskSnapshot] | None = None
    mcp_servers: list[dict[str, Any]] | None = None
    bridge_sessions: list[dict[str, Any]] | None = None
    commands: list[str] | None = None
    modal: dict[str, Any] | None = None
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    output: str | None = None
    is_error: bool | None = None
    phase: str | None = None          # 当前会话阶段
    tool_count: int | None = None     # 工具链中的工具数量
    # 新增字段用于增强事件
    todo_items: list[dict[str, Any]] | None = None
    todo_markdown: str | None = None
    plan_mode: str | None = None
    swarm_teammates: list[dict[str, Any]] | None = None
    swarm_notifications: list[dict[str, Any]] | None = None

    @classmethod
    def ready(
        cls,
        state: AppState,
        tasks: list[TaskRecord],
        commands: list[str],
    ) -> "BackendEvent":
        """创建就绪事件。

        Args:
            state: 应用状态
            tasks: 任务记录列表
            commands: 命令列表

        Returns:
            BackendEvent: 就绪事件
        """
        return cls(
            type="ready",
            state=_state_payload(state),
            tasks=[TaskSnapshot.from_record(task) for task in tasks],
            mcp_servers=[],
            bridge_sessions=[],
            commands=commands,
        )

    @classmethod
    def state_snapshot(cls, state: AppState) -> "BackendEvent":
        """创建状态快照事件。

        Args:
            state: 应用状态

        Returns:
            BackendEvent: 状态快照事件
        """
        return cls(type="state_snapshot", state=_state_payload(state))

    @classmethod
    def tasks_snapshot(cls, tasks: list[TaskRecord]) -> "BackendEvent":
        """创建任务快照事件。

        Args:
            tasks: 任务记录列表

        Returns:
            BackendEvent: 任务快照事件
        """
        return cls(
            type="tasks_snapshot",
            tasks=[TaskSnapshot.from_record(task) for task in tasks],
        )

    @classmethod
    def status_snapshot(
        cls,
        *,
        state: AppState,
        mcp_servers: list[McpConnectionStatus],
        bridge_sessions: list[BridgeSessionRecord],
    ) -> "BackendEvent":
        """创建状态快照事件（包含 MCP 和桥接信息）。

        Args:
            state: 应用状态
            mcp_servers: MCP 服务器状态列表
            bridge_sessions: 桥接会话列表

        Returns:
            BackendEvent: 状态快照事件
        """
        return cls(
            type="state_snapshot",
            state=_state_payload(state),
            mcp_servers=[
                {
                    "name": server.name,
                    "state": server.state,
                    "detail": server.detail,
                    "transport": server.transport,
                    "auth_configured": server.auth_configured,
                    "tool_count": len(server.tools),
                    "resource_count": len(server.resources),
                }
                for server in mcp_servers
            ],
            bridge_sessions=[
                {
                    "session_id": session.session_id,
                    "command": session.command,
                    "cwd": session.cwd,
                    "pid": session.pid,
                    "status": session.status,
                    "started_at": session.started_at,
                    "output_path": session.output_path,
                }
                for session in bridge_sessions
            ],
        )


def _state_payload(state: AppState) -> dict[str, Any]:
    """将应用状态转换为载荷字典。

    Args:
        state: 应用状态

    Returns:
        dict[str, Any]: 状态载荷
    """
    return {
        "model": state.model,
        "cwd": state.cwd,
        "provider": state.provider,
        "auth_status": state.auth_status,
        "base_url": state.base_url,
        "permission_mode": _format_permission_mode(state.permission_mode),
        "theme": state.theme,
        "ui_language": state.ui_language,
        "fast_mode": state.fast_mode,
        "effort": state.effort,
        "passes": state.passes,
        "mcp_connected": state.mcp_connected,
        "mcp_failed": state.mcp_failed,
        "bridge_sessions": state.bridge_sessions,
        "output_style": state.output_style,
        "phase": state.phase,
    }


# 权限模式标签映射
_MODE_LABELS = {
    "default": "Default",
    "plan": "Plan Mode",
    "full_auto": "Auto",
    "PermissionMode.DEFAULT": "Default",
    "PermissionMode.PLAN": "Plan Mode",
    "PermissionMode.FULL_AUTO": "Auto",
}


def _format_permission_mode(raw: str) -> str:
    """将原始权限模式转换为人类可读的标签。

    Args:
        raw: 原始权限模式字符串

    Returns:
        str: 格式化的权限模式标签
    """
    return _MODE_LABELS.get(raw, raw)


__all__ = [
    "BackendEvent",
    "FrontendRequest",
    "TaskSnapshot",
    "TranscriptItem",
]