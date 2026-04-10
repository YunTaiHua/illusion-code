"""
MCP 认证配置工具
================

本模块提供更新 MCP 认证配置的功能。

主要组件：
    - McpAuthTool: 配置 MCP 服务器认证的工具

使用示例：
    >>> from illusion.tools import McpAuthTool
    >>> tool = McpAuthTool()
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from illusion.config.settings import load_settings, save_settings
from illusion.mcp.types import McpHttpServerConfig, McpStdioServerConfig, McpWebSocketServerConfig
from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class McpAuthToolInput(BaseModel):
    """MCP 认证更新参数。

    属性：
        server_name: 配置的 MCP 服务器名称
        mode: 认证模式：bearer、header 或 env
        value: 要保存的密钥值
        key: 可选的 header 或 env 键覆盖
    """

    server_name: str = Field(description="Configured MCP server name")
    mode: str = Field(description="Auth mode: bearer, header, or env")
    value: str = Field(description="Secret value to persist")
    key: str | None = Field(default=None, description="Header or env key override")


class McpAuthTool(BaseTool):
    """为服务器持久化 MCP 认证设置。

    用于配置 MCP 服务器的认证信息。
    """

    name = "mcp_auth"
    description = "Configure auth for an MCP server and reconnect active sessions when possible."
    input_model = McpAuthToolInput

    async def execute(self, arguments: McpAuthToolInput, context: ToolExecutionContext) -> ToolResult:
        # 加载设置
        settings = load_settings()
        mcp_manager = context.metadata.get("mcp_manager")
        # 尝试从设置或 mcp_manager 获取服务器配置
        config = settings.mcp_servers.get(arguments.server_name)
        if config is None and mcp_manager is not None:
            getter = getattr(mcp_manager, "get_server_config", None)
            if callable(getter):
                config = getter(arguments.server_name)
        if config is None:
            return ToolResult(output=f"Unknown MCP server: {arguments.server_name}", is_error=True)

        # 根据服务器类型处理认证
        if isinstance(config, McpStdioServerConfig):
            # stdio 服务器支持 env 或 bearer 模式
            if arguments.mode not in {"env", "bearer"}:
                return ToolResult(output="stdio MCP auth supports env or bearer modes", is_error=True)
            env_key = arguments.key or "MCP_AUTH_TOKEN"
            env = dict(config.env or {})
            env[env_key] = f"Bearer {arguments.value}" if arguments.mode == "bearer" else arguments.value
            updated = config.model_copy(update={"env": env})
        elif isinstance(config, (McpHttpServerConfig, McpWebSocketServerConfig)):
            # http/ws 服务器支持 header 或 bearer 模式
            if arguments.mode not in {"header", "bearer"}:
                return ToolResult(output="http/ws MCP auth supports header or bearer modes", is_error=True)
            header_key = arguments.key or "Authorization"
            headers = dict(config.headers)
            headers[header_key] = (
                f"Bearer {arguments.value}" if arguments.mode == "bearer" and header_key == "Authorization" else arguments.value
            )
            updated = config.model_copy(update={"headers": headers})
        else:
            return ToolResult(output="Unsupported MCP server config type", is_error=True)

        # 保存设置
        settings.mcp_servers[arguments.server_name] = updated
        save_settings(settings)

        # 尝试重新连接
        if mcp_manager is not None:
            try:
                mcp_manager.update_server_config(arguments.server_name, updated)
                await mcp_manager.reconnect_all()
            except Exception as exc:  # 防御性处理
                return ToolResult(
                    output=f"Saved MCP auth for {arguments.server_name}, but reconnect failed: {exc}",
                    is_error=True,
                )

        return ToolResult(output=f"Saved MCP auth for {arguments.server_name}")
