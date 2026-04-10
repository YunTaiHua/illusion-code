"""
桥接会话运行器模块
=================

本模块提供桥接会话的生成和管理功能。

主要功能：
    - 生成子会话进程
    - 管理会话生命周期

类说明：
    - SessionHandle: 生成的桥接会话句柄

函数说明：
    - spawn_session: 生成新的桥接会话

使用示例：
    >>> from illusion.bridge import spawn_session, SessionHandle
    >>> handle = await spawn_session(session_id="test", command="echo hello", cwd=".")
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path

from illusion.utils.shell import create_shell_subprocess


@dataclass
class SessionHandle:
    """生成的桥接会话句柄
    
    Attributes:
        session_id: 会话唯一标识符
        process: 异步子进程对象
        cwd: 工作目录路径
        started_at: 启动时间戳
    """

    session_id: str  # 会话ID
    process: asyncio.subprocess.Process  # 异步进程
    cwd: Path  # 工作目录
    started_at: float = field(default_factory=time.time)  # 启动时间

    async def kill(self) -> None:
        """终止会话进程
        
        先尝试优雅终止 (terminate)，超时后强制终止 (kill)
        """
        self.process.terminate()  # 发送终止信号
        try:
            await asyncio.wait_for(self.process.wait(), timeout=3)  # 等待进程终止
        except asyncio.TimeoutError:  # 超时
            self.process.kill()  # 强制终止
            await self.process.wait()  # 等待进程


async def spawn_session(
    *,
    session_id: str,
    command: str,
    cwd: str | Path,
) -> SessionHandle:
    """生成一个桥接管理的子会话
    
    Args:
        session_id: 会话唯一标识符
        command: 要执行的命令
        cwd: 工作目录
    
    Returns:
        SessionHandle: 会话句柄
    """
    resolved_cwd = Path(cwd).resolve()  # 解析为绝对路径
    process = await create_shell_subprocess(  # 创建子进程
        command,  # 命令
        cwd=resolved_cwd,  # 工作目录
        stdout=asyncio.subprocess.PIPE,  # 标准输出管道
        stderr=asyncio.subprocess.PIPE,  # 标准错误管道
    )
    return SessionHandle(session_id=session_id, process=process, cwd=resolved_cwd)