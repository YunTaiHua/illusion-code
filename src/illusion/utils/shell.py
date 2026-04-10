"""
Shell 和子进程辅助函数模块
=====================

本模块提供 shell 命令执行和子进程创建的跨平台支持功能。

主要功能：
    - 解析适合当前平台的最佳 shell 命令
    - 创建带有沙箱支持的异步子进程
    - 在 Windows 上智能查找可用的 bash 可执行文件

函数说明：
    - resolve_shell_command: 返回当前平台的最佳 shell 命令 argv
    - create_shell_subprocess: 创建带有沙箱支持的 shell 子进程
    - _resolve_windows_bash: 解析 Windows 上可用的 bash 可执行文件

使用示例：
    >>> from illusion.utils import resolve_shell_command
    
    >>> # 获取当前平台的 shell 命令
    >>> argv = resolve_shell_command("echo hello")
    >>> print(argv)  # ['bash', '-lc', 'echo hello']
    
    >>> # 创建子进程
    >>> process = await create_shell_subprocess("ls", cwd="/tmp")
"""

from __future__ import annotations

import asyncio
import os
import shutil
from collections.abc import Mapping
from pathlib import Path

from illusion.config import Settings, load_settings
from illusion.platforms import PlatformName, get_platform
from illusion.sandbox import wrap_command_for_sandbox


def resolve_shell_command(
    command: str,
    *,
    platform_name: PlatformName | None = None,
) -> list[str]:
    """
    解析适合当前平台的最佳 shell 命令
    
    根据平台类型自动选择最优的 shell 解释器：
    - Windows: 优先 WSL bash，其次 PowerShell，最后 cmd.exe
    - Unix/Linux/macOS: 优先 bash，其次 sh
    
    Args:
        command: 要执行的 shell 命令字符串
        platform_name: 指定平台名称，默认自动检测
    
    Returns:
        list[str]: shell 命令的 argv 列表，第一个元素为可执行文件路径
    
    使用示例：
        >>> argv = resolve_shell_command("ls -la")
        >>> argv  # ['bash', '-lc', 'ls -la']
    """
    resolved_platform = platform_name or get_platform()
    # Windows 平台优先尝试 WSL bash
    if resolved_platform == "windows":
        bash = _resolve_windows_bash()
        if bash:
            return [bash, "-lc", command]
        powershell = shutil.which("pwsh") or shutil.which("powershell")
        if powershell:
            return [powershell, "-NoLogo", "-NoProfile", "-Command", command]
        return [shutil.which("cmd.exe") or "cmd.exe", "/d", "/s", "/c", command]

    # Unix 系统优先使用 bash
    bash = shutil.which("bash")
    if bash:
        return [bash, "-lc", command]
    shell = shutil.which("sh") or os.environ.get("SHELL") or "/bin/sh"
    return [shell, "-lc", command]


async def create_shell_subprocess(
    command: str,
    *,
    cwd: str | Path,
    settings: Settings | None = None,
    stdin: int | None = None,
    stdout: int | None = None,
    stderr: int | None = None,
    env: Mapping[str, str] | None = None,
) -> asyncio.subprocess.Process:
    """
    创建带有平台感知和沙箱支持的 shell 子进程
    
    自动解析适合平台的 shell 命令，并应用沙箱包装（如果启用）。
    
    Args:
        command: 要执行的 shell 命令
        cwd: 工作目录
        settings: 配置对象，默认自动加载
        stdin: 标准输入文件描述符
        stdout: 标准输出文件描述符
        stderr: 标准错误文件描述符
        environment: 环境变量映射
    
    Returns:
        asyncio.subprocess.Process: 异步子进程对象
    
    使用示例：
        >>> process = await create_shell_subprocess("ls", cwd="/tmp")
        >>> await process.wait()
    """
    resolved_settings = settings or load_settings()
    argv = resolve_shell_command(command)
    # 使用沙箱包装命令（如果配置启用）
    argv, cleanup_path = wrap_command_for_sandbox(argv, settings=resolved_settings)

    try:
        process = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(Path(cwd).resolve()),
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            env=dict(env) if env is not None else None,
        )
    except Exception:
        # 发生异常时清理沙箱临时文件
        if cleanup_path is not None:
            cleanup_path.unlink(missing_ok=True)
        raise

    # 进程结束后异步清理沙箱临时文件
    if cleanup_path is not None:
        asyncio.create_task(_cleanup_after_exit(process, cleanup_path))
    return process


