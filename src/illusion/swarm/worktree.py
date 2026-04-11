"""
Git Worktree 隔离模块
====================

本模块提供 swarm 代理的 Git worktree 隔离功能。
使用 Git worktree 实现代理间的文件系统隔离。

主要组件：
    - WorktreeManager: Git worktree 管理器
    - WorktreeInfo: Worktree 元数据
    - validate_worktree_slug: Worktree slug 验证函数

使用示例：
    >>> from illusion.swarm.worktree import WorktreeManager
    >>> 
    >>> manager = WorktreeManager()
    >>> info = await manager.create_worktree(repo_path, "researcher-1", agent_id="agent-1")
    >>> print(f"Worktree created at: {info.path}")
"""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Slug 验证
# ---------------------------------------------------------------------------

# 有效的路径段正则
_VALID_SEGMENT = re.compile(r"^[a-zA-Z0-9._-]+$")
# 最大 slug 长度
_MAX_SLUG_LENGTH = 64
# 常见符号链接目录
_COMMON_SYMLINK_DIRS = ("node_modules", ".venv", "__pycache__", ".tox")


def validate_worktree_slug(slug: str) -> str:
    """清理并验证 worktree slug。

    规则：
    - 最多 64 个字符
    - 每个 '/' 分隔的段必须匹配 [a-zA-Z0-9._-]+
    - 拒绝 '.' 和 '..' 段（路径遍历）
    - 拒绝前导/尾随 '/'

    如果有效则返回 slug 不变，否则引发 ValueError。
    """
    if not slug:
        raise ValueError("Worktree slug must not be empty")

    if len(slug) > _MAX_SLUG_LENGTH:
        raise ValueError(
            f"Worktree slug must be {_MAX_SLUG_LENGTH} characters or fewer (got {len(slug)})"
        )

    # 拒绝绝对路径
    if slug.startswith("/") or slug.startswith("\\"):
        raise ValueError(f"Worktree slug must not be an absolute path: {slug!r}")

    for segment in slug.split("/"):
        if segment in (".", ".."):
            raise ValueError(
                f"Worktree slug {slug!r}: must not contain '.' or '..' path segments"
            )
        if not _VALID_SEGMENT.match(segment):
            raise ValueError(
                f"Worktree slug {slug!r}: each segment must be non-empty and contain only "
                "letters, digits, dots, underscores, and dashes"
            )

    return slug


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class WorktreeInfo:
    """管理的 git worktree 的元数据。"""

    slug: str
    path: Path
    branch: str
    original_path: Path
    created_at: float
    agent_id: str | None = None


# ---------------------------------------------------------------------------
# 内部辅助函数
# ---------------------------------------------------------------------------

def _flatten_slug(slug: str) -> str:
    """用 '+' 替换 '/' 以避免嵌套目录/分支问题。"""
    return slug.replace("/", "+")


def _worktree_branch(slug: str) -> str:
    """生成 worktree 分支名称。"""
    return f"worktree-{_flatten_slug(slug)}"


async def _run_git(*args: str, cwd: Path) -> tuple[int, str, str]:
    """运行 git 命令，返回 (returncode, stdout, stderr)。"""
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    proc = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=str(cwd),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": ""},
        **kwargs,
    )
    stdout_bytes, stderr_bytes = await proc.communicate()
    return (
        proc.returncode or 0,
        stdout_bytes.decode(errors="replace").strip(),
        stderr_bytes.decode(errors="replace").strip(),
    )


async def _symlink_common_dirs(repo_path: Path, worktree_path: Path) -> None:
    """从主仓库符号链接大型公共目录以避免重复。"""
    for dir_name in _COMMON_SYMLINK_DIRS:
        src = repo_path / dir_name
        dst = worktree_path / dir_name
        if dst.exists() or dst.is_symlink():
            continue
        if not src.exists():
            continue
        try:
            dst.symlink_to(src)
        except OSError:
            pass  # 非致命：磁盘满、不支持的文件系统等


async def _remove_symlinks(worktree_path: Path) -> None:
    """移除由 _symlink_common_dirs 创建的符号链接。"""
    for dir_name in _COMMON_SYMLINK_DIRS:
        dst = worktree_path / dir_name
        if dst.is_symlink():
            try:
                dst.unlink()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# WorktreeManager
# ---------------------------------------------------------------------------

