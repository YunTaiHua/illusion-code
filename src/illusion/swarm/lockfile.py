"""
跨平台文件锁辅助模块
===================

本模块为 swarm 邮箱和权限存储提供跨平台的文件锁功能。
支持 POSIX 系统（Linux、macOS）和 Windows。

主要组件：
    - exclusive_file_lock: 独占文件锁上下文管理器
    - SwarmLockError: 锁失败基础异常
    - SwarmLockUnavailableError: 平台不支持锁异常

使用示例：
    >>> from illusion.swarm.lockfile import exclusive_file_lock
    >>> 
    >>> with exclusive_file_lock(lock_path):
    >>>     # 临界区代码
    >>>     pass
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from illusion.platforms import PlatformName, get_platform


class SwarmLockError(RuntimeError):
    """swarm 锁失败的基础异常。"""


class SwarmLockUnavailableError(SwarmLockError):
    """当当前平台不支持文件锁时引发。"""


@contextmanager
def exclusive_file_lock(
    lock_path: Path,
    *,
    platform_name: PlatformName | None = None,
) -> Iterator[None]:
    """为 swarm 邮箱/权限操作获取独占文件锁。

    Args:
        lock_path: 锁文件路径。
        platform_name: 可选的平台覆盖（用于测试）。

    Yields:
        无。

    Raises:
        SwarmLockUnavailableError: 当平台不支持文件锁时。
    """
    resolved_platform = platform_name or get_platform()
    if resolved_platform == "windows":
        with _exclusive_windows_lock(lock_path):
            yield
        return
    if resolved_platform in {"macos", "linux", "wsl"}:
        with _exclusive_posix_lock(lock_path):
            yield
        return
    raise SwarmLockUnavailableError(
        f"swarm file locking is not supported on platform {resolved_platform!r}"
    )


@contextmanager
def _exclusive_posix_lock(lock_path: Path) -> Iterator[None]:
    """POSIX 系统（Linux、macOS）的独占文件锁实现。"""
    import fcntl

    # 确保锁目录存在
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch(exist_ok=True)
    
    # 打开文件并获取排他锁
    with lock_path.open("a+b") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


@contextmanager
def _exclusive_windows_lock(lock_path: Path) -> Iterator[None]:
    """Windows 的独占文件锁实现。"""
    import msvcrt

    # 确保锁目录存在
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    
    with lock_path.open("a+b") as lock_file:
        # msvcrt.locking 需要字节范围存在且文件以二进制模式打开。
        # 锁定关键部分生命周期内的第一个字节。
        lock_file.seek(0)
        if lock_path.stat().st_size == 0:
            lock_file.write(b"\0")
            lock_file.flush()
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        try:
            yield
        finally:
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
