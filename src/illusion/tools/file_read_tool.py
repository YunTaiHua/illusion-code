"""
文件读取工具
===========

本模块提供读取本地文件系统文件的功能，支持文本文件和部分二进制格式。

主要组件：
    - FileReadTool: 读取 UTF-8 文本文件的工具

使用示例：
    >>> from illusion.tools import FileReadTool
    >>> tool = FileReadTool()
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class FileReadToolInput(BaseModel):
    """文件读取参数。

    属性：
        path: 要读取的文件路径
        offset: 起始行号（从 0 开始）
        limit: 返回的行数限制
    """

    path: str = Field(description="Path of the file to read")
    offset: int = Field(default=0, ge=0, description="Zero-based starting line")
    limit: int = Field(default=200, ge=1, le=2000, description="Number of lines to return")


class FileReadTool(BaseTool):
    """读取带行号的 UTF-8 文本文件。

    用于查看文件内容，支持指定行范围。
    """

    name = "read_file"
    description = """Reads a file from the local filesystem. You can access any file directly by using this tool.
Assume this tool is able to read all files on the machine. If the User provides a path to a file assume that path is valid. It is okay to read a file that does not exist; an error will be returned.

Usage:
- The file_path parameter must be an absolute path, not a relative path
- By default, it reads up to 2000 lines starting from the beginning of the file
- You can optionally specify a line offset and limit (especially handy for long files), but it's recommended to read the whole file by not providing these parameters
- Results are returned using cat -n format, with line numbers starting at 1
- This tool allows Illusion Code to read images (eg PNG, JPG, etc). When reading an image file the contents are presented visually as Illusion Code is a multimodal LLM.
- This tool can read PDF files (.pdf). For large PDFs (more than 10 pages), you MUST provide the pages parameter to read specific page ranges (e.g., pages: "1-5"). Reading a large PDF without the pages parameter will fail. Maximum 20 pages per request.
- This tool can read Jupyter notebooks (.ipynb files) and returns all cells with their outputs, combining code, text, and visualizations.
- This tool can only read files, not directories. To read a directory, use an ls command via the Bash tool.
- You will regularly be asked to read screenshots. If the user provides a path to a screenshot, ALWAYS use this tool to view the file at the path. This tool will work with all temporary file paths.
- If you read a file that exists but has empty contents you will receive a system reminder warning in place of file contents."""
    input_model = FileReadToolInput

    def is_read_only(self, arguments: FileReadToolInput) -> bool:
        del arguments
        return True

    async def execute(
        self,
        arguments: FileReadToolInput,
        context: ToolExecutionContext,
    ) -> ToolResult:
        # 解析文件路径
        path = _resolve_path(context.cwd, arguments.path)
        # 检查文件是否存在
        if not path.exists():
            return ToolResult(output=f"File not found: {path}", is_error=True)
        # 检查是否为目录
        if path.is_dir():
            return ToolResult(output=f"Cannot read directory: {path}", is_error=True)

        # 读取文件内容
        raw = path.read_bytes()
        # 检查是否为二进制文件
        if b"\x00" in raw:
            return ToolResult(output=f"Binary file cannot be read as text: {path}", is_error=True)

        # 解码为 UTF-8 文本
        text = raw.decode("utf-8", errors="replace")
        lines = text.splitlines()
        # 根据 offset 和 limit 选取行
        selected = lines[arguments.offset : arguments.offset + arguments.limit]
        # 添加行号
        numbered = [
            f"{arguments.offset + index + 1:>6}\t{line}"
            for index, line in enumerate(selected)
        ]
        if not numbered:
            return ToolResult(output=f"(no content in selected range for {path})")

        # 注册文件已被读取（用于读后编辑强制检查）
        from illusion.tools.file_edit_tool import mark_file_read
        mark_file_read(str(path))

        return ToolResult(output="\n".join(numbered))


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
