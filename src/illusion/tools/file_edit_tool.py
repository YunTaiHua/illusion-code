"""String-based file editing tool."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field

from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


# Module-level set tracking which files have been read in this session.
# The FileReadTool writes to this set; FileEditTool reads from it.
_read_files: set[str] = set()


def mark_file_read(abs_path: str) -> None:
    """Record that a file has been read (called by FileReadTool after reading)."""
    _read_files.add(abs_path)


def has_file_been_read(abs_path: str) -> bool:
    """Check whether a file has been read in this session."""
    return abs_path in _read_files


class FileEditToolInput(BaseModel):
    """Arguments for the file edit tool."""

    path: str = Field(description="Path of the file to edit")
    old_str: str = Field(description="Existing text to replace")
    new_str: str = Field(description="Replacement text")
    replace_all: bool = Field(default=False)


class FileEditTool(BaseTool):
    """Replace text in an existing file."""

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
        path = _resolve_path(context.cwd, arguments.path)

        # Reject notebook files — model should use NotebookEdit instead
        if path.suffix.lower() == ".ipynb":
            return ToolResult(
                output=".ipynb files must be edited with the notebook_edit tool, not edit_file.",
                is_error=True,
            )

        # Handle new file creation: only allowed when old_str is empty
        if not path.exists():
            if arguments.old_str:
                return ToolResult(
                    output=f"File not found: {path}. To create a new file, set old_str to empty string.",
                    is_error=True,
                )
            # Create new file
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(arguments.new_str, encoding="utf-8")
            mark_file_read(str(path))
            return ToolResult(output=f"Created {path}")

        # Read-before-edit enforcement
        if not has_file_been_read(str(path)):
            return ToolResult(
                output=(
                    f"You must read the file at {path} using the Read tool "
                    "before you can edit it. This tool will error if you attempt "
                    "an edit without reading the file first."
                ),
                is_error=True,
            )

        # No-op guard
        if arguments.old_str == arguments.new_str:
            return ToolResult(
                output="old_string and new_string are identical — no changes needed.",
                is_error=True,
            )

        # Empty old_str on non-empty existing file
        original = path.read_text(encoding="utf-8")
        if not arguments.old_str and original.strip():
            return ToolResult(
                output=(
                    "old_string is empty but the file is not empty. "
                    "To replace the entire file content, use the Write tool instead."
                ),
                is_error=True,
            )

        # Empty old_str on empty file = write new content
        if not arguments.old_str and not original.strip():
            path.write_text(arguments.new_str, encoding="utf-8")
            return ToolResult(output=f"Updated {path}")

        # Check old_str exists in file
        if arguments.old_str not in original:
            # Try to provide helpful context about what's in the file
            _similar = _find_similar_lines(original, arguments.old_str)
            msg = "old_string was not found in the file."
            if _similar:
                msg += f"\n\nThe closest matches in the file are:\n{_similar}"
            return ToolResult(output=msg, is_error=True)

        # Uniqueness check (when not replacing all)
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

        # Apply the edit
        if arguments.replace_all:
            updated = original.replace(arguments.old_str, arguments.new_str)
        else:
            updated = original.replace(arguments.old_str, arguments.new_str, 1)

        path.write_text(updated, encoding="utf-8")
        return ToolResult(output=f"Updated {path}")


def _resolve_path(base: Path, candidate: str) -> Path:
    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def _find_similar_lines(content: str, target: str, max_lines: int = 5) -> str:
    """Find lines in content that partially match lines in the target string.

    Returns a formatted string showing the closest matches, or empty string.
    """
    target_lines = [line.strip() for line in target.splitlines() if line.strip()]
    if not target_lines:
        return ""

    content_lines = content.splitlines()
    matches: list[str] = []
    first_target = target_lines[0].lower()

    for i, line in enumerate(content_lines):
        stripped = line.strip().lower()
        # Check if this line contains the first target line or vice versa
        if first_target in stripped or stripped in first_target:
            start = max(0, i - 1)
            end = min(len(content_lines), i + 2)
            block = "\n".join(f"  {j+1}: {content_lines[j]}" for j in range(start, end))
            matches.append(block)
            if len(matches) >= max_lines:
                break

    return "\n\n".join(matches) if matches else ""
