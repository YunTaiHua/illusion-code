"""Content search tool with a pure-Python fallback."""

from __future__ import annotations

import asyncio
import re
import shutil
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class GrepToolInput(BaseModel):
    """Arguments for the grep tool."""

    pattern: str = Field(description="Regular expression to search for")
    path: str | None = Field(default=None, description="File or directory to search")
    glob: str | None = Field(default=None, description='File filter glob (e.g., "*.js", "**/*.tsx")')
    output_mode: Literal["content", "files_with_matches", "count"] = Field(
        default="files_with_matches",
        description="Output mode: content shows matching lines, files_with_matches shows only file paths (default), count shows match counts",
    )
    context_before: int | None = Field(default=None, description="Lines before match")
    context_after: int | None = Field(default=None, description="Lines after match")
    context: int | None = Field(default=None, description="Lines around match (overrides -B/-A)")
    case_sensitive: bool = Field(default=True, description="Case sensitive search")
    type: str | None = Field(default=None, description='rg --type filter (e.g., "js", "py", "rust")')
    multiline: bool = Field(default=False, description="Enable multiline matching (rg -U --multiline-dotall)")
    head_limit: int = Field(default=250, ge=0, description="Max results (0 = unlimited)")
    offset: int = Field(default=0, ge=0, description="Skip first N results")


class GrepTool(BaseTool):
    """Search text files for a regex pattern."""

    name = "grep"
    description = """A powerful search tool built on ripgrep

Usage:
- ALWAYS use Grep for search tasks. NEVER invoke `grep` or `rg` as a Bash command. The Grep tool has been optimized for correct permissions and access.
- Supports full regex syntax (e.g., "log.*Error", "function\\s+\\w+")
- Filter files with glob parameter (e.g., "*.js", "**/*.tsx") or type parameter (e.g., "js", "py", "rust")
- Output modes: "content" shows matching lines, "files_with_matches" shows only file paths (default), "count" shows match counts
- Use Agent tool for open-ended searches requiring multiple rounds
- Pattern syntax: Uses ripgrep (not grep) - literal braces need escaping (use `interface\\{\\}` to find `interface{}` in Go code)
- Multiline matching: By default patterns match within single lines only. For cross-line patterns like `struct \\{[\\s\\S]*?field`, use `multiline: true`"""
    input_model = GrepToolInput

    def is_read_only(self, arguments: GrepToolInput) -> bool:
        del arguments
        return True

    async def execute(self, arguments: GrepToolInput, context: ToolExecutionContext) -> ToolResult:
        root = _resolve_path(context.cwd, arguments.path) if arguments.path else context.cwd

        if not root.exists():
            return ToolResult(output=f"Path does not exist: {root}", is_error=True)

        # For ripgrep: build args based on output_mode
        if root.is_file():
            result = await _rg_search(
                path=root,
                pattern=arguments.pattern,
                output_mode=arguments.output_mode,
                glob=arguments.glob,
                case_sensitive=arguments.case_sensitive,
                context_before=arguments.context or arguments.context_before,
                context_after=arguments.context or arguments.context_after,
                type_filter=arguments.type,
                multiline=arguments.multiline,
                head_limit=arguments.head_limit,
                offset=arguments.offset,
                cwd=context.cwd,
            )
            if result is not None:
                return ToolResult(output=result)

            # Python fallback for single file
            return ToolResult(
                output=_python_grep_file(
                    path=root,
                    pattern=arguments.pattern,
                    output_mode=arguments.output_mode,
                    case_sensitive=arguments.case_sensitive,
                    head_limit=arguments.head_limit,
                    offset=arguments.offset,
                    display_base=_display_base(root, context.cwd),
                )
            )

        # Directory search
        result = await _rg_search(
            path=root,
            pattern=arguments.pattern,
            output_mode=arguments.output_mode,
            glob=arguments.glob,
            case_sensitive=arguments.case_sensitive,
            context_before=arguments.context or arguments.context_before,
            context_after=arguments.context or arguments.context_after,
            type_filter=arguments.type,
            multiline=arguments.multiline,
            head_limit=arguments.head_limit,
            offset=arguments.offset,
            cwd=context.cwd,
        )
        if result is not None:
            return ToolResult(output=result)

        # Python fallback for directory
        return ToolResult(
            output=_python_grep_dir(
                root=root,
                pattern=arguments.pattern,
                glob=arguments.glob or "**/*",
                output_mode=arguments.output_mode,
                case_sensitive=arguments.case_sensitive,
                head_limit=arguments.head_limit,
                offset=arguments.offset,
                display_base=root,
            )
        )


