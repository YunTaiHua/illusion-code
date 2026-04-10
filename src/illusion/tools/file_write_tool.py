"""
文件写入工具
===========

本模块提供写入完整文件内容到本地文件系统的功能。

主要组件：
    - FileWriteTool: 写入完整文件内容的工具

使用示例：
    >>> from illusion.tools import FileWriteTool
    >>> tool = FileWriteTool()
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class FileWriteToolInput(BaseModel):
    """文件写入参数。

    属性：
        path: 要写入的文件路径
        content: 完整的文件内容
        create_directories: 是否创建父目录
    """

    path: str = Field(description="Path of the file to write")
    content: str = Field(description="Full file contents")
    create_directories: bool = Field(default=True)


class FileWriteTool(BaseTool):
    """写入完整的文件内容。

    用于创建新文件或完全重写现有文件。
    """

    name = "write_file"
    description = """Writes a file to the local filesystem.

Usage:
- This tool will overwrite the existing file if there is one at the provided path.
- If this is an existing file, you MUST use the Read tool first to read the file's contents. This tool will fail if you read the file first.
- Prefer the Edit tool for modifying existing files — it only sends the diff. Only use this tool to create new files or for complete rewrites.
- NEVER create documentation files (*.md) or README files unless explicitly requested by the User.
- Only use emojis if the user explicitly requests it. Avoid writing emojis to files unless asked.
"""
    input_model = FileWriteToolInput

    async def execute(
        self,
        arguments: FileWriteToolInput,
        context: ToolExecutionContext,
    ) -> ToolResult:
        # 解析文件路径
        path = _resolve_path(context.cwd, arguments.path)

        # 对于已有文件，执行读后写强制检查
        if path.exists():
            from illusion.tools.file_edit_tool import has_file_been_read, mark_file_read
            if not has_file_been_read(str(path)):
                return ToolResult(
                    output=(
                        f"You must read the file at {path} using the Read tool "
                        "before you can write to it. This tool will fail if you attempt "
                        "a write without reading the file first."
                    ),
                    is_error=True,
                )

        # 如果需要，创建父目录
        if arguments.create_directories:
            path.parent.mkdir(parents=True, exist_ok=True)

        # 判断是创建还是更新
        action = "update" if path.exists() else "create"

        # 写入文件内容
        path.write_text(arguments.content, encoding="utf-8")

        # 写入后将文件标记为已读，以便后续编辑
        from illusion.tools.file_edit_tool import mark_file_read
        mark_file_read(str(path))

        return ToolResult(output=f"{action.title()}d {path}")


def _resolve_path(base: Path, candidate: str) -> Path:
    """解析相对路径为绝对路径。

    参数：
        base: 基础目录
        candidate: 候选路径（可能是相对路径）

    返回：
        解析后的绝对路径
    """
    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()
