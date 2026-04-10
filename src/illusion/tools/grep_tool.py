"""
内容搜索工具模块
================

本模块提供基于正则表达式的文本文件搜索功能，带有纯Python后备方案。

主要功能：
    - 强大的搜索工具，基于ripgrep
    - 支持完整正则表达式语法
    - 支持文件过滤（glob和type参数）
    - 支持多种输出模式（content、files_with_matches、count）
    - 支持多行匹配
    - 提供纯Python后备方案

类说明：
    - GrepToolInput: Grep工具输入参数
    - GrepTool: Grep工具类

函数说明：
    - _display_base: 计算显示基础路径
    - _format_path: 格式化路径
    - _resolve_path: 解析路径
    - _apply_pagination: 应用分页
    - _rg_search: ripgrep搜索
    - _python_grep_file: 纯Python单文件搜索
    - _python_grep_dir: 纯Python目录搜索

使用示例：
    >>> # 搜索包含 "function" 的Python文件
    >>> pattern = "def.*function"
    >>> type = "py"
"""

from __future__ import annotations

import asyncio
import re
import shutil
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class GrepToolInput(BaseModel):
    """Grep工具的参数模型
    
    Attributes:
        pattern: 要搜索的正则表达式
        path: 要搜索的文件或目录
        glob: 文件过滤glob（如 "*.js", "**/*.tsx"）
        output_mode: 输出模式：content显示匹配行，files_with_matches只显示文件路径（默认），count显示匹配计数
        context_before: 匹配前的行数
        context_after: 匹配后的行数
        context: 匹配周围的行数（覆盖-B/-A）
        case_sensitive: 是否区分大小写
        type: rg --type 过滤器（如 "js", "py", "rust"）
        multiline: 启用多行匹配（rg -U --multiline-dotall）
        head_limit: 最大结果数（0=无限制）
        offset: 跳过前N个结果
    """

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
    """搜索文本文件的正则表达式模式
    
    使用说明：
    - 始终使用Grep进行搜索任务。永远不要调用Bash命令中的grep或rg。Grep工具已针对正确的权限和访问进行优化
    - 支持完整正则表达式语法（如 "log.*Error", "function\\s+\\w+"）
    - 使用glob参数过滤文件（如 "*.js", "**/*.tsx"）或type参数（如 "js", "py", "rust"）
    - 输出模式："content"显示匹配行，"files_with_matches"只显示文件路径（默认），"count"显示匹配计数
    - 对于需要多轮搜索的开放性搜索使用Agent工具
    - 模式语法：使用ripgrep（不是grep）- 字面大括号需要转义（使用 `interface\\{\\}` 在Go代码中查找 `interface{}`）
    - 多行匹配：默认模式仅在单行内匹配。对于跨行模式如 `struct \\{[\\s\\S]*?field`，使用 `multiline: true`
    """

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
        """返回工具是否为只读操作
        
        Args:
            arguments: 工具输入参数
        
        Returns:
            bool: 始终返回True，grep是只读操作
        """
        del arguments
        return True

    async def execute(self, arguments: GrepToolInput, context: ToolExecutionContext) -> ToolResult:
        """执行grep搜索
        
        Args:
            arguments: 工具输入参数
            context: 工具执行上下文
        
        Returns:
            ToolResult: 搜索结果
        """
        # 解析搜索根目录
        root = _resolve_path(context.cwd, arguments.path) if arguments.path else context.cwd

        # 检查路径是否存在
        if not root.exists():
            return ToolResult(output=f"Path does not exist: {root}", is_error=True)

        # 对于ripgrep：根据output_mode构建参数
        if root.is_file():
            # 单文件搜索
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

            # 单文件的Python后备
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

        # 目录搜索
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

        # 目录的Python后备
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
    """计算显示基础路径
    
    Args:
        path: 目标路径
        cwd: 当前工作目录
    
    Returns:
        Path: 显示基础路径
    """
    try:
        path.relative_to(cwd)
    except ValueError:
        return path.parent
    return cwd


def _format_path(path: Path, display_base: Path) -> str:
    """格式化路径为相对路径
    
    Args:
        path: 完整路径
        display_base: 显示基础路径
    
    Returns:
        str: 相对路径字符串
    """
    try:
        return str(path.relative_to(display_base))
    except ValueError:
        return str(path)


