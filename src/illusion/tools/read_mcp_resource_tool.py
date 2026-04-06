"""Tool to read MCP resources."""

from __future__ import annotations

from pydantic import BaseModel, Field

from illusion.mcp.client import McpClientManager
from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class ReadMcpResourceToolInput(BaseModel):
    """Arguments for reading an MCP resource."""

    server: str = Field(description="MCP server name")
    uri: str = Field(description="Resource URI")


class ReadMcpResourceTool(BaseTool):
    """Read one resource from an MCP server."""

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
        output = await self._manager.read_resource(arguments.server, arguments.uri)
        return ToolResult(output=output)