async def _cleanup_after_exit(process: asyncio.subprocess.Process, cleanup_path: Path) -> None:
    """
    进程退出后清理沙箱临时文件
    
    Args:
        process: 要监控的子进程
        cleanup_path: 需要清理的文件路径
    """
    try:
        await process.wait()
    finally:
        cleanup_path.unlink(missing_ok=True)


def _resolve_windows_bash() -> str | None:
    """
    解析 Windows 上可用的 bash 可执行文件
    
    忽略传统的 Windows 系统 shim（C:\\Windows\\System32\\bash.exe），
    该位置可能在未配置 WSL 的机器上失败或输出无法读取的内容。
    
    解析优先级：
        1. ILLUSION_CODE_GIT_BASH_PATH 环境变量覆盖
        2. 通过 PATH 找到的 bash（排除 system32 shim）
        3. 从 git 可执行文件位置解析 bash
        4. 在已知的 Git for Windows 安装路径中查找
    
    Returns:
        str | None: bash 可执行文件路径，未找到则返回 None
    """
    # 1. 通过环境变量显式指定
    env_bash = os.environ.get("ILLUSION_CODE_GIT_BASH_PATH")
    if env_bash and Path(env_bash).exists():
        return env_bash

    # 2. PATH 上的 bash（跳过传统的 system32 shim）
    bash = shutil.which("bash")
    if bash and not _is_windows_bash_shim(bash):
        return bash

    # 3. 从 git 可执行文件位置解析 bash
    git_path = shutil.which("git")
    if git_path:
        # git.exe 通常位于 <Git-Root>\cmd\git.exe 或 <Git-Root>\bin\git.exe
        # bash.exe 位于 <Git-Root>\bin\bash.exe
        git_root = Path(git_path).resolve().parent.parent
        bash_via_git = git_root / "bin" / "bash.exe"
        if bash_via_git.exists():
            return str(bash_via_git)

    # 4. 在已知的 Git for Windows 安装路径中搜索
    for candidate in _windows_git_bash_candidates():
        if candidate.exists():
            return str(candidate)

    return None


def _windows_git_bash_candidates() -> list[Path]:
    """
    生成已知的 Git for Windows 安装路径候选列表
    
    在常见的 Program Files 目录中查找 Git 安装路径。
    
    Returns:
        list[Path]: 可能的 bash.exe 路径列表
    """
    roots: list[str] = []
    for key in ("ProgramFiles", "ProgramFiles(x86)", "LocalAppData"):
        value = os.environ.get(key)
        if value:
            roots.append(value)

    candidates: list[Path] = []
    for root in roots:
        base = Path(root)
        candidates.append(base / "Git" / "bin" / "bash.exe")
        candidates.append(base / "Git" / "usr" / "bin" / "bash.exe")
        candidates.append(base / "Programs" / "Git" / "bin" / "bash.exe")
        candidates.append(base / "Programs" / "Git" / "usr" / "bin" / "bash.exe")
    return candidates


def _is_windows_bash_shim(path: str) -> bool:
    """
    检查路径是否为 Windows system32 bash shim
    
    判断给定路径是否为传统的 Windows system32 bash 替身（shim），
    这是一个空壳程序，不提供真正的 bash 功能。
    
    Args:
        path: 要检查的可执行文件路径
    
    Returns:
        bool: 是否为 system32 shim
    """
    normalized = path.replace("/", "\\").lower()
    return normalized.endswith("\\windows\\system32\\bash.exe")