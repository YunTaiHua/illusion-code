"""
MCP 模块
========

本模块提供 MCP（Model Context Protocol）客户端和管理功能。

主要组件：
    - McpClientManager: MCP 客户端管理器
    - McpServerConfig: MCP 服务器配置
    - McpStdioServerConfig: STDIO 服务器配置
    - McpHttpServerConfig: HTTP 服务器配置
    - McpWebSocketServerConfig: WebSocket 服务器配置
    - McpToolInfo: MCP 工具信息
    - McpResourceInfo: MCP 资源信息
    - McpConnectionStatus: MCP 连接状态
    - load_mcp_server_configs: 加载 MCP 服务器配置

使用示例：
    >>> from illusion.mcp import McpClientManager, load_mcp_server_configs
"""

from __future__ import annotations

from typing import TYPE_CHECKING

# 类型检查时导入，避免循环依赖
if TYPE_CHECKING:  # pragma: no cover
    from illusion.mcp.client import McpClientManager
    from illusion.mcp.types import (
        McpConnectionStatus,
        McpHttpServerConfig,
        McpJsonConfig,
        McpResourceInfo,
        McpServerConfig,
        McpStdioServerConfig,
        McpToolInfo,
        McpWebSocketServerConfig,
    )

__all__ = [
    "McpClientManager",
    "McpConnectionStatus",
    "McpHttpServerConfig",
    "McpJsonConfig",
    "McpResourceInfo",
    "McpServerConfig",
    "McpStdioServerConfig",
    "McpToolInfo",
    "McpWebSocketServerConfig",
    "load_mcp_server_configs",
]


def __getattr__(name: str):
    # 延迟导入 McpClientManager，避免不必要的导入开销
    if name == "McpClientManager":
        from illusion.mcp.client import McpClientManager

        return McpClientManager
    # 延迟导入 load_mcp_server_configs
    if name == "load_mcp_server_configs":
        from illusion.mcp.config import load_mcp_server_configs

        return load_mcp_server_configs
    # 延迟导入类型定义
    if name in {
        "McpConnectionStatus",
        "McpHttpServerConfig",
        "McpJsonConfig",
        "McpResourceInfo",
        "McpServerConfig",
        "McpStdioServerConfig",
        "McpToolInfo",
        "McpWebSocketServerConfig",
    }:
        from illusion.mcp.types import (
            McpConnectionStatus,
            McpHttpServerConfig,
            McpJsonConfig,
            McpResourceInfo,
            McpServerConfig,
            McpStdioServerConfig,
            McpToolInfo,
            McpWebSocketServerConfig,
        )

        return {
            "McpConnectionStatus": McpConnectionStatus,
            "McpHttpServerConfig": McpHttpServerConfig,
            "McpJsonConfig": McpJsonConfig,
            "McpResourceInfo": McpResourceInfo,
            "McpServerConfig": McpServerConfig,
            "McpStdioServerConfig": McpStdioServerConfig,
            "McpToolInfo": McpToolInfo,
            "McpWebSocketServerConfig": McpWebSocketServerConfig,
        }[name]
    raise AttributeError(name)
