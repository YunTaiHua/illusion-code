"""查询引擎产生的事件。

本模块定义查询引擎在执行过程中产生的各种事件类型。

主要事件类：
    - AssistantTextDelta: 助手文本增量
    - AssistantTurnComplete: 助手轮次完成
    - ToolExecutionStarted: 工具执行开始
    - ToolExecutionCompleted: 工具执行完成
    - ToolChainStarted: 工具链开始
    - ToolChainCompleted: 工具链完成
    - ErrorEvent: 错误事件
    - StatusEvent: 状态事件

使用示例：
    >>> from illusion.engine.stream_events import StreamEvent, AssistantTextDelta
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from illusion.api.usage import UsageSnapshot
from illusion.engine.messages import ConversationMessage


class SessionPhase(Enum):
    """智能体会话阶段。

    Attributes:
        IDLE: 空闲状态
        THINKING: 思考中
        TOOL_EXECUTING: 工具执行中
    """

    IDLE = "idle"
    THINKING = "thinking"
    TOOL_EXECUTING = "tool_executing"


@dataclass(frozen=True)
class AssistantTextDelta:
    """增量助手文本。

    在流式响应过程中逐步产生的文本片段。

    Attributes:
        text: 新增的文本内容
    """

    text: str


@dataclass(frozen=True)
class AssistantTurnComplete:
    """助手轮次完成。

    当助手完成一个完整的响应轮次时产生，包含最终消息和使用量统计。

    Attributes:
        message: 助手生成的消息
        usage: 本轮使用的令牌统计
    """

    message: ConversationMessage
    usage: UsageSnapshot


@dataclass(frozen=True)
class ToolExecutionStarted:
    """引擎即将执行工具。

    在工具执行开始时产生，包含工具名称和输入参数。

    Attributes:
        tool_name: 工具名称
        tool_input: 工具输入参数字典
    """

    tool_name: str
    tool_input: dict[str, Any]


@dataclass(frozen=True)
class ToolExecutionCompleted:
    """工具执行完成。

    工具执行完成后产生，包含工具名称、输出结果和是否出错。

    Attributes:
        tool_name: 工具名称
        output: 工具执行输出
        is_error: 是否为错误结果
    """

    tool_name: str
    output: str
    is_error: bool = False


@dataclass(frozen=True)
class ErrorEvent:
    """应向用户显示的错误。

    包含错误信息和是否可恢复。

    Attributes:
        message: 错误消息
        recoverable: 是否可恢复（默认True）
    """

    message: str
    recoverable: bool = True


@dataclass(frozen=True)
class StatusEvent:
    """向用户显示的瞬态系统状态消息。

    Attributes:
        message: 状态消息内容
    """

    message: str


@dataclass(frozen=True)
class ToolChainStarted:
    """一批工具执行即将开始。

    Attributes:
        tool_count: 即将执行的工具数量
    """

    tool_count: int


@dataclass(frozen=True)
class ToolChainCompleted:
    """批处理中的所有工具已完成执行。

    Attributes:
        results_summary: 工具执行结果摘要列表
    """

    results_summary: list[dict[str, Any]]


# 事件联合类型：所有可能的流事件类型
StreamEvent = (
    AssistantTextDelta
    | AssistantTurnComplete
    | ToolExecutionStarted
    | ToolExecutionCompleted
    | ErrorEvent
    | StatusEvent
    | ToolChainStarted
    | ToolChainCompleted
)
