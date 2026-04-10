"""
文件系统Glob工具模块
====================

本模块提供基于glob模式的文件搜索功能。

主要功能：
    - 快速的文件模式匹配工具，支持任意大小的代码库
    - 支持glob模式如 "**/*.js" 或 "src/**/*.ts"
    - 返回按修改时间排序的匹配文件路径
    - 使用ripgrep的文件遍历器（可用时），尊重.gitignore并可跳过重目录

类说明：
    - GlobToolInput: Glob工具输入参数
    - GlobTool: Glob工具类

函数说明：
    - _resolve_path: 解析路径
    - _looks_like_git_repo: 判断是否像Git仓库
    - _glob: 异步glob实现

使用示例：
    >>> # 查找所有Python文件
    >>> pattern = "**/*.py"
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from pydantic import BaseModel, Field

from illusion.tools.base import BaseTool, ToolExecutionContext, ToolResult


class GlobToolInput(BaseModel):
    """Glob工具的参数模型
    
    Attributes:
        pattern: 相对于工作目录的glob模式
        root: 可选的搜索根目录
        limit: 返回结果数量限制
    """

    pattern: str = Field(description="Glob pattern relative to the working directory")
    root: str | None = Field(default=None, description="Optional search root")
    limit: int = Field(default=200, ge=1, le=5000)


class GlobTool(BaseTool):
    """列出匹配glob模式的文件
    
    使用说明：
    - 快速的文件模式匹配工具，适用于任何规模的代码库
    - 支持glob模式如 "**/*.js" 或 "src/**/*.ts"
    - 返回按修改时间排序的匹配文件路径
    - 当需要按名称模式查找文件时使用此工具
    - 当进行开放性搜索可能需要多轮glob和grep时，使用Agent工具
    """

    name = "glob"
    description = """- Fast file pattern matching tool that works with any codebase size
- Supports glob patterns like "**/*.js" or "src/**/*.ts"
- Returns matching file paths sorted by modification time
- Use this tool when you need to find files by name patterns
- When you are doing an open ended search that may require multiple rounds of globbing and grepping, use the Agent tool instead"""
    input_model = GlobToolInput

    def is_read_only(self, arguments: GlobToolInput) -> bool:
        """返回工具是否为只读操作
        
        Args:
            arguments: 工具输入参数
        
        Returns:
            bool: 始终返回True，glob是只读操作
        """
        del arguments
        return True

    async def execute(self, arguments: GlobToolInput, context: ToolExecutionContext) -> ToolResult:
        """执行glob搜索
        
        Args:
            arguments: 工具输入参数
            context: 工具执行上下文
        
        Returns:
            ToolResult: 搜索结果
        """
        # 解析根目录路径
        root = _resolve_path(context.cwd, arguments.root) if arguments.root else context.cwd
        # 执行异步glob搜索
        matches = await _glob(root, arguments.pattern, limit=arguments.limit)
        if not matches:
            return ToolResult(output="(no matches)")
        return ToolResult(output="\n".join(matches))


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


def _looks_like_git_repo(path: Path) -> bool:
    """启发式判断：确定搜索时是否应该包含隐藏路径
    
    对于代码库，隐藏目录如 `.github/` 是相关的；
    对于任意目录（如用户主目录），搜索隐藏路径可能会爆炸搜索空间。
    
    Args:
        path: 要检查的路径
    
    Returns:
        bool: 是否像Git仓库
    """
    current = path
    for _ in range(6):
        git_dir = current / ".git"
        if git_dir.exists():
            return True
        if current.parent == current:
            break
        current = current.parent
    return False


async def _glob(root: Path, pattern: str, *, limit: int) -> list[str]:
    """快速glob实现
    
    使用ripgrep的文件遍历器（可用时），尊重.gitignore并可跳过重目录如`.venv/`，
    有Python后备方案。
    
    Args:
        root: 搜索根目录
        pattern: glob模式
        limit: 结果数量限制
    
    Returns:
        list[str]: 匹配的文件路径列表
    """
    # 检查ripgrep是否可用
    rg = shutil.which("rg")
    # Path.glob("**/*") 会遍历隐藏和忽略的路径（如 .venv/）
    # 在实际工作区上可能很慢。优先使用 rg --files。
    if rg and ("**" in pattern or "/" in pattern):
        # 判断是否应该包含隐藏文件
        include_hidden = _looks_like_git_repo(root)
        cmd = [rg, "--files"]
        if include_hidden:
            cmd.append("--hidden")
        cmd.extend(["--glob", pattern, "."])

        # 创建异步子进程执行ripgrep
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(root),
            stdin=asyncio.subprocess.DEVNULL,  # 防止Windows上的句柄继承死锁
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        lines: list[str] = []
        try:
            assert process.stdout is not None
            # 读取输出直到达到限制
            while len(lines) < limit:
                raw = await process.stdout.readline()
                if not raw:
                    break
                line = raw.decode("utf-8", errors="replace").strip()
                if line:
                    lines.append(line)
        finally:
            # 如果达到限制且进程仍在运行，终止进程
            if len(lines) >= limit and process.returncode is None:
                process.terminate()
            await process.wait()

        # 排序保持单元测试和用户输出的确定性
        lines.sort()
        return lines

    # 后备：非递归模式通常很便宜；保持Python语义
    return sorted(
        str(path.relative_to(root))
        for path in root.glob(pattern)
    )[:limit]
