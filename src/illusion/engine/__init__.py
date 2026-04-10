"""
核心引擎模块
============

本模块提供 IllusionCode 核心引擎的导出接口。

主要组件：
    - ConversationMessage: 对话消息模型
    - TextBlock: 文本内容块
    - ToolUseBlock: 工具调用块
    - ToolResultBlock: 工具结果块
    - QueryEngine: 查询引擎
    - AssistantTextDelta: 助手文本增量事件
    - AssistantTurnComplete: 助手轮次完成事件
    - ToolExecutionStarted: 工具执行开始事件
    - ToolExecutionCompleted: 工具执行完成事件

使用示例：
    >>> from illusion.engine import ConversationMessage, QueryEngine
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # 类型检查时导入，避免循环依赖
    from illusion.engine.messages import (
        ConversationMessage,
        TextBlock,
        ToolResultBlock,
        ToolUseBlock,
    )
    from illusion.engine.query_engine import QueryEngine
    from illusion.engine.stream_events import (
        AssistantTextDelta,
        AssistantTurnComplete,
        ToolExecutionCompleted,
        ToolExecutionStarted,
    )

__all__ = [
    "AssistantTextDelta",
    "AssistantTurnComplete",
    "ConversationMessage",
    "QueryEngine",
    "TextBlock",
    "ToolExecutionCompleted",
    "ToolExecutionStarted",
    "ToolResultBlock",
    "ToolUseBlock",
]


def __getattr__(name: str):
    if name in {"ConversationMessage", "TextBlock", "ToolResultBlock", "ToolUseBlock"}:
        from illusion.engine.messages import (
            ConversationMessage,
            TextBlock,
            ToolResultBlock,
            ToolUseBlock,
        )

        return {
            "ConversationMessage": ConversationMessage,
            "TextBlock": TextBlock,
            "ToolResultBlock": ToolResultBlock,
            "ToolUseBlock": ToolUseBlock,
        }[name]

    if name == "QueryEngine":
        from illusion.engine.query_engine import QueryEngine

        return QueryEngine

    if name in {
        "AssistantTextDelta",
        "AssistantTurnComplete",
        "ToolExecutionCompleted",
        "ToolExecutionStarted",
    }:
        from illusion.engine.stream_events import (
            AssistantTextDelta,
            AssistantTurnComplete,
            ToolExecutionCompleted,
            ToolExecutionStarted,
        )

        return {
            "AssistantTextDelta": AssistantTextDelta,
            "AssistantTurnComplete": AssistantTurnComplete,
            "ToolExecutionCompleted": ToolExecutionCompleted,
            "ToolExecutionStarted": ToolExecutionStarted,
        }[name]

    raise AttributeError(name)
