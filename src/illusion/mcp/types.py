"""
MCP 配置和状态模型
==================

本模块定义 MCP（Model Context Protocol）相关的配置和数据类型。

主要功能：
    - 定义 MCP 服务器配置（STDIO、HTTP、WebSocket）
    - 定义 MCP 工具和资源信息
    - 定义 MCP 连接状态

类说明：
    - McpStdioServerConfig: STDIO 类型 MCP 服务器配置
    - McpHttpServerConfig: HTTP 类型 MCP 服务器配置
    - McpWebSocketServerConfig: WebSocket 类型 MCP 服务器配置
    - McpServerConfig: MCP 服务器配置联合类型
    - McpJsonConfig: 配置文件格式（用于插件和项目文件）
    - McpToolInfo: MCP 工具元数据
    - McpResourceInfo: MCP 资源元数据
    - McpConnectionStatus: MCP 服务器运行时状态

使用示例：
    >>> from illusion.mcp.types import McpStdioServerConfig
    >>> config = McpStdioServerConfig(command="node", args=["server.js"])
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field


class McpStdioServerConfig(BaseModel):
    """
    STDIO 类型 MCP 服务器配置
    
    通过标准输入输出流与 MCP 服务器通信的配置。
    
    Attributes:
        type: 服务器类型，固定为 "stdio"
        command: 要执行的命令
        args: 命令参数列表
        env: 环境变量字典
        cwd: 工作目录
    """

    type: Literal["stdio"] = "stdio"
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] | None = None
    cwd: str | None = None


class McpHttpServerConfig(BaseModel):
    """
    HTTP 类型 MCP 服务器配置
    
    通过 HTTP 协议与 MCP 服务器通信的配置。
    
    Attributes:
        type: 服务器类型，固定为 "http"
        url: 服务器 URL 地址
        headers: HTTP 请求头字典
    """

    type: Literal["http"] = "http"
    url: str
    headers: dict[str, str] = Field(default_factory=dict)


class McpWebSocketServerConfig(BaseModel):
    """
    WebSocket 类型 MCP 服务器配置
    
    通过 WebSocket 协议与 MCP 服务器通信的配置。
    
    Attributes:
        type: 服务器类型，固定为 "ws"
        url: 服务器 WebSocket URL 地址
        headers: WebSocket 连接请求头字典
    """

    type: Literal["ws"] = "ws"
    url: str
    headers: dict[str, str] = Field(default_factory=dict)


# MCP 服务器配置联合类型，支持 STDIO、HTTP、WebSocket 三种传输方式
McpServerConfig = McpStdioServerConfig | McpHttpServerConfig | McpWebSocketServerConfig


class McpJsonConfig(BaseModel):
    """
    MCP 配置文件格式
    
    用于插件和项目文件中的 MCP 服务器配置格式。
    
    Attributes:
        mcp_servers: MCP 服务器名称到配置的映射字典
    """

    mcpServers: dict[str, McpServerConfig] = Field(default_factory=dict)


@dataclass(frozen=True)
class McpToolInfo:
    """
    MCP 工具信息
    
    MCP 服务器暴露的工具元数据，包含工具名称、描述和输入模式。
    
    Attributes:
        server_name: 所属服务器名称
        name: 工具名称
        description: 工具描述
        input_schema: 工具输入参数的 JSON Schema 定义
    """

    server_name: str
    name: str
    description: str
    input_schema: dict[str, object]


@dataclass(frozen=True)
class McpResourceInfo:
    """
    MCP 资源信息
    
    MCP 服务器暴露的资源元数据，包含资源名称、URI 和描述。
    
    Attributes:
        server_name: 所属服务器名称
        name: 资源名称
        uri: 资源统一标识符
        description: 资源描述
    """

    server_name: str
    name: str
    uri: str
    description: str = ""


@dataclass
class McpConnectionStatus:
    """
    MCP 连接状态
    
    MCP 服务器的运行时状态信息，包含连接状态、传输类型、认证配置、工具和资源列表。
    
    Attributes:
        name: 服务器名称
        state: 连接状态（connected/failed/pending/disabled）
        detail: 状态详情或错误信息
        transport: 传输类型（stdio/http/ws）
        auth_configured: 是否配置了认证
        tools: 该服务器提供的工具列表
        resources: 该服务器提供的资源列表
    """

    name: str
    state: Literal["connected", "failed", "pending", "disabled"]
    detail: str = ""
    transport: str = "unknown"
    auth_configured: bool = False
    tools: list[McpToolInfo] = field(default_factory=list)
    resources: list[McpResourceInfo] = field(default_factory=list)
