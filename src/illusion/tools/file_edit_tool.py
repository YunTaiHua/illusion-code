"""
字符串替换文件编辑工具
======================

本模块提供在现有文件中进行精确字符串替换的功能。

主要组件：
    - FileEditTool: 替换文件中文本的工具

使用示例：
    >>> from illusion.tools import FileEditTool
    >>> tool = FileEditTool()
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field

from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


# 模块级集合，跟踪本次会话中已读取的文件
# FileReadTool 写入此集合；FileEditTool 从中读取
_read_files: set[str] = set()


def mark_file_read(abs_path: str) -> None:
    """记录文件已被读取（在 FileReadTool 读取后调用）。"""
    _read_files.add(abs_path)


def has_file_been_read(abs_path: str) -> bool:
    """检查文件是否在本次会话中已被读取。"""
    return abs_path in _read_files


class FileEditToolInput(BaseModel):
    """文件编辑参数。

    属性：
        path: 要编辑的文件路径
        old_str: 要替换的现有文本
        new_str: 替换文本
        replace_all: 是否替换所有匹配项
    """

    path: str = Field(description="Path of the file to edit")
    old_str: str = Field(description="Existing text to replace")
    new_str: str = Field(description="Replacement text")
    replace_all: bool = Field(default=False)


class FileEditTool(BaseTool):
    """替换现有文件中的文本。

    用于对文件进行精确的字符串替换编辑。
    """

    name = "edit_file"
    description = """Performs exact string replacements in files.

Usage:
- You must use your `Read` tool at least once in the conversation before editing. This tool will error if you attempt an edit without reading the file.
- When editing text from Read tool output, ensure you preserve the exact indentation (tabs/spaces) as it appears AFTER the line number prefix. The line number prefix format is: spaces + line number + arrow. Everything after that is the actual file content to match. Never include any part of the line number prefix in the old_string or new_string.
- ALWAYS prefer editing existing files in the codebase. NEVER write new files unless explicitly required.
- Only use emojis if the user explicitly requests it. Avoid adding emojis to files unless asked.
- The edit will FAIL if `old_string` is not unique in the file. Either provide a larger string with more surrounding context to make it unique or use `replace_all` to change every instance of `old_string`.
- Use `replace_all` for replacing and renaming strings across the file. This parameter is useful if you want to rename a variable for instance.
- Use the smallest old_string that's clearly unique — usually 2-4 adjacent lines is sufficient. Avoid including 10+ lines of context when less uniquely identifies the target."""
    input_model = FileEditToolInput

    async def execute(
        self,
        arguments: FileEditToolInput,
        context: ToolExecutionContext,
    ) -> ToolResult:
        # 解析文件路径
        path = _resolve_path(context.cwd, arguments.path)

        # 拒绝 notebook 文件 — 模型应使用 NotebookEdit
        if path.suffix.lower() == ".ipynb":
            return ToolResult(
                output=".ipynb files must be edited with the notebook_edit tool, not edit_file.",
                is_error=True,
            )

        # 处理新文件创建：仅当 old_str 为空时允许
        if not path.exists():
            if arguments.old_str:
                return ToolResult(
                    output=f"File not found: {path}. To create a new file, set old_str to empty string.",
                    is_error=True,
                )
            # 创建新文件
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(arguments.new_str, encoding="utf-8")
            mark_file_read(str(path))
            return ToolResult(output=f"Created {path}")

        # 读后编辑强制检查
        if not has_file_been_read(str(path)):
            return ToolResult(
                output=(
                    f"You must read the file at {path} using the Read tool "
                    "before you can edit it. This tool will error if you attempt "
                    "an edit without reading the file first."
                ),
                is_error=True,
            )

        # 空操作保护
        if arguments.old_str == arguments.new_str:
            return ToolResult(
                output="old_string and new_string are identical — no changes needed.",
                is_error=True,
            )

        # 非空文件上的空 old_str
        original = path.read_text(encoding="utf-8")
        if not arguments.old_str and original.strip():
            return ToolResult(
                output=(
                    "old_string is empty but the file is not empty. "
                    "To replace the entire file content, use the Write tool instead."
                ),
                is_error=True,
            )

        # 空文件上的空 old_str = 写入新内容
        if not arguments.old_str and not original.strip():
            path.write_text(arguments.new_str, encoding="utf-8")
            return ToolResult(output=f"Updated {path}")

        # 检查 old_str 是否存在于文件中
        if arguments.old_str not in original:
            # 尝试提供关于文件中内容的帮助上下文
            _similar = _find_similar_lines(original, arguments.old_str)
            msg = "old_string was not found in the file."
            if _similar:
                msg += f"\n\nThe closest matches in the file are:\n{_similar}"
            return ToolResult(output=msg, is_error=True)

        # 唯一性检查（当不是替换所有时）
        if not arguments.replace_all:
            count = original.count(arguments.old_str)
            if count > 1:
                return ToolResult(
                    output=(
                        f"old_string appears {count} times in the file. "
                        "Either provide a larger string with more surrounding context to make it unique, "
                        "or use replace_all=true to change every instance."
                    ),
                    is_error=True,
                )

        # 应用编辑
        if arguments.replace_all:
            updated = original.replace(arguments.old_str, arguments.new_str)
        else:
            updated = original.replace(arguments.old_str, arguments.new_str, 1)

        path.write_text(updated, encoding="utf-8")
        return ToolResult(output=f"Updated {path}")


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


def _find_similar_lines(content: str, target: str, max_lines: int = 5) -> str:
    """在内容中找到与目标字符串部分匹配的行。

    返回格式化的字符串，显示最接近的匹配，或空字符串。
    """
    target_lines = [line.strip() for line in target.splitlines() if line.strip()]
    if not target_lines:
        return ""

    content_lines = content.splitlines()
    matches: list[str] = []
    first_target = target_lines[0].lower()

    for i, line in enumerate(content_lines):
        stripped = line.strip().lower()
        # 检查此行是否包含第一个目标行或被其包含
        if first_target in stripped or stripped in first_target:
            start = max(0, i - 1)
            end = min(len(content_lines), i + 2)
            block = "\n".join(f"  {j+1}: {content_lines[j]}" for j in range(start, end))
            matches.append(block)
            if len(matches) >= max_lines:
                break

    return "\n\n".join(matches) if matches else ""