def _resolve_path(base: Path, candidate: str | None) -> Path:
    """解析相对路径为绝对路径
    
    Args:
        base: 基础路径
        candidate: 候选路径字符串
    
    Returns:
        Path: 解析后的绝对路径
    """
    path = Path(candidate or ".").expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def _apply_pagination(lines: list[str], head_limit: int, offset: int) -> list[str]:
    """应用偏移和限制到结果列表
    
    Args:
        lines: 原始行列表
        head_limit: 限制数量
        offset: 偏移量
    
    Returns:
        list[str]: 分页后的行列表
    """
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
    """统一的ripgrep搜索（文件和目录）
    
    返回格式化的输出字符串，如果rg不可用则返回None。
    
    Args:
        path: 搜索路径
        pattern: 正则表达式模式
        output_mode: 输出模式
        glob: 文件过滤glob
        case_sensitive: 是否区分大小写
        context_before: 上下文前几行
        context_after: 上下文后几行
        type_filter: 类型过滤器
        multiline: 是否多行
        head_limit: 结果限制
        offset: 偏移量
        cwd: 当前工作目录
    
    Returns:
        str | None: 格式化输出或None
    """
    rg = shutil.which("rg")
    if not rg:
        return None

    is_dir = path.is_dir()
    # 判断是否包含隐藏文件
    include_hidden = is_dir and ((path / ".git").exists() or (path / ".gitignore").exists())

    cmd: list[str] = [rg, "--color", "never"]

    # 输出模式标志
    if output_mode == "files_with_matches":
        cmd.append("-l")  # 只显示文件路径
    elif output_mode == "count":
        cmd.append("-c")  # 计数模式
    else:
        # content模式 - 显示行号和可选上下文
        cmd.extend(["--no-heading", "--line-number"])

    if include_hidden:
        cmd.append("--hidden")

    # VCS目录排除
    for vcs_dir in (".git", ".svn", ".hg", ".bzr"):
        cmd.extend(["--glob", f"!{vcs_dir}"])

    if not case_sensitive:
        cmd.append("-i")

    # 上下文行（仅在content模式）
    if output_mode == "content":
        if context_before is not None:
            cmd.extend(["-B", str(context_before)])
        if context_after is not None:
            cmd.extend(["-A", str(context_after)])

    # 多行模式
    if multiline:
        cmd.extend(["-U", "--multiline-dotall"])

    # 类型过滤器
    if type_filter:
        cmd.extend(["--type", type_filter])

    # Glob过滤器 - 处理空格分隔的模式和大括号扩展
    if glob:
        # 保持大括号模式如 *.{ts,tsx} 完整
        parts = glob.split()
        for part in parts:
            cmd.extend(["--glob", part])

    # 最大列数防止base64/压缩内容淹没输出
    cmd.extend(["--max-columns", "500"])

    # 模式 - 如果模式以-开头使用-e
    if pattern.startswith("-"):
        cmd.extend(["-e", pattern])
    else:
        cmd.append(pattern)

    # 搜索路径
    if is_dir:
        cmd.append(".")
    else:
        cmd.append(str(path))

    # 执行异步子进程
    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(path) if is_dir else str(path.parent),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    raw_lines: list[str] = []
    limit = head_limit if head_limit > 0 else 10000  # 无限制的安全上限
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

    # rg 在找到匹配时退出0，未找到时退出1
    if process.returncode not in {0, 1}:
        return None

    if not raw_lines:
        return "(no matches)"

    # 应用分页
    paged = _apply_pagination(raw_lines, head_limit, offset)

    # 根据模式格式化输出
    if output_mode == "files_with_matches":
        # 转换为相对路径
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

    # content模式 - 转换路径为相对路径
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
    """纯Python单文件grep后备方案
    
    Args:
        path: 文件路径
        pattern: 正则表达式模式
        output_mode: 输出模式
        case_sensitive: 是否区分大小写
        head_limit: 结果限制
        offset: 偏移量
        display_base: 显示基础路径
    
    Returns:
        str: 格式化输出
    """
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

    # content模式
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
    """纯Python目录grep后备方案
    
    Args:
        root: 根目录
        pattern: 正则表达式模式
        glob: 文件过滤glob
        output_mode: 输出模式
        case_sensitive: 是否区分大小写
        head_limit: 结果限制
        offset: 偏移量
        display_base: 显示基础路径
    
    Returns:
        str: 格式化输出
    """
    flags = 0 if case_sensitive else re.IGNORECASE
    compiled = re.compile(pattern, flags)
    limit = head_limit if head_limit > 0 else 10000

    file_matches: list[str] = []  # files_with_matches模式
    content_matches: list[str] = []  # content/count模式
    count_matches: list[str] = []  # count模式

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