def _display_base(path: Path, cwd: Path) -> Path:
    try:
        path.relative_to(cwd)
    except ValueError:
        return path.parent
    return cwd


def _format_path(path: Path, display_base: Path) -> str:
    try:
        return str(path.relative_to(display_base))
    except ValueError:
        return str(path)


def _resolve_path(base: Path, candidate: str | None) -> Path:
    path = Path(candidate or ".").expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def _apply_pagination(lines: list[str], head_limit: int, offset: int) -> list[str]:
    """Apply offset and head_limit to a list of results."""
    sliced = lines[offset:]
    if head_limit > 0:
        sliced = sliced[:head_limit]
    return sliced


async def _rg_search(
    *,
    path: Path,
    pattern: str,
    output_mode: str,
    glob: str | None,
    case_sensitive: bool,
    context_before: int | None,
    context_after: int | None,
    type_filter: str | None,
    multiline: bool,
    head_limit: int,
    offset: int,
    cwd: Path,
) -> str | None:
    """Unified ripgrep search for both files and directories.

    Returns formatted output string, or None if rg is unavailable.
    """
    rg = shutil.which("rg")
    if not rg:
        return None

    is_dir = path.is_dir()
    include_hidden = is_dir and ((path / ".git").exists() or (path / ".gitignore").exists())

    cmd: list[str] = [rg, "--color", "never"]

    # Output mode flags
    if output_mode == "files_with_matches":
        cmd.append("-l")  # only file paths
    elif output_mode == "count":
        cmd.append("-c")  # count mode
    else:
        # content mode - show line numbers and optionally context
        cmd.extend(["--no-heading", "--line-number"])

    if include_hidden:
        cmd.append("--hidden")

    # VCS directory exclusions
    for vcs_dir in (".git", ".svn", ".hg", ".bzr"):
        cmd.extend(["--glob", f"!{vcs_dir}"])

    if not case_sensitive:
        cmd.append("-i")

    # Context lines (only in content mode)
    if output_mode == "content":
        if context_before is not None:
            cmd.extend(["-B", str(context_before)])
        if context_after is not None:
            cmd.extend(["-A", str(context_after)])

    # Multiline
    if multiline:
        cmd.extend(["-U", "--multiline-dotall"])

    # Type filter
    if type_filter:
        cmd.extend(["--type", type_filter])

    # Glob filter - handle space-separated patterns and brace expansion
    if glob:
        # Keep brace patterns like *.{ts,tsx} intact
        parts = glob.split()
        for part in parts:
            cmd.extend(["--glob", part])

    # Max columns to prevent base64/minified content from flooding output
    cmd.extend(["--max-columns", "500"])

    # Pattern - use -e if pattern starts with -
    if pattern.startswith("-"):
        cmd.extend(["-e", pattern])
    else:
        cmd.append(pattern)

    # Path to search
    if is_dir:
        cmd.append(".")
    else:
        cmd.append(str(path))

    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(path) if is_dir else str(path.parent),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    raw_lines: list[str] = []
    limit = head_limit if head_limit > 0 else 10000  # safety cap for unlimited
    try:
        assert process.stdout is not None
        while len(raw_lines) < limit + offset:
            raw = await process.stdout.readline()
            if not raw:
                break
            line = raw.decode("utf-8", errors="replace").rstrip("\n")
            if line:
                raw_lines.append(line)
    finally:
        if len(raw_lines) >= limit + offset and process.returncode is None:
            process.terminate()
        await process.wait()

    # rg exits 0 when matches are found, 1 when none are found
    if process.returncode not in {0, 1}:
        return None

    if not raw_lines:
        return "(no matches)"

    # Apply pagination
    paged = _apply_pagination(raw_lines, head_limit, offset)

    # Format output based on mode
    if output_mode == "files_with_matches":
        # Convert to relative paths
        display_base = _display_base(path, cwd) if not is_dir else cwd
        rel_paths = []
        for line in paged:
            file_path = Path(line)
            rel_paths.append(_format_path(file_path, display_base))
        return "\n".join(rel_paths) if rel_paths else "(no matches)"

    if output_mode == "count":
        display_base = cwd if is_dir else _display_base(path, cwd)
        formatted = []
        for line in paged:
            parts = line.rsplit(":", 1)
            if len(parts) == 2:
                file_path = Path(parts[0])
                rel = _format_path(file_path, display_base)
                formatted.append(f"{rel}:{parts[1]}")
            else:
                formatted.append(line)
        return "\n".join(formatted) if formatted else "(no matches)"

    # content mode - convert paths to relative
    if not is_dir:
        display_base = _display_base(path, cwd)
        prefix = _format_path(path, display_base)
        return "\n".join(paged) if paged else "(no matches)"

    return "\n".join(paged) if paged else "(no matches)"


