"""
钩子配置模式定义
================

本模块定义钩子的配置数据模型，使用 Pydantic 进行验证。

支持的钩子类型：
    - CommandHookDefinition: 执行 Shell 命令的钩子
    - PromptHookDefinition: 使用模型验证条件的钩子
    - HttpHookDefinition: 发送 HTTP 请求的钩子
    - AgentHookDefinition: 使用 Agent 进行深度验证的钩子

使用示例：
    >>> from illusion.hooks.schemas import CommandHookDefinition
    >>> hook = CommandHookDefinition(type="command", command="echo hello")
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CommandHookDefinition(BaseModel):
    """
    命令钩子定义
    
    执行 Shell 命令的钩子类型。
    
    Attributes:
        type: 钩子类型，固定为 "command"
        command: 要执行的 shell 命令
        timeout_seconds: 超时时间（秒），默认30秒，范围1-600
        matcher: 可选的匹配器，用于过滤 payload
        block_on_failure: 失败时是否阻止后续操作，默认 False
    """

    type: Literal["command"] = "command"  # 钩子类型标识
    command: str  # 要执行的命令
    timeout_seconds: int = Field(default=30, ge=1, le=600)  # 超时时间（秒）
    matcher: str | None = None  # payload 匹配器
    block_on_failure: bool = False  # 失败时是否阻塞


class PromptHookDefinition(BaseModel):
    """
    提示词钩子定义
    
    使用大语言模型验证条件的钩子类型。
    
    Attributes:
        type: 钩子类型，固定为 "prompt"
        prompt: 验证提示词
        model: 可选的模型名称，默认使用上下文中的模型
        timeout_seconds: 超时时间（秒），默认30秒，范围1-600
        matcher: 可选的匹配器，用于过滤 payload
        block_on_failure: 失败时是否阻止后续操作，默认 True
    """

    type: Literal["prompt"] = "prompt"  # 钩子类型标识
    prompt: str  # 验证提示词
    model: str | None = None  # 可选的模型名称
    timeout_seconds: int = Field(default=30, ge=1, le=600)  # 超时时间（秒）
    matcher: str | None = None  # payload 匹配器
    block_on_failure: bool = True  # 失败时是否阻塞


class HttpHookDefinition(BaseModel):
    """
    HTTP 钩子定义
    
    向 HTTP 端点发送事件载荷的钩子类型。
    
    Attributes:
        type: 钩子类型，固定为 "http"
        url: 请求目标 URL
        headers: 可选的请求头字典
        timeout_seconds: 超时时间（秒），默认30秒，范围1-600
        matcher: 可选的匹配器，用于过滤 payload
        block_on_failure: 失败时是否阻止后续操作，默认 False
    """

    type: Literal["http"] = "http"  # 钩子类型标识
    url: str  # 请求 URL
    headers: dict[str, str] = Field(default_factory=dict)  # 请求头
    timeout_seconds: int = Field(default=30, ge=1, le=600)  # 超时时间（秒）
    matcher: str | None = None  # payload 匹配器
    block_on_failure: bool = False  # 失败时是否阻塞


class AgentHookDefinition(BaseModel):
    """
    Agent 钩子定义
    
    使用 Agent 进行深度模型验证的钩子类型。
    
    Attributes:
        type: 钩子类型，固定为 "agent"
        prompt: 验证提示词
        model: 可选的模型名称，默认使用上下文中的模型
        timeout_seconds: 超时时间（秒），默认60秒，范围1-1200
        matcher: 可选的匹配器，用于过滤 payload
        block_on_failure: 失败时是否阻止后续操作，默认 True
    """

    type: Literal["agent"] = "agent"  # 钩子类型标识
    prompt: str  # 验证提示词
    model: str | None = None  # 可选的模型名称
    timeout_seconds: int = Field(default=60, ge=1, le=1200)  # 超时时间（秒）
    matcher: str | None = None  # payload 匹配器
    block_on_failure: bool = True  # 失败时是否阻塞


# 联合类型：所有钩子定义的联合
HookDefinition = (
    CommandHookDefinition
    | PromptHookDefinition
    | HttpHookDefinition
    | AgentHookDefinition
)