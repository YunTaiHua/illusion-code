"""
PowerShell 命令执行工具
======================

本模块提供执行 PowerShell 命令并捕获标准输出/错误的功能。

主要组件：
    - PowerShellTool: 执行 PowerShell 命令的工具

使用示例：
    >>> from illusion.tools import PowerShellTool
    >>> tool = PowerShellTool()
"""

from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult
from illusion.tools.shell_common import CommandExecutor


# PowerShell 版本类型
PowerShellEdition = Literal["core", "desktop"]


# ---------------------------------------------------------------------------
# PowerShell 检测
# ---------------------------------------------------------------------------

def _find_powershell() -> str | None:
    """在系统上查找 PowerShell。优先 pwsh (Core 7+) 而非 powershell (5.1)。"""
    pwsh = shutil.which("pwsh")
    if pwsh:
        return pwsh
    ps = shutil.which("powershell")
    if ps:
        return ps
    return None


def _get_powershell_edition(powershell_path: str | None) -> PowerShellEdition | None:
    """根据可执行文件名确定 PowerShell 版本。

    'pwsh' → Core (7+), 'powershell' → Desktop (5.1)。
    """
    if not powershell_path:
        return None
    base = powershell_path.replace("/", "\\").split("\\")[-1].lower()
    base = base.replace(".exe", "")
    if base == "pwsh":
        return "core"
    return "desktop"


# ---------------------------------------------------------------------------
# 提示词生成
# ---------------------------------------------------------------------------

_DEFAULT_TIMEOUT_MS = 120_000  # 默认超时 2 分钟
_MAX_TIMEOUT_MS = 600_000      # 最大超时 10 分钟
_MAX_OUTPUT_LENGTH = 30_000    # 最大输出长度


def _get_background_usage_note() -> str | None:
    if os.environ.get("ILLUSION_DISABLE_BACKGROUND_TASKS", "").lower() in ("1", "true"):
        return None
    return (
        "  - You can use the `run_in_background` parameter to run the command in the background. "
        "Only use this if you don't need the result immediately and are OK being notified when "
        "the command completes later. You do not need to check the output right away - you'll be "
        "notified when it finishes."
    )


def _get_sleep_guidance() -> str | None:
    if os.environ.get("ILLUSION_DISABLE_BACKGROUND_TASKS", "").lower() in ("1", "true"):
        return None
    return (
        "  - Avoid unnecessary `Start-Sleep` commands:\n"
        "    - Do not sleep between commands that can run immediately — just run them.\n"
        "    - If your command is long running and you would like to be notified when it "
        "finishes — simply run your command using `run_in_background`. There is no need to "
        "sleep in this case.\n"
        "    - Do not retry failing commands in a sleep loop — diagnose the root cause or "
        "consider an alternative approach.\n"
        "    - If waiting for a background task you started with `run_in_background`, you will "
        "be notified when it completes — do not poll.\n"
        "    - If you must poll an external process, use a check command rather than sleeping first.\n"
        "    - If you must sleep, keep the duration short (1-5 seconds) to avoid blocking the user."
    )


def _get_edition_section(edition: PowerShellEdition | None) -> str:
    """Version-specific syntax guidance.

    The model's training data covers both editions but it can't tell which one
    it's targeting, so it either emits pwsh-7 syntax on 5.1 (parser error → exit 1)
    or needlessly avoids && on 7.
    """
    if edition == "desktop":
        return (
            "PowerShell edition: Windows PowerShell 5.1 (powershell.exe)\n"
            "   - Pipeline chain operators `&&` and `||` are NOT available — they cause a parser "
            "error. To run B only if A succeeds: `A; if ($?) { B }`. To chain unconditionally: `A; B`.\n"
            "   - Ternary (`?:`), null-coalescing (`??`), and null-conditional (`?.`) operators are "
            "NOT available. Use `if/else` and explicit `$null -eq` checks instead.\n"
            "   - Avoid `2>&1` on native executables. In 5.1, redirecting a native command's stderr "
            "inside PowerShell wraps each line in an ErrorRecord (NativeCommandError) and sets `$?` to "
            "`$false` even when the exe returned exit code 0. stderr is already captured for you — "
            "don't redirect it.\n"
            "   - Default file encoding is UTF-16 LE (with BOM). When writing files other tools will "
            "read, pass `-Encoding utf8` to `Out-File`/`Set-Content`.\n"
            "   - `ConvertFrom-Json` returns a PSCustomObject, not a hashtable. `-AsHashtable` is not available."
        )
    if edition == "core":
        return (
            "PowerShell edition: PowerShell 7+ (pwsh)\n"
            "   - Pipeline chain operators `&&` and `||` ARE available and work like bash. Prefer "
            "`cmd1 && cmd2` over `cmd1; cmd2` when cmd2 should only run if cmd1 succeeds.\n"
            "   - Ternary (`$cond ? $a : $b`), null-coalescing (`??`), and null-conditional (`?.`) "
            "operators are available.\n"
            "   - Default file encoding is UTF-8 without BOM."
        )
    # Detection not yet resolved or PS not installed — give conservative 5.1-safe guidance.
    return (
        "PowerShell edition: unknown — assume Windows PowerShell 5.1 for compatibility\n"
        "   - Do NOT use `&&`, `||`, ternary `?:`, null-coalescing `??`, or null-conditional `?:`. "
        "These are PowerShell 7+ only and parser-error on 5.1.\n"
        "   - To chain commands conditionally: `A; if ($?) { B }`. Unconditionally: `A; B`."
    )


def _build_powershell_description() -> str:
    ps_path = _find_powershell()
    edition = _get_powershell_edition(ps_path)
    background_note = _get_background_usage_note()
    sleep_guidance = _get_sleep_guidance()

    sections = [
        "Executes a given PowerShell command with optional timeout. Working directory persists "
        "between commands; shell state (variables, functions) does not.",
        "",
        "IMPORTANT: This tool is for terminal operations via PowerShell: git, npm, docker, and PS "
        "cmdlets. DO NOT use it for file operations (reading, writing, editing, searching, finding files) "
        "- use the specialized tools for this instead.",
        "",
        _get_edition_section(edition),
        "",
        "Before executing the command, please follow these steps:",
        "",
        "1. Directory Verification:",
        "   - If the command will create new directories or files, first use `Get-ChildItem` (or `ls`) "
        "to verify the parent directory exists and is the correct location",
        "",
        "2. Command Execution:",
        "   - Always quote file paths that contain spaces with double quotes",
        "   - Capture the output of the command.",
        "",
        "PowerShell Syntax Notes:",
        '   - Variables use $ prefix: $myVar = "value"',
        "   - Escape character is backtick (`), not backslash",
        "   - Use Verb-Noun cmdlet naming: Get-ChildItem, Set-Location, New-Item, Remove-Item",
        "   - Common aliases: ls (Get-ChildItem), cd (Set-Location), cat (Get-Content), rm (Remove-Item)",
        "   - Pipe operator | works similarly to bash but passes objects, not text",
        "   - Use Select-Object, Where-Object, ForEach-Object for filtering and transformation",
        '   - String interpolation: "Hello $name" or "Hello $($obj.Property)"',
        "   - Registry access uses PSDrive prefixes: `HKLM:\\SOFTWARE\\...`, `HKCU:\\...` — NOT raw "
        "`HKEY_LOCAL_MACHINE\\...`",
        '   - Environment variables: read with `$env:NAME`, set with `$env:NAME = "value"` '
        "(NOT `Set-Variable` or bash `export`)",
        '   - Call native exe with spaces in path via call operator: `& "C:\\Program Files\\App\\app.exe" arg1 arg2`',
        "",
        "Interactive and blocking commands (will hang — this tool runs with -NonInteractive):",
        "   - NEVER use `Read-Host`, `Get-Credential`, `Out-GridView`, `$Host.UI.PromptForChoice`, or `pause`",
        "   - Destructive cmdlets (`Remove-Item`, `Stop-Process`, `Clear-Content`, etc.) may prompt for "
        "confirmation. Add `-Confirm:$false` when you intend the action to proceed. Use `-Force` for "
        "read-only/hidden items.",
        "   - Never use `git rebase -i`, `git add -i`, or other commands that open an interactive editor",
        "",
        "Passing multiline strings (commit messages, file content) to native executables:",
        "   - Use a single-quoted here-string so PowerShell does not expand `$` or backticks inside. "
        "The closing `'@` MUST be at column 0 (no leading whitespace) on its own line — indenting it "
        "is a parse error:",
        "<example>",
        "git commit -m @'",
        "Commit message here.",
        "Second line with $literal dollar signs.",
        "'@",
        "</example>",
        "   - Use `@'...'@` (single-quoted, literal) not `@\"...\"@` (double-quoted, interpolated) "
        "unless you need variable expansion",
        "   - For arguments containing `-`, `@`, or other characters PowerShell parses as operators, "
        "use the stop-parsing token: `git log --% --format=%H`",
        "",
        "Usage notes:",
        "  - The command argument is required.",
        f"  - You can specify an optional timeout in milliseconds (up to {_MAX_TIMEOUT_MS}ms / "
        f"{_MAX_TIMEOUT_MS // 60000} minutes). If not specified, commands will timeout after "
        f"{_DEFAULT_TIMEOUT_MS}ms ({_DEFAULT_TIMEOUT_MS // 60000} minutes).",
        "  - It is very helpful if you write a clear, concise description of what this command does.",
        f"  - If the output exceeds {_MAX_OUTPUT_LENGTH} characters, output will be truncated before "
        "being returned to you.",
    ]

    if background_note is not None:
        sections.append(background_note)

    sections.extend([
        "  - Avoid using PowerShell to run commands that have dedicated tools, unless explicitly instructed:",
        "    - File search: Use Glob (NOT Get-ChildItem -Recurse)",
        "    - Content search: Use Grep (NOT Select-String)",
        "    - Read files: Use Read (NOT Get-Content)",
        "    - Edit files: Use Edit",
        "    - Write files: Use Write (NOT Set-Content/Out-File)",
        "    - Communication: Output text directly (NOT Write-Output/Write-Host)",
        "  - When issuing multiple commands:",
        "    - If the commands are independent and can run in parallel, make multiple PowerShell tool "
        "calls in a single message.",
        "    - If the commands depend on each other and must run sequentially, chain them in a single "
        "PowerShell call (see edition-specific chaining syntax above).",
        "    - Use `;` only when you need to run commands sequentially but don't care if earlier commands fail.",
        "    - DO NOT use newlines to separate commands (newlines are ok in quoted strings and here-strings)",
        "  - Do NOT prefix commands with `cd` or `Set-Location` -- the working directory is already set "
        "to the correct project directory automatically.",
    ])

    if sleep_guidance is not None:
        sections.append(sleep_guidance)

    sections.extend([
        "  - For git commands:",
        "    - Prefer to create a new commit rather than amending an existing commit.",
        "    - Before running destructive operations (e.g., git reset --hard, git push --force, "
        "git checkout --), consider whether there is a safer alternative that achieves the same goal. "
        "Only use destructive operations when they are truly the best approach.",
        "    - Never skip hooks (--no-verify) or bypass signing (--no-gpg-sign, -c commit.gpgsign=false) "
        "unless the user has explicitly asked for it. If a hook fails, investigate and fix the underlying issue.",
    ])

    return "\n".join(sections)


class PowerShellToolInput(BaseModel):
    """Arguments for the powershell tool."""

    command: str = Field(description="PowerShell command to execute")
    cwd: str | None = Field(default=None, description="Working directory override")
    timeout_seconds: int = Field(default=120, ge=1, le=600)


class PowerShellTool(BaseTool):
    """执行 PowerShell 命令并捕获标准输出/错误。

    用于在 Windows 平台上执行 PowerShell 命令。
    """

    name = "powershell"
    description = _build_powershell_description()
    input_model = PowerShellToolInput

    async def execute(self, arguments: PowerShellToolInput, context: ToolExecutionContext) -> ToolResult:
        # 查找 PowerShell
        powershell = _find_powershell()
        if powershell is None:
            return ToolResult(output="PowerShell is not available on this machine", is_error=True)

        # 解析工作目录
        cwd = Path(arguments.cwd).expanduser() if arguments.cwd else context.cwd

        # 确定版本特定的标志
        edition = _get_powershell_edition(powershell)
        if edition == "core":
            # pwsh 7+ 支持 -NoProfile -NonInteractive -Command
            args = ["-NoProfile", "-NonInteractive", "-Command", arguments.command]
        else:
            # Windows PowerShell 5.1 使用 -NoLogo -NoProfile -Command
            args = ["-NoLogo", "-NoProfile", "-Command", arguments.command]

        # 创建子进程
        process = await asyncio.create_subprocess_exec(
            powershell,
            *args,
            cwd=str(cwd.resolve()),
            stdin=asyncio.subprocess.DEVNULL,  # 防止 Windows 上的句柄继承死锁
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # 执行命令并归一化结果
        result = await CommandExecutor.run_and_normalize(
            process,
            timeout=arguments.timeout_seconds,
        )
        return ToolResult(
            output=result.output,
            is_error=result.is_error,
            metadata=dict(result.metadata),
        )
