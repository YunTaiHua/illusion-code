"""
Bash 命令执行工具
================

本模块提供执行 shell 命令并捕获标准输出/错误的功能。

主要组件：
    - BashTool: 执行 bash 命令的工具

使用示例：
    >>> from illusion.tools import BashTool
    >>> tool = BashTool()
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from pydantic import BaseModel, Field

from illusion.platforms import get_platform
from illusion.sandbox import SandboxUnavailableError
from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult
from illusion.tools.shell_common import CommandExecutor
from illusion.utils.shell import _resolve_windows_bash, create_shell_subprocess


class BashToolInput(BaseModel):
    """Bash 工具参数。

    属性：
        command: 要执行的 shell 命令
        cwd: 可选的工作目录覆盖
        timeout_seconds: 超时秒数（1-600）
    """

    command: str = Field(description="Shell command to execute")
    cwd: str | None = Field(default=None, description="Working directory override")
    timeout_seconds: int = Field(default=120, ge=1, le=600)


# ---------------------------------------------------------------------------
# 提示词生成（从 claude-code-sourcemap BashTool/prompt.ts 移植）
# ---------------------------------------------------------------------------

_DEFAULT_TIMEOUT_MS = 120_000  # 默认超时 2 分钟
_MAX_TIMEOUT_MS = 600_000      # 最大超时 10 分钟
_MAX_OUTPUT_LENGTH = 30_000    # 最大输出长度


def _get_background_usage_note() -> str | None:
    if os.environ.get("ILLUSION_DISABLE_BACKGROUND_TASKS", "").lower() in ("1", "true"):
        return None
    return (
        "You can use the `run_in_background` parameter to run the command in the background. "
        "Only use this if you don't need the result immediately and are OK being notified when "
        "the command completes later. You do not need to check the output right away - you'll be "
        "notified when it finishes. You do not need to use '&' at the end of the command when "
        "using this parameter."
    )


def _get_sleep_guidance() -> str | None:
    if os.environ.get("ILLUSION_DISABLE_BACKGROUND_TASKS", "").lower() in ("1", "true"):
        return None
    return (
        "  - Avoid unnecessary `sleep` commands:\n"
        "    - Do not sleep between commands that can run immediately — just run them.\n"
        "    - If your command is long running and you would like to be notified when it finishes — "
        "use `run_in_background`. No sleep needed.\n"
        "    - Do not retry failing commands in a sleep loop — diagnose the root cause.\n"
        "    - If waiting for a background task you started with `run_in_background`, you will be "
        "notified when it completes — do not poll.\n"
        "    - If you must poll an external process, use a check command (e.g. `gh run view`) "
        "rather than sleeping first.\n"
        "    - If you must sleep, keep the duration short (1-5 seconds) to avoid blocking the user."
    )


def _get_sandbox_section() -> str:
    """Generate sandbox section for the prompt (simplified without live sandbox config)."""
    return """\
## Command sandbox

By default, your command will be run in a sandbox. This sandbox controls which directories and network hosts commands may access or modify without an explicit override.

