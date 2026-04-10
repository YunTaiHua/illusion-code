"""
轻量级代码智能工具
==================

本模块提供与语言服务器协议（LSP）交互的功能，用于 Python 代码的代码智能查询。

主要组件：
    - LspTool: 代码智能查询工具

使用示例：
    >>> from illusion.tools import LspTool
    >>> tool = LspTool()
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from illusion.services.lsp import (
    find_references,
    go_to_definition,
    hover,
    list_document_symbols,
    workspace_symbol_search,
)
from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class LspToolInput(BaseModel):
    """代码智能查询参数。

    属性：
        operation: 要执行的代码智能操作
        file_path: 用于基于文件的操作的源文件路径
        symbol: 要查找的显式符号名称
        line: 基于位置查询的 1-based 行号
        character: 基于位置查询的 1-based 字符偏移
        query: workspace_symbol 的子字符串查询
    """

    operation: Literal[
        "document_symbol",
        "workspace_symbol",
        "go_to_definition",
        "find_references",
        "hover",
    ] = Field(description="The code intelligence operation to perform")
    file_path: str | None = Field(default=None, description="Path to the source file for file-based operations")
    symbol: str | None = Field(default=None, description="Explicit symbol name to look up")
    line: int | None = Field(default=None, ge=1, description="1-based line number for position-based lookups")
    character: int | None = Field(default=None, ge=1, description="1-based character offset for position-based lookups")
    query: str | None = Field(default=None, description="Substring query for workspace_symbol")

    @model_validator(mode="after")
    def validate_arguments(self) -> "LspToolInput":
        # workspace_symbol 需要 query 参数
        if self.operation == "workspace_symbol":
            if not self.query:
                raise ValueError("workspace_symbol requires query")
            return self
        # 其他操作需要 file_path
        if not self.file_path:
            raise ValueError(f"{self.operation} requires file_path")
        # document_symbol 不需要 symbol 或 line
        if self.operation == "document_symbol":
            return self
        # 其他操作需要 symbol 或 line
        if not self.symbol and self.line is None:
            raise ValueError(f"{self.operation} requires symbol or line")
        return self


class LspTool(BaseTool):
    """Python 源文件的只读代码智能。

    用于查询代码定义、引用、悬停信息等。
    """

    name = "lsp"
    description = """Interact with Language Server Protocol (LSP) servers to get code intelligence features.

Supported operations:
- goToDefinition: Find where a symbol is defined
- findReferences: Find all references to a symbol
- hover: Get hover information (documentation, type info) for a symbol
- documentSymbol: Get all symbols (functions, classes, variables) in a document
- workspaceSymbol: Search for symbols across the entire workspace
- goToImplementation: Find implementations of an interface or abstract method
- prepareCallHierarchy: Get call hierarchy item at a position (functions/methods)
- incomingCalls: Find all functions/methods that call the function at a position
- outgoingCalls: Find all functions/methods called by the function at a position

All operations require:
- filePath: The file to operate on
- line: The line number (1-based, as shown in editors)
- character: The character offset (1-based, as shown in editors)

Note: LSP servers must be configured for the file type. If no server is available, an error will be returned."""
    input_model = LspToolInput

    def is_read_only(self, arguments: LspToolInput) -> bool:
        del arguments
        return True

    async def execute(self, arguments: LspToolInput, context: ToolExecutionContext) -> ToolResult:
        # 获取工作区根目录
        root = context.cwd.resolve()

        # workspace_symbol 操作
        if arguments.operation == "workspace_symbol":
            results = workspace_symbol_search(root, arguments.query or "")
            return ToolResult(output=_format_symbol_locations(results, root))

        # 解析文件路径
        assert arguments.file_path is not None  # 已在上面验证
        file_path = _resolve_path(root, arguments.file_path)
        if not file_path.exists():
            return ToolResult(output=f"File not found: {file_path}", is_error=True)
        if file_path.suffix != ".py":
            return ToolResult(output="The lsp tool currently supports Python files only.", is_error=True)

        # 执行对应的代码智能操作
        if arguments.operation == "document_symbol":
            return ToolResult(output=_format_symbol_locations(list_document_symbols(file_path), root))

        if arguments.operation == "go_to_definition":
            results = go_to_definition(
                root=root,
                file_path=file_path,
                symbol=arguments.symbol,
                line=arguments.line,
                character=arguments.character,
            )
            return ToolResult(output=_format_symbol_locations(results, root))

        if arguments.operation == "find_references":
            results = find_references(
                root=root,
                file_path=file_path,
                symbol=arguments.symbol,
                line=arguments.line,
                character=arguments.character,
            )
            return ToolResult(output=_format_references(results, root))

        # hover 操作
        result = hover(
            root=root,
            file_path=file_path,
            symbol=arguments.symbol,
            line=arguments.line,
            character=arguments.character,
        )
        if result is None:
            return ToolResult(output="(no hover result)")
        # 构建输出
        parts = [
            f"{result.kind} {result.name}",
            f"path: {_display_path(result.path, root)}:{result.line}:{result.character}",
        ]
        if result.signature:
            parts.append(f"signature: {result.signature}")
        if result.docstring:
            parts.append(f"docstring: {result.docstring.strip()}")
        return ToolResult(output="\n".join(parts))


def _resolve_path(base: Path, candidate: str) -> Path:
    """解析相对路径为绝对路径。"""
    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def _display_path(path: Path, root: Path) -> str:
    """将路径显示为相对于根目录的路径。"""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _format_symbol_locations(results, root: Path) -> str:
    """格式化符号位置结果。"""
    if not results:
        return "(no results)"
    lines = []
    for item in results:
        lines.append(
            f"{item.kind} {item.name} - {_display_path(item.path, root)}:{item.line}:{item.character}"
        )
        if item.signature:
            lines.append(f"  signature: {item.signature}")
        if item.docstring:
            lines.append(f"  docstring: {item.docstring.strip()}")
    return "\n".join(lines)


def _format_references(results: list[tuple[Path, int, str]], root: Path) -> str:
    """格式化引用结果。"""
    if not results:
        return "(no results)"
    return "\n".join(f"{_display_path(path, root)}:{line}:{text}" for path, line, text in results)

