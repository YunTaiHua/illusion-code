"""
MCP 客户端管理器模块
===================

本模块提供 MCP（Model Context Protocol）客户端管理功能。

主要功能：
    - 管理 MCP 服务器连接
    - 暴露 MCP 工具和资源
    - 支持 STDIO 传输类型连接
    - 提供工具调用和资源读取接口

类说明：
    - McpClientManager: MCP 客户端管理器类

使用示例：
    >>> from illusion.mcp.client import McpClientManager
    >>> from illusion.mcp.types import McpStdioServerConfig
    >>> 
    >>> configs = {"my_server": McpStdioServerConfig(command="node", args=["server.js"])}
    >>> manager = McpClientManager(configs)
    >>> await manager.connect_all()
"""

from __future__ import annotations

from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, ReadResourceResult

from illusion.mcp.types import (
    McpConnectionStatus,
    McpResourceInfo,
    McpStdioServerConfig,
    McpToolInfo,
)


class McpClientManager:
    """
    MCP 客户端管理器
    
    管理与 MCP 服务器的连接，并暴露服务器提供的工具和资源。
    支持 STDIO 传输类型的服务器连接。
    
    Attributes:
        _server_configs: 服务器名称到配置的映射
        _statuses: 服务器名称到连接状态的映射
        _sessions: 服务器名称到客户端会话的映射
        _stacks: 服务器名称到异步退出栈的映射
    
    使用示例：
        >>> manager = McpClientManager(configs)
        >>> await manager.connect_all()
        >>> tools = manager.list_tools()
    """

    def __init__(self, server_configs: dict[str, object]) -> None:
        """
        初始化 MCP 客户端管理器
        
        Args:
            server_configs: 服务器名称到配置的映射字典
        """
        self._server_configs = server_configs
        # 初始化所有服务器状态为 pending（待连接）
        self._statuses: dict[str, McpConnectionStatus] = {
            name: McpConnectionStatus(
                name=name,
                state="pending",
                transport=getattr(config, "type", "unknown"),
            )
            for name, config in server_configs.items()
        }
        self._sessions: dict[str, ClientSession] = {}  # 存储活跃的客户端会话
        self._stacks: dict[str, AsyncExitStack] = {}   # 存储异步上下文管理器栈

    async def connect_all(self) -> None:
        """
        连接所有已配置的 STDIO 类型 MCP 服务器
        
        遍历所有服务器配置，对于 STDIO 类型的服务器建立连接，
        其他类型的服务器标记为失败（当前版本仅支持 STDIO）。
        """
        for name, config in self._server_configs.items():
            # 仅支持 STDIO 类型的服务器连接
            if isinstance(config, McpStdioServerConfig):
                await self._connect_stdio(name, config)
            else:
                # 其他传输类型标记为失败
                self._statuses[name] = McpConnectionStatus(
                    name=name,
                    state="failed",
                    transport=config.type,
                    auth_configured=bool(getattr(config, "headers", None)),
                    detail=f"Unsupported MCP transport in current build: {config.type}",
                )

    async def reconnect_all(self) -> None:
        """
        重新连接所有已配置的服务器
        
        先关闭所有现有连接，然后重置状态并重新建立连接。
        """
        await self.close()
        # 重置所有服务器状态为 pending
        self._statuses = {
            name: McpConnectionStatus(name=name, state="pending", transport=getattr(config, "type", "unknown"))
            for name, config in self._server_configs.items()
        }
        await self.connect_all()

    def update_server_config(self, name: str, config: object) -> None:
        """
        替换内存中的服务器配置
        
        Args:
            name: 服务器名称
            config: 新的服务器配置对象
        """
        self._server_configs[name] = config

    def get_server_config(self, name: str) -> object | None:
        """
        获取指定的服务器配置
        
        Args:
            name: 服务器名称
        
        Returns:
            服务器配置对象，如果不存在则返回 None
        """
        return self._server_configs.get(name)

    async def close(self) -> None:
        """
        关闭所有活跃的 MCP 会话
        
        释放所有资源，包括关闭流和清理会话。
        """
        # 关闭所有异步上下文栈
        for stack in list(self._stacks.values()):
            await stack.aclose()
        self._stacks.clear()
        self._sessions.clear()

    def list_statuses(self) -> list[McpConnectionStatus]:
        """
        获取所有已配置服务器的状态列表
        
        Returns:
            按服务器名称排序的连接状态列表
        """
        return [self._statuses[name] for name in sorted(self._statuses)]

    def list_tools(self) -> list[McpToolInfo]:
        """
        获取所有已连接 MCP 服务器提供的工具列表
        
        Returns:
            合并后的工具信息列表
        """
        tools: list[McpToolInfo] = []
        for status in self.list_statuses():
            tools.extend(status.tools)
        return tools

    def list_resources(self) -> list[McpResourceInfo]:
        """
        获取所有已连接 MCP 服务器提供的资源列表
        
        Returns:
            合并后的资源信息列表
        """
        resources: list[McpResourceInfo] = []
        for status in self.list_statuses():
            resources.extend(status.resources)
        return resources

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict[str, Any]) -> str:
        """
        调用指定的 MCP 工具
        
        在指定服务器上调用工具并返回字符串形式的结果。
        
        Args:
            server_name: 服务器名称
            tool_name: 工具名称
            arguments: 工具参数字典
        
        Returns:
            工具执行结果的字符串形式
        """
        session = self._sessions[server_name]
        result: CallToolResult = await session.call_tool(tool_name, arguments)
        parts: list[str] = []
        # 处理返回的内容，支持文本和其他类型
        for item in result.content:
            if getattr(item, "type", None) == "text":
                parts.append(getattr(item, "text", ""))
            else:
                parts.append(item.model_dump_json())
        # 如果有结构化内容但没有文本 parts，添加结构化内容
        if result.structuredContent and not parts:
            parts.append(str(result.structuredContent))
        # 如果没有输出，返回默认消息
        if not parts:
            parts.append("(no output)")
        return "\n".join(parts).strip()

    async def read_resource(self, server_name: str, uri: str) -> str:
        """
        读取指定的 MCP 资源
        
        从指定服务器读取资源并返回字符串形式的内容。
        
        Args:
            server_name: 服务器名称
            uri: 资源统一标识符
        
        Returns:
            资源内容的字符串形式
        """
        session = self._sessions[server_name]
        result: ReadResourceResult = await session.read_resource(uri)
        parts: list[str] = []
        for item in result.contents:
            text = getattr(item, "text", None)
            if text is not None:
                parts.append(text)
            else:
                parts.append(str(getattr(item, "blob", "")))
        return "\n".join(parts).strip()

    async def _connect_stdio(self, name: str, config: McpStdioServerConfig) -> None:
        """
        连接 STDIO 类型的 MCP 服务器
        
        建立与 STDIO 服务器的连接，初始化会话，并获取服务器提供的工具和资源列表。
        
        Args:
            name: 服务器名称
            config: STDIO 服务器配置
        """
        stack = AsyncExitStack()
        try:
            # 创建 STDIO 客户端连接
            read_stream, write_stream = await stack.enter_async_context(
                stdio_client(
                    StdioServerParameters(
                        command=config.command,
                        args=config.args,
                        env=config.env,
                        cwd=config.cwd,
                    )
                )
            )
            # 创建客户端会话
            session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
            await session.initialize()
            # 获取服务器提供的工具列表
            tool_result = await session.list_tools()
            # 转换工具信息为内部数据模型
            tools = [
                McpToolInfo(
                    server_name=name,
                    name=tool.name,
                    description=tool.description or "",
                    input_schema=dict(tool.inputSchema or {"type": "object", "properties": {}}),
                )
                for tool in tool_result.tools
            ]
            # 获取服务器提供的资源列表（可选能力，服务器可能不支持）
            resources: list[McpResourceInfo] = []
            try:
                resource_result = await session.list_resources()
                resources = [
                    McpResourceInfo(
                        server_name=name,
                        name=resource.name or str(resource.uri),
                        uri=str(resource.uri),
                        description=resource.description or "",
                    )
                    for resource in resource_result.resources
                ]
            except Exception:
                # 服务器不支持 resources 能力，忽略错误
                pass
            # 保存会话和栈
            self._sessions[name] = session
            self._stacks[name] = stack
            # 更新连接状态为已连接
            self._statuses[name] = McpConnectionStatus(
                name=name,
                state="connected",
                transport=config.type,
                auth_configured=bool(config.env),
                tools=tools,
                resources=resources,
            )
        except Exception as exc:
            # 连接失败，清理资源并更新状态
            await stack.aclose()
            self._statuses[name] = McpConnectionStatus(
                name=name,
                state="failed",
                transport=config.type,
                auth_configured=bool(config.env),
                detail=str(exc),
            )
