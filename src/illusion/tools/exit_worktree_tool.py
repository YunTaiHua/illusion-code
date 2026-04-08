"""Tool for removing git worktrees."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class ExitWorktreeToolInput(BaseModel):
    """Arguments for worktree removal."""

    action: Literal["keep", "remove"] = Field(
        description='"keep" leaves the worktree directory and branch intact on disk; "remove" deletes both.',
    )
    discard_changes: bool = Field(
        default=False,
        description='Only meaningful with action "remove". If true, force-remove even with uncommitted changes.',
    )


class ExitWorktreeTool(BaseTool):
    """Remove a git worktree."""

    name = "exit_worktree"
    description = """Exit a worktree session created by EnterWorktree and return the session to the original working directory.

## Scope

This tool ONLY operates on worktrees created by EnterWorktree in this session. It will NOT touch:
- Worktrees you created manually with `git worktree add`
- Worktrees from a previous session (even if created by EnterWorktree then)
- The directory you're in if EnterWorktree was never called

If called outside an EnterWorktree session, the tool is a **no-op**: it reports that no worktree session is active and takes no action. Filesystem state is unchanged.

## When to Use

- The user explicitly asks to "exit the worktree", "leave the worktree", "go back", or otherwise end the worktree session
- Do NOT call this proactively — only when the user asks

## Parameters

- `action` (required): `"keep"` or `"remove"`
  - `"keep"` — leave the worktree directory and branch intact on disk. Use this if the user wants to come back to the work later, or if there are changes to preserve.
  - `"remove"` — delete the worktree directory and its branch. Use this for a clean exit when the work is done or abandoned.
- `discard_changes` (optional, default false): only meaningful with `action: "remove"`. If the worktree has uncommitted files or commits not on the original branch, the tool will REFUSE to remove it unless this is set to `true`. If the tool returns an error listing changes, confirm with the user before re-invoking with `discard_changes: true`.

## Behavior

- Restores the session's working directory to where it was before EnterWorktree
- Clears CWD-dependent caches (system prompt sections, memory files, plans directory) so the session state reflects the original directory
- If a tmux session was attached to the worktree: killed on `remove`, left running on `keep` (its name is returned so the user can reattach)
- Once exited, EnterWorktree can be called again to create a fresh worktree"""
    input_model = ExitWorktreeToolInput

    async def execute(
        self,
        arguments: ExitWorktreeToolInput,
        context: ToolExecutionContext,
    ) -> ToolResult:
        # Verify we're in a git repo
        git_check = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=context.cwd,
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL,
        )
        if git_check.returncode != 0:
            return ToolResult(output="Not in a git repository", is_error=True)

        repo_root = Path(git_check.stdout.strip())

        # Find worktree path - look for .illusion/worktrees/
        worktree_base = repo_root / ".illusion" / "worktrees"
        current_cwd = context.cwd.resolve()

        # Check if current CWD is inside a worktree
        if not str(current_cwd).startswith(str(worktree_base)):
            return ToolResult(output="No active worktree session found", is_error=True)

        worktree_path = current_cwd

        if arguments.action == "keep":
            return ToolResult(output=f"Worktree kept at {worktree_path}")

        # Remove action
        # Check for uncommitted changes unless discard_changes is set
        if not arguments.discard_changes:
            status_check = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=worktree_path,
                capture_output=True,
                text=True,
                check=False,
                stdin=subprocess.DEVNULL,
            )
            if status_check.stdout.strip():
                return ToolResult(
                    output=(
                        f"Worktree has uncommitted changes. "
                        f"Set discard_changes=true to force remove.\n"
                        f"Changes:\n{status_check.stdout.strip()[:500]}"
                    ),
                    is_error=True,
                )

        # Remove the worktree
        cmd = ["git", "worktree", "remove"]
        if arguments.discard_changes:
            cmd.append("--force")
        cmd.append(str(worktree_path))

        result = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL,
        )
        output = (result.stdout or result.stderr).strip() or f"Removed worktree {worktree_path}"
        return ToolResult(output=output, is_error=result.returncode != 0)
