"""
MCP 资源列表工具
================

本模块提供列出 MCP 资源的功能。

主要组件：
    - ListMcpResourcesTool: 列出 MCP 服务器上的资源

使用示例：
    >>> from illusion.tools import ListMcpResourcesTool
    >>> tool = ListMcpResourcesTool(manager)
"""

from __future__ import annotations

from pydantic import BaseModel

from illusion.mcp.client import McpClientManager
from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class ListMcpResourcesToolInput(BaseModel):
    """MCP 资源列表参数。"""


class ListMcpResourcesTool(BaseTool):
    """列出从已连接服务器发现的 MCP 资源。

    用于查看可用的 MCP 服务器资源。
    """

    name = "list_mcp_resources"
    description = """List available resources from configured MCP servers.
Each returned resource will include all standard MCP resource fields plus a 'server' field
indicating which server the resource belongs to.

Parameters:
- server (optional): The name of a specific MCP server to get resources from. If not provided,
  resources from all servers will be returned."""
    input_model = ListMcpResourcesToolInput

    def __init__(self, manager: McpClientManager) -> None:
        self._manager = manager

    def is_read_only(self, arguments: ListMcpResourcesToolInput) -> bool:
        del arguments
        return True

    async def execute(self, arguments: ListMcpResourcesToolInput, context: ToolExecutionContext) -> ToolResult:
        del arguments, context
        # 获取所有资源
        resources = self._manager.list_resources()
        if not resources:
            return ToolResult(output="(no MCP resources)")
        return ToolResult(
            output="\n".join(f"{item.server_name}:{item.uri} {item.description}".strip() for item in resources)
        )
