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

from difflib import unified_diff
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
- If this is an existing file, you MUST use the Read tool first to read the file's contents. This tool will fail if you did not read the file first.
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
        """执行文件写入操作，对新文件返回内容预览，对已有文件返回差异信息
        
        Args:
            arguments: 文件写入参数
            context: 工具执行上下文
        
        Returns:
            ToolResult: 包含写入结果和差异/预览文本的执行结果
        """
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
        is_update = path.exists()

        # 对于已有文件，读取原始内容以生成diff
        original = ""
        if is_update:
            original = path.read_text(encoding="utf-8")

        # 写入文件内容
        path.write_text(arguments.content, encoding="utf-8")

        # 写入后将文件标记为已读，以便后续编辑
        from illusion.tools.file_edit_tool import mark_file_read
        mark_file_read(str(path))

        # 生成差异或预览
        if is_update:
            diff_text = _generate_diff(str(path), original, arguments.content)
            return ToolResult(output=f"Updated {path}\n{diff_text}")
        else:
            preview = _generate_create_preview(str(path), arguments.content)
            return ToolResult(output=f"Created {path}\n{preview}")


def _generate_diff(file_path: str, original: str, updated: str, context_lines: int = 3) -> str:
    """生成统一差异格式的文本

    Args:
        file_path: 文件路径
        original: 原始内容
        updated: 更新后内容
        context_lines: 上下文行数

    Returns:
        str: 差异文本
    """
    original_lines = original.splitlines(keepends=True)
    updated_lines = updated.splitlines(keepends=True)
    diff_lines = list(unified_diff(
        original_lines,
        updated_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
        n=context_lines,
    ))
    if not diff_lines:
        return ""
    return "".join(diff_lines).rstrip()


def _generate_create_preview(file_path: str, content: str, max_lines: int = 10) -> str:
    """生成新文件创建的内容预览

    Args:
        file_path: 文件路径
        content: 文件内容
        max_lines: 最大预览行数

    Returns:
        str: 预览文本
    """
    lines = content.splitlines()
    total = len(lines)
    if total <= max_lines:
        return content
    preview_lines = lines[:max_lines]
    remaining = total - max_lines
    return "\n".join(preview_lines) + f"\n... +{remaining} lines"


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