def _python_grep_file(
    *,
    path: Path,
    pattern: str,
    output_mode: str,
    case_sensitive: bool,
    head_limit: int,
    offset: int,
    display_base: Path,
) -> str:
    """Pure Python fallback for single file grep."""
    flags = 0 if case_sensitive else re.IGNORECASE
    compiled = re.compile(pattern, flags)

    try:
        raw = path.read_bytes()
    except OSError:
        return "(no matches)"
    if b"\x00" in raw:
        return "(no matches)"

    text = raw.decode("utf-8", errors="replace")
    rel_path = _format_path(path, display_base)

    if output_mode == "files_with_matches":
        for line in text.splitlines():
            if compiled.search(line):
                return rel_path
        return "(no matches)"

    if output_mode == "count":
        count = sum(1 for line in text.splitlines() if compiled.search(line))
        return f"{rel_path}:{count}" if count > 0 else "(no matches)"

    # content mode
    matches: list[str] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if compiled.search(line):
            matches.append(f"{rel_path}:{line_no}:{line}")

    if not matches:
        return "(no matches)"

    paged = _apply_pagination(matches, head_limit, offset)
    return "\n".join(paged)


def _python_grep_dir(
    *,
    root: Path,
    pattern: str,
    glob: str,
    output_mode: str,
    case_sensitive: bool,
    head_limit: int,
    offset: int,
    display_base: Path,
) -> str:
    """Pure Python fallback for directory grep."""
    flags = 0 if case_sensitive else re.IGNORECASE
    compiled = re.compile(pattern, flags)
    limit = head_limit if head_limit > 0 else 10000

    file_matches: list[str] = []  # for files_with_matches
    content_matches: list[str] = []  # for content/count
    count_matches: list[str] = []  # for count

    for path in root.glob(glob):
        if not path.is_file():
            continue
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        if b"\x00" in raw:
            continue

        text = raw.decode("utf-8", errors="replace")
        rel_path = _format_path(path, display_base)

        if output_mode == "files_with_matches":
            for line in text.splitlines():
                if compiled.search(line):
                    file_matches.append(rel_path)
                    break
            if len(file_matches) >= limit + offset:
                break
        elif output_mode == "count":
            count = sum(1 for line in text.splitlines() if compiled.search(line))
            if count > 0:
                count_matches.append(f"{rel_path}:{count}")
            if len(count_matches) >= limit + offset:
                break
        else:
            for line_no, line in enumerate(text.splitlines(), start=1):
                if compiled.search(line):
                    content_matches.append(f"{rel_path}:{line_no}:{line}")
                    if len(content_matches) >= limit + offset:
                        break
            if len(content_matches) >= limit + offset:
                break

    if output_mode == "files_with_matches":
        if not file_matches:
            return "(no matches)"
        return "\n".join(_apply_pagination(file_matches, head_limit, offset))

    if output_mode == "count":
        if not count_matches:
            return "(no matches)"
        return "\n".join(_apply_pagination(count_matches, head_limit, offset))

    if not content_matches:
        return "(no matches)"
    return "\n".join(_apply_pagination(content_matches, head_limit, offset))
