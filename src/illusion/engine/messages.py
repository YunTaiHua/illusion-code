"""
对话消息模型模块
================

本模块提供查询引擎使用的对话消息模型。

主要类：
    - TextBlock: 纯文本内容块
    - ToolUseBlock: 模型执行命名工具的请求
    - ToolResultBlock: 发送回模型的工具结果内容
    - ConversationMessage: 单个助手或用户消息

使用示例：
    >>> from illusion.engine.messages import ConversationMessage, TextBlock
    >>> msg = ConversationMessage.from_user_text("Hello")
"""

from __future__ import annotations

from typing import Any, Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class TextBlock(BaseModel):
    """纯文本内容块
    
    Attributes:
        type: 块类型（固定为 "text"）
        text: 文本内容
    """

    type: Literal["text"] = "text"
    text: str


class ToolUseBlock(BaseModel):
    """模型执行命名工具的请求
    
    Attributes:
        type: 块类型（固定为 "tool_use"）
        id: 工具调用唯一标识
        name: 工具名称
        input: 工具输入参数
    """

    type: Literal["tool_use"] = "tool_use"
    id: str = Field(default_factory=lambda: f"toolu_{uuid4().hex}")
    name: str
    input: dict[str, Any] = Field(default_factory=dict)


class ToolResultBlock(BaseModel):
    """发送回模型的工具结果内容
    
    Attributes:
        type: 块类型（固定为 "tool_result"）
        tool_use_id: 对应的工具调用 ID
        content: 工具返回的内容
        is_error: 是否为错误结果
    """

    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: str
    is_error: bool = False


# 内容块联合类型
ContentBlock = Annotated[TextBlock | ToolUseBlock | ToolResultBlock, Field(discriminator="type")]


class ConversationMessage(BaseModel):
    """单个助手或用户消息
    
    Attributes:
        role: 消息角色（"user" 或 "assistant"）
        content: 内容块列表
    """

    role: Literal["user", "assistant"]
    content: list[ContentBlock] = Field(default_factory=list)

    @classmethod
    def from_user_text(cls, text: str) -> "ConversationMessage":
        """从原始文本构造用户消息
        
        Args:
            text: 用户输入文本
        
        Returns:
            ConversationMessage: 用户消息
        """
        return cls(role="user", content=[TextBlock(text=text)])

    @property
    def text(self) -> str:
        """返回连接的文本块
        
        Returns:
            str: 所有文本块的连接字符串
        """
        return "".join(
            block.text for block in self.content if isinstance(block, TextBlock)
        )

    @property
    def tool_uses(self) -> list[ToolUseBlock]:
        """返回消息中包含的所有工具调用
        
        Returns:
            list[ToolUseBlock]: 工具调用列表
        """
        return [block for block in self.content if isinstance(block, ToolUseBlock)]

    def to_api_param(self) -> dict[str, Any]:
        """将消息转换为 Anthropic SDK 消息参数
        
        Returns:
            dict[str, Any]: API 参数格式的字典
        """
        return {
            "role": self.role,
            "content": [serialize_content_block(block) for block in self.content],
        }


def serialize_content_block(block: ContentBlock) -> dict[str, Any]:
    """将本地内容块转换为提供商线格式
    
    Args:
        block: 内容块
    
    Returns:
        dict[str, Any]: 线格式字典
    """
    if isinstance(block, TextBlock):
        return {"type": "text", "text": block.text}

    if isinstance(block, ToolUseBlock):
        return {
            "type": "tool_use",
            "id": block.id,
            "name": block.name,
            "input": block.input,
        }

    return {
        "type": "tool_result",
        "tool_use_id": block.tool_use_id,
        "content": block.content,
        "is_error": block.is_error,
    }


def assistant_message_from_api(raw_message: Any) -> ConversationMessage:
    """将 Anthropic SDK 消息对象转换为对话消息
    
    Args:
        raw_message: Anthropic SDK 原始消息
    
    Returns:
        ConversationMessage: 转换后的对话消息
    """
    content: list[ContentBlock] = []

    for raw_block in getattr(raw_message, "content", []):
        block_type = getattr(raw_block, "type", None)
        if block_type == "text":
            content.append(TextBlock(text=getattr(raw_block, "text", "")))
        elif block_type == "tool_use":
            content.append(
                ToolUseBlock(
                    id=getattr(raw_block, "id", f"toolu_{uuid4().hex}"),
                    name=getattr(raw_block, "name", ""),
                    input=dict(getattr(raw_block, "input", {}) or {}),
                )
            )

    return ConversationMessage(role="assistant", content=content)
