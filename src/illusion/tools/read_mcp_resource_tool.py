"""
MCP 资源读取工具
================

本模块提供读取 MCP 资源的功能。

主要组件：
    - ReadMcpResourceTool: 从 MCP 服务器读取资源

使用示例：
    >>> from illusion.tools import ReadMcpResourceTool
    >>> tool = ReadMcpResourceTool(manager)
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from illusion.mcp.client import McpClientManager
from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class ReadMcpResourceToolInput(BaseModel):
    """MCP 资源读取参数。

    属性：
        server: MCP 服务器名称
        uri: 资源 URI
    """

    server: str = Field(description="MCP server name")
    uri: str = Field(description="Resource URI")


class ReadMcpResourceTool(BaseTool):
    """从 MCP 服务器读取一个资源。

    用于访问 MCP 服务器提供的资源内容。
    """

    name = "read_mcp_resource"
    description = """Reads a specific resource from an MCP server, identified by server name and resource URI.

Parameters:
- server (required): The name of the MCP server from which to read the resource
- uri (required): The URI of the resource to read"""
    input_model = ReadMcpResourceToolInput

    def __init__(self, manager: McpClientManager) -> None:
        self._manager = manager

    def is_read_only(self, arguments: ReadMcpResourceToolInput) -> bool:
        del arguments
        return True

    async def execute(self, arguments: ReadMcpResourceToolInput, context: ToolExecutionContext) -> ToolResult:
        del context
        # 读取资源
        output = await self._manager.read_resource(arguments.server, arguments.uri)
        return ToolResult(output=output)
