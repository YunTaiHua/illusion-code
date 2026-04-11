"""
进入工作树工具
=============

本模块提供创建和进入 git 工作树的功能，用于隔离开发环境。

主要组件：
    - EnterWorktreeTool: 创建并进入 git 工作树的工具

使用示例：
    >>> from illusion.tools import EnterWorktreeTool
    >>> tool = EnterWorktreeTool()
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class EnterWorktreeToolInput(BaseModel):
    """进入工作树参数。

    属性：
        name: 工作树名称（可选，不提供则生成随机名称）
    """

    name: str | None = Field(
        default=None,
        description="A name for the worktree. If not provided, a random name is generated.",
    )


class EnterWorktreeTool(BaseTool):
    """创建 git 工作树。

    仅在用户明确要求使用工作树时使用。此工具创建隔离的 git 工作树并切换当前会话到其中。
    """

    name = "enter_worktree"
    description = """Use this tool ONLY when the user explicitly asks to work in a worktree. This tool creates an isolated git worktree and switches the current session into it.

## When to Use

- The user explicitly says "worktree" (e.g., "start a worktree", "work in a worktree", "create a worktree", "use a worktree")

## When NOT to Use

- The user asks to create a branch, switch branches, or work on a different branch -- use git commands instead
- The user asks to fix a bug or work on a feature -- use normal git workflow unless they specifically mention worktrees
- Never use this tool unless the user explicitly mentions "worktree"

## Requirements

- Must be in a git repository, OR have WorktreeCreate/WorktreeRemove hooks configured in settings.json
- Must not already be in a worktree

## Behavior

- In a git repository: creates a new git worktree inside `.illusion/worktrees/` with a new branch based on HEAD
- Outside a git repository: delegates to WorktreeCreate/WorktreeRemove hooks for VCS-agnostic isolation
- Switches the session's working directory to the new worktree
- Use ExitWorktree to leave the worktree mid-session (keep or remove). On session exit, if still in the worktree, the user will be prompted to keep or remove it

## Parameters

- `name` (optional): A name for the worktree. If not provided, a random name is generated."""
    input_model = EnterWorktreeToolInput

    async def execute(
        self,
        arguments: EnterWorktreeToolInput,
        context: ToolExecutionContext,
    ) -> ToolResult:
        # 获取 git 仓库根目录
        top_level = _git_output(context.cwd, "rev-parse", "--show-toplevel")
        if top_level is None:
            return ToolResult(output="enter_worktree requires a git repository", is_error=True)

        repo_root = Path(top_level)
        # 生成或使用指定的工作树名称
        name = arguments.name or f"wt-{uuid4().hex[:8]}"
        branch_name = name
        # 解析工作树路径
        worktree_path = _resolve_worktree_path(repo_root, branch_name)
        # 创建父目录
        worktree_path.parent.mkdir(parents=True, exist_ok=True)
        # 执行 git worktree add 命令
        cmd = ["git", "worktree", "add", "-b", branch_name, str(worktree_path), "HEAD"]
        result = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL,
            **({"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}),
        )
        output = (result.stdout or result.stderr).strip() or f"Created worktree {worktree_path}"
        if result.returncode != 0:
            return ToolResult(output=output, is_error=True)
        return ToolResult(output=f"{output}\nPath: {worktree_path}")


def _git_output(cwd: Path, *args: str) -> str | None:
    """执行 git 命令并返回输出。

    参数：
        cwd: 工作目录
        *args: git 命令参数

    返回：
        命令输出字符串，失败返回 None
    """
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        stdin=subprocess.DEVNULL,
        **({"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}),
    )
    if result.returncode != 0:
        return None
    return (result.stdout or "").strip()


def _resolve_worktree_path(repo_root: Path, name: str) -> Path:
    """解析工作树路径。

    参数：
        repo_root: 仓库根目录
        name: 工作树名称

    返回：
        解析后的工作树路径
    """
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "worktree"
    return (repo_root / ".illusion" / "worktrees" / slug).resolve()
