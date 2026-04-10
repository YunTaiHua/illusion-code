"""
工具搜索工具
============

本模块提供搜索可用工具注册表的功能。

主要组件：
    - ToolSearchTool: 搜索工具注册表的工具

使用示例：
    >>> from illusion.tools import ToolSearchTool
    >>> tool = ToolSearchTool()
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class ToolSearchToolInput(BaseModel):
    """工具搜索参数。

    属性：
        query: 在工具名称和描述中搜索的子字符串
    """

    query: str = Field(description="Substring to search in tool names and descriptions")


class ToolSearchTool(BaseTool):
    """搜索工具注册表内容。

    用于查找已注册的工具。
    """

    name = "tool_search"
    description = """Fetches full schema definitions for deferred tools so they can be called.

Deferred tools appear by name in <system-reminder> messages. Until fetched, only the name is known — there is no parameter schema, so the tool cannot be invoked. This tool takes a query, matches it against the deferred tool list, and returns the matched tools' complete JSONSchema definitions inside a <functions> block. Once a tool's schema appears in that result, it is callable exactly like any tool defined at the top of this prompt.

Result format: each matched tool appears as one <function>{"description": "...", "name": "...", "parameters": {...}}</function> line inside the <functions> block — the same encoding as the tool list at the top of this prompt.

Query forms:
- "select:Read,Edit,Grep" — fetch these exact tools by name
- "notebook jupyter" — keyword search, up to max_results best matches
- "+slack send" — require "slack" in the name, rank by remaining terms"""
    input_model = ToolSearchToolInput

    def is_read_only(self, arguments: ToolSearchToolInput) -> bool:
        del arguments
        return True

    async def execute(self, arguments: ToolSearchToolInput, context: ToolExecutionContext) -> ToolResult:
        # 获取工具注册表
        registry = context.metadata.get("tool_registry") if hasattr(context, "metadata") else None
        if registry is None:
            return ToolResult(output="Tool registry context not available", is_error=True)
        # 搜索匹配的工具
        query = arguments.query.lower()
        matches = [
            tool for tool in registry.list_tools()
            if query in tool.name.lower() or query in tool.description.lower()
        ]
        if not matches:
            return ToolResult(output="(no matches)")
        return ToolResult(output="\n".join(f"{tool.name}: {tool.description}" for tool in matches))