The sandbox has the following restrictions:
Filesystem: {...}
Network: {...}

 - You should always default to running commands within the sandbox. Do NOT attempt to set `dangerouslyDisableSandbox: true` unless:
   - The user *explicitly* asks you to bypass sandbox
   - A specific command just failed and you see evidence of sandbox restrictions causing the failure.
 - Evidence of sandbox-caused failures includes:
   - "Operation not permitted" errors for file/network operations
   - Access denied to specific paths outside allowed directories
   - Network connection failures to non-whitelisted hosts
   - Unix socket connection errors
 - When you see evidence of sandbox-caused failure:
   - Immediately retry with `dangerouslyDisableSandbox: true` (don't ask, just do it)
   - Briefly explain what sandbox restriction likely caused the failure.
   - This will prompt the user for permission
 - Treat each command you execute with `dangerouslyDisableSandbox: true` individually.
 - Do not suggest adding sensitive paths like ~/.bashrc, ~/.zshrc, ~/.ssh/*, or credential files to the sandbox allowlist.
 - For temporary files, always use the `$TMPDIR` environment variable. TMPDIR is automatically set to the correct sandbox-writable directory in sandbox mode. Do NOT use `/tmp` directly - use `$TMPDIR` instead."""


def _get_commit_and_pr_instructions() -> str:
    return """\
# Committing changes with git

Only create commits when requested by the user. If unclear, ask first. When the user asks you to create a new git commit, follow these steps carefully:

You can call multiple tools in a single response. When multiple independent pieces of information are requested and all commands are likely to succeed, run multiple tool calls in parallel for optimal performance. The numbered steps below indicate which commands should be batched in parallel.

Git Safety Protocol:
- NEVER update the git config
- NEVER run destructive git commands (push --force, reset --hard, checkout ., restore ., clean -f, branch -D) unless the user explicitly requests these actions. Taking unauthorized destructive actions is unhelpful and can result in lost work, so it's best to ONLY run these commands when given direct instructions
- NEVER skip hooks (--no-verify, --no-gpg-sign, etc) unless the user explicitly requests it
- NEVER run force push to main/master, warn the user if they request it
- CRITICAL: Always create NEW commits rather than amending, unless the user explicitly requests a git amend. When a pre-commit hook fails, the commit did NOT happen — so --amend would modify the PREVIOUS commit, which may result in destroying work or losing previous changes. Instead, after hook failure, fix the issue, re-stage, and create a NEW commit
- When staging files, prefer adding specific files by name rather than using "git add -A" or "git add .", which can accidentally include sensitive files (.env, credentials) or large binaries
- NEVER commit changes unless the user explicitly asks you to. It is VERY IMPORTANT to only commit when explicitly asked, otherwise the user will feel that you are being too proactive

1. Run the following bash commands in parallel, each using the Bash tool:
  - Run a git status command to see all untracked files. IMPORTANT: Never use the -uall flag as it can cause memory issues on large repos.
  - Run a git diff command to see both staged and unstaged changes that will be committed.
  - Run a git log command to see recent commit messages, so that you can follow this repository's commit message style.
2. Analyze all staged changes (both previously staged and newly added) and draft a commit message:
  - Summarize the nature of the changes (eg. new feature, enhancement to an existing feature, bug fix, refactoring, test, docs, etc.). Ensure the message accurately reflects the changes and their purpose (i.e. "add" means a wholly new feature, "update" means an enhancement to an existing feature, "fix" means a bug fix, etc.).
  - Do not commit files that likely contain secrets (.env, credentials.json, etc). Warn the user if they specifically request to commit those files
  - Draft a concise (1-2 sentences) commit message that focuses on the "why" rather than the "what"
  - Ensure it accurately reflects the changes and their purpose
3. Run the following commands in parallel:
   - Add relevant untracked files to the staging area.
   - Create the commit with a message ending with:

   Co-Authored-By: Illusion <noreply@illusion.dev>
   - Run git status after the commit completes to verify success.
   Note: git status depends on the commit completing, so run it sequentially after the commit.
4. If the commit fails due to pre-commit hook: fix the issue and create a NEW commit

Important notes:
- NEVER run additional commands to read or explore code, besides git bash commands
- NEVER use the TodoWrite or Agent tools
- DO NOT push to the remote repository unless the user explicitly asks you to do so
- IMPORTANT: Never use git commands with the -i flag (like git rebase -i or git add -i) since they require interactive input which is not supported.
- IMPORTANT: Do not use --no-edit with git rebase commands, as the --no-edit flag is not a valid option for git rebase.
- If there are no changes to commit (i.e., no untracked files and no modifications), do not create an empty commit
- In order to ensure good formatting, ALWAYS pass the commit message via a HEREDOC, a la this example:
<example>
git commit -m "$(cat <<'EOF'
   Commit message here.

   Co-Authored-By: Illusion <noreply@illusion.dev>
   EOF
   )"
</example>

# Creating pull requests
Use the gh command via the Bash tool for ALL GitHub-related tasks including working with issues, pull requests, checks, and releases. If given a Github URL use the gh command to get the information needed.

IMPORTANT: When the user asks you to create a pull request, follow these steps carefully:

1. Run the following bash commands in parallel using the Bash tool, in order to understand the current state of the branch since it diverged from the main branch:
   - Run a git status command to see all untracked files (never use -uall flag)
   - Run a git diff command to see both staged and unstaged changes that will be committed
   - Check if the current branch tracks a remote branch and is up to date with the remote, so you know if you need to push to the remote
   - Run a git log command and `git diff [base-branch]...HEAD` to understand the full commit history for the current branch (from the time it diverged from the base branch)
2. Analyze all changes that will be included in the pull request, making sure to look at all relevant commits (NOT just the latest commit, but ALL commits that will be included in the pull request!!!), and draft a pull request title and summary:
   - Keep the PR title short (under 70 characters)
   - Use the description/body for details, not the title
3. Run the following commands in parallel:
   - Create new branch if needed
   - Push to remote with -u flag if needed
   - Create PR using gh pr create with the format below. Use a HEREDOC to pass the body to ensure correct formatting.
<example>
gh pr create --title "the pr title" --body "$(cat <<'EOF'
## Summary
<1-3 bullet points>

## Test plan
[Bulleted markdown checklist of TODOs for testing the pull request...]

🤖 Generated with [Illusion Code]
EOF
)"
</example>

Important:
- DO NOT use the TodoWrite or Agent tools
- Return the PR URL when you're done, so the user can see it

# Other common operations
- View comments on a Github PR: gh api repos/foo/bar/pulls/123/comments"""


def _build_bash_description() -> str:
    background_note = _get_background_usage_note()

    tool_preference_items = [
        "File search: Use Glob (NOT find or ls)",
        "Content search: Use Grep (NOT grep or rg)",
        "Read files: Use Read (NOT cat/head/tail)",
        "Edit files: Use Edit (NOT sed/awk)",
        "Write files: Use Write (NOT echo >/cat <<EOF)",
        "Communication: Output text directly (NOT echo/printf)",
    ]

    avoid_commands = "`find`, `grep`, `cat`, `head`, `tail`, `sed`, `awk`, or `echo`"

    multiple_commands_subitems = (
        'If the commands are independent and can run in parallel, make multiple Bash tool calls in a single message. '
        'Example: if you need to run "git status" and "git diff", send a single message with two Bash tool calls in parallel.\n'
        "If the commands depend on each other and must run sequentially, use a single Bash call with '&&' to chain them together.\n"
        "Use ';' only when you need to run commands sequentially but don't care if earlier commands fail.\n"
        "DO NOT use newlines to separate commands (newlines are ok in quoted strings)."
    )

    git_subitems = (
        "Prefer to create a new commit rather than amending an existing commit.\n"
        "Before running destructive operations (e.g., git reset --hard, git push --force, git checkout --), "
        "consider whether there is a safer alternative that achieves the same goal. Only use destructive operations "
        "when they are truly the best approach.\n"
        "Never skip hooks (--no-verify) or bypass signing (--no-gpg-sign, -c commit.gpgsign=false) unless the "
        "user has explicitly asked for it. If a hook fails, investigate and fix the underlying issue."
    )

    sleep_subitems = (
        "Do not sleep between commands that can run immediately — just run them.\n"
        "If your command is long running and you would like to be notified when it finishes — "
        "use `run_in_background`. No sleep needed.\n"
        "Do not retry failing commands in a sleep loop — diagnose the root cause.\n"
        "If waiting for a background task you started with `run_in_background`, you will be notified "
        "when it completes — do not poll.\n"
        "If you must poll an external process, use a check command (e.g. `gh run view`) rather than "
        "sleeping first.\n"
        "If you must sleep, keep the duration short (1-5 seconds) to avoid blocking the user."
    )

    instruction_items = [
        "If your command will create new directories or files, first use this tool to run `ls` to verify the parent directory exists and is the correct location.",
        'Always quote file paths that contain spaces with double quotes in your command (e.g., cd "path with spaces/file.txt")',
        "Try to maintain your current working directory throughout the session by using absolute paths and avoiding usage of `cd`. You may use `cd` if the User explicitly requests it.",
        f"You may specify an optional timeout in milliseconds (up to {_MAX_TIMEOUT_MS}ms / {_MAX_TIMEOUT_MS // 60000} minutes). "
        f"By default, your command will timeout after {_DEFAULT_TIMEOUT_MS}ms ({_DEFAULT_TIMEOUT_MS // 60000} minutes).",
    ]

    if background_note is not None:
        instruction_items.append(background_note)

    instruction_items.extend([
        "When issuing multiple commands:",
        multiple_commands_subitems,
        "For git commands:",
        git_subitems,
        "Avoid unnecessary `sleep` commands:",
        sleep_subitems,
    ])

    # Build tool preference bullets
    preference_bullets = "\n".join(f" - {item}" for item in tool_preference_items)

    # Build instruction bullets
    instruction_lines: list[str] = []
    for item in instruction_items:
        if "\n" in item:
            # Multi-line sub-items get their own indented block
            for line in item.split("\n"):
                instruction_lines.append(f"   - {line}" if not line.startswith(" ") else f" {line}")
        else:
            instruction_lines.append(f" - {item}")

    sections = [
        "Executes a given bash command and returns its output.",
        "",
        "The working directory persists between commands, but shell state does not. "
        "The shell environment is initialized from the user's profile (bash or zsh).",
        "",
        f"IMPORTANT: Avoid using this tool to run {avoid_commands} commands, unless explicitly "
        "instructed or after you have verified that a dedicated tool cannot accomplish your task. "
        "Instead, use the appropriate dedicated tool as this will provide a much better experience for the user:",
        "",
        preference_bullets,
        "While the Bash tool can do similar things, it's better to use the built-in tools as they "
        "provide a better user experience and make it easier to review tool calls and give permission.",
        "",
        "# Instructions",
    ]

    for line in instruction_lines:
        sections.append(line)

    sections.append(_get_sandbox_section())
    sections.append("")
    sections.append(_get_commit_and_pr_instructions())

    return "\n".join(sections)


class BashTool(BaseTool):
    """执行 shell 命令并捕获标准输出/错误。

    用于执行终端操作，如 git、npm、docker 等命令。
    """

    name = "bash"
    description = _build_bash_description()
    input_model = BashToolInput

    async def execute(self, arguments: BashToolInput, context: ToolExecutionContext) -> ToolResult:
        # 检查 Windows 平台上的 bash 可用性
        if get_platform() == "windows":
            bash_path = _resolve_windows_bash()
            if not bash_path:
                return ToolResult(
                    output=(
                        "Bash is not available on this Windows machine. "
                        "Install Git for Windows or set ILLUSION_CODE_GIT_BASH_PATH, "
                        "or use the powershell tool for command execution."
                    ),
                    is_error=True,
                )

        # 解析工作目录
        cwd = Path(arguments.cwd).expanduser() if arguments.cwd else context.cwd
        try:
            # 创建 shell 子进程
            process = await create_shell_subprocess(
                arguments.command,
                cwd=cwd,
                stdin=asyncio.subprocess.DEVNULL,  # 防止 Windows 上的句柄继承死锁
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except SandboxUnavailableError as exc:
            return ToolResult(output=str(exc), is_error=True)

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