class WorktreeManager:
    """管理隔离代理执行的 git worktree。

    Worktree 存储在 ``base_dir/<slug>/`` 下（'/' 替换为 '+' 以保持布局扁平）。
    JSON 元数据文件跟踪活跃 worktree 及其关联的代理 ID，以便可以清理过期的 worktree。
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        """初始化 WorktreeManager。"""
        self.base_dir: Path = base_dir or Path.home() / ".illusion" / "worktrees"

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    async def create_worktree(
        self,
        repo_path: Path,
        slug: str,
        branch: str | None = None,
        agent_id: str | None = None,
    ) -> WorktreeInfo:
        """为 *slug* 创建（或恢复）git worktree。

        如果 worktree 目录已存在且是有效的 git worktree，
        则在不重新运行 ``git worktree add`` 的情况下恢复。

        Args:
            repo_path: 主仓库的绝对路径。
            slug: 人类可读标识符（通过 validate_worktree_slug 验证）。
            branch: 要检出的分支名称；默认为生成的 ``worktree-<slug>`` 名称。
            agent_id: 拥有此 worktree 的代理的可选标识符。

        Returns:
            描述 worktree 的 WorktreeInfo。
        """
        # 验证 slug
        validate_worktree_slug(slug)
        repo_path = repo_path.resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # 扁平化 slug 并构建路径
        flat_slug = _flatten_slug(slug)
        worktree_path = self.base_dir / flat_slug
        worktree_branch = branch or _worktree_branch(slug)

        # 快速恢复：检查 worktree 是否已注册
        if worktree_path.exists():
            code, _, _ = await _run_git(
                "rev-parse", "--git-dir", cwd=worktree_path
            )
            if code == 0:
                return WorktreeInfo(
                    slug=slug,
                    path=worktree_path,
                    branch=worktree_branch,
                    original_path=repo_path,
                    created_at=worktree_path.stat().st_mtime,
                    agent_id=agent_id,
                )

        # 新 worktree：-B 重置之前移除留下的孤儿分支
        code, _, stderr = await _run_git(
            "worktree", "add", "-B", worktree_branch, str(worktree_path), "HEAD",
            cwd=repo_path,
        )
        if code != 0:
            raise RuntimeError(f"git worktree add failed: {stderr}")

        # 符号链接公共目录
        await _symlink_common_dirs(repo_path, worktree_path)

        return WorktreeInfo(
            slug=slug,
            path=worktree_path,
            branch=worktree_branch,
            original_path=repo_path,
            created_at=time.time(),
            agent_id=agent_id,
        )

    async def remove_worktree(self, slug: str) -> bool:
        """按 slug 移除 worktree。

        首先清理符号链接，然后运行 ``git worktree remove --force``。

        Returns:
            如果 worktree 被移除返回 True；如果不存在则返回 False。
        """
        validate_worktree_slug(slug)
        flat_slug = _flatten_slug(slug)
        worktree_path = self.base_dir / flat_slug

        if not worktree_path.exists():
            return False

        # 在 git 移除目录之前先移除符号链接
        await _remove_symlinks(worktree_path)

        # 从 worktree 的 git 元数据确定仓库根目录
        code, git_common, _ = await _run_git(
            "rev-parse", "--git-common-dir", cwd=worktree_path
        )
        if code == 0 and git_common:
            # git_common 指向主仓库内的 .git
            repo_path = Path(git_common).resolve().parent
            if repo_path.exists():
                await _run_git(
                    "worktree", "remove", "--force", str(worktree_path),
                    cwd=repo_path,
                )
                return True

        # 回退：尝试从任何工作目录通过绝对路径移除
        # 如果 repo_path 检测失败，尝试使用 cwd=base_dir 移除
        code, _, _ = await _run_git(
            "worktree", "remove", "--force", str(worktree_path),
            cwd=self.base_dir,
        )
        return code == 0

    async def list_worktrees(self) -> list[WorktreeInfo]:
        """返回 base_dir 下每个已知 worktree 的 WorktreeInfo。"""
        if not self.base_dir.exists():
            return []

        results: list[WorktreeInfo] = []
        for child in self.base_dir.iterdir():
            if not child.is_dir():
                continue
            code, _, _ = await _run_git("rev-parse", "--git-dir", cwd=child)
            if code != 0:
                continue

            # 从 HEAD 恢复分支名称
            rc, branch_out, _ = await _run_git(
                "rev-parse", "--abbrev-ref", "HEAD", cwd=child
            )
            branch = branch_out if rc == 0 else "unknown"

            # 从 git-common-dir 恢复原始仓库路径
            rc2, common_dir, _ = await _run_git(
                "rev-parse", "--git-common-dir", cwd=child
            )
            if rc2 == 0 and common_dir:
                original_path = Path(common_dir).resolve().parent
            else:
                original_path = child

            # Slug 是目录名（扁平形式）；从 '+' 恢复 '/'
            slug = child.name.replace("+", "/")
            results.append(
                WorktreeInfo(
                    slug=slug,
                    path=child,
                    branch=branch,
                    original_path=original_path,
                    created_at=child.stat().st_mtime,
                )
            )

        return results

    async def cleanup_stale(self, active_agent_ids: set[str] | None = None) -> list[str]:
        """移除没有活跃代理的 worktree。

        Args:
            active_agent_ids: 仍在运行的代理 ID 集合。如果为 None，
                *所有* 有 agent_id 的 worktree 都被视为过期。

        Returns:
            已移除的 slugs 列表。
        """
        worktrees = await self.list_worktrees()
        removed: list[str] = []
        for info in worktrees:
            if info.agent_id is None:
                continue
            if active_agent_ids is not None and info.agent_id in active_agent_ids:
                continue
            ok = await self.remove_worktree(info.slug)
            if ok:
                removed.append(info.slug)
        return removed
