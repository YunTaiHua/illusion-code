"""
桥接会话管理器模块
=================

本模块提供桥接会话的跟踪和管理功能。

主要功能：
    - 管理生成的子会话
    - 捕获会话输出
    - 列出和读取会话状态

类说明：
    - BridgeSessionRecord: UI安全的会话快照
    - BridgeSessionManager: 桥接会话管理器

函数说明：
    - get_bridge_manager: 获取单例会话管理器

使用示例：
    >>> from illusion.bridge import get_bridge_manager
    >>> manager = get_bridge_manager()
    >>> sessions = manager.list_sessions()
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from illusion.config.paths import get_data_dir
from illusion.bridge.session_runner import SessionHandle, spawn_session


@dataclass(frozen=True)
class BridgeSessionRecord:
    """UI安全的桥接会话快照
    
    Attributes:
        session_id: 会话唯一标识符
        command: 执行的命令
        cwd: 工作目录
        pid: 进程ID
        status: 会话状态 (running/completed/failed)
        started_at: 启动时间戳
        output_path: 输出文件路径
    """

    session_id: str  # 会话ID
    command: str  # 命令
    cwd: str  # 工作目录
    pid: int  # 进程ID
    status: str  # 状态
    started_at: float  # 启动时间
    output_path: str  # 输出路径


class BridgeSessionManager:
    """管理桥接运行的子会话并捕获其输出
    
    Attributes:
        _sessions: 会话ID到句柄的映射
        _commands: 会话ID到命令的映射
        _output_paths: 会话ID到输出文件路径的映射
        _copy_tasks: 会话ID到异步复制任务的映射
    
    Example:
        >>> manager = BridgeSessionManager()
        >>> handle = await manager.spawn(session_id="test", command="echo hello", cwd=".")
    """

    def __init__(self) -> None:
        self._sessions: dict[str, SessionHandle] = {}  # 会话映射
        self._commands: dict[str, str] = {}  # 命令映射
        self._output_paths: dict[str, Path] = {}  # 输出路径映射
        self._copy_tasks: dict[str, asyncio.Task[None]] = {}  # 复制任务映射

    async def spawn(self, *, session_id: str, command: str, cwd: str | Path) -> SessionHandle:
        """生成新的桥接会话
        
        Args:
            session_id: 会话唯一标识符
            command: 要执行的命令
            cwd: 工作目录
        
        Returns:
            SessionHandle: 会话句柄
        """
        handle = await spawn_session(session_id=session_id, command=command, cwd=cwd)  # 生成会话
        self._sessions[session_id] = handle  # 存储句柄
        self._commands[session_id] = command  # 存储命令
        output_dir = get_data_dir() / "bridge"  # 输出目录
        output_dir.mkdir(parents=True, exist_ok=True)  # 创建目录
        output_path = output_dir / f"{session_id}.log"  # 输出文件
        output_path.write_text("", encoding="utf-8")  # 初始化文件
        self._output_paths[session_id] = output_path  # 存储路径
        self._copy_tasks[session_id] = asyncio.create_task(self._copy_output(session_id, handle))  # 启动输出复制
        return handle

    def list_sessions(self) -> list[BridgeSessionRecord]:
        """列出所有会话
        
        Returns:
            list[BridgeSessionRecord]: 按启动时间倒序排列的会话列表
        """
        items: list[BridgeSessionRecord] = []  # 结果列表
        for session_id, handle in self._sessions.items():  # 遍历会话
            process = handle.process  # 进程
            if process.returncode is None:  # 运行中
                status = "running"
            elif process.returncode == 0:  # 正常退出
                status = "completed"
            else:  # 异常退出
                status = "failed"
            items.append(
                BridgeSessionRecord(
                    session_id=session_id,  # 会话ID
                    command=self._commands.get(session_id, ""),  # 命令
                    cwd=str(handle.cwd),  # 工作目录
                    pid=process.pid or 0,  # 进程ID
                    status=status,  # 状态
                    started_at=handle.started_at,  # 启动时间
                    output_path=str(self._output_paths[session_id]),  # 输出路径
                )
            )
        return sorted(items, key=lambda item: item.started_at, reverse=True)  # 按时间倒序

    def read_output(self, session_id: str, *, max_bytes: int = 12000) -> str:
        """读取会话输出
        
        Args:
            session_id: 会话ID
            max_bytes: 最大返回字节数
        
        Returns:
            str: 输出内容 (如果超过max_bytes，返回最后max_bytes字节)
        """
        path = self._output_paths.get(session_id)  # 获取输出路径
        if path is None or not path.exists():  # 不存在
            return ""
        content = path.read_text(encoding="utf-8", errors="replace")  # 读取内容
        if len(content) > max_bytes:  # 超过限制
            return content[-max_bytes:]  # 返回最后部分
        return content  # 返回全部

    async def stop(self, session_id: str) -> None:
        """停止会话
        
        Args:
            session_id: 会话ID
        
        Raises:
            ValueError: 如果会话不存在
        """
        handle = self._sessions.get(session_id)  # 获取句柄
        if handle is None:  # 不存在
            raise ValueError(f"Unknown bridge session: {session_id}")
        await handle.kill()  # 终止会话

    async def _copy_output(self, session_id: str, handle: SessionHandle) -> None:
        """异步复制会话输出到文件
        
        Args:
            session_id: 会话ID
            handle: 会话句柄
        """
        path = self._output_paths[session_id]  # 输出路径
        if handle.process.stdout is not None:  # 有输出
            while True:
                chunk = await handle.process.stdout.read(4096)  # 读取块
                if not chunk:  # 无数据
                    break
                with path.open("ab") as stream:  # 追加模式
                    stream.write(chunk)  # 写入
        await handle.process.wait()  # 等待进程结束


_DEFAULT_MANAGER: BridgeSessionManager | None = None  # 默认管理器单例


def get_bridge_manager() -> BridgeSessionManager:
    """获取单例桥接会话管理器
    
    Returns:
        BridgeSessionManager: 全局会话管理器实例
    """
    global _DEFAULT_MANAGER  # 声明全局变量
    if _DEFAULT_MANAGER is None:  # 未初始化
        _DEFAULT_MANAGER = BridgeSessionManager()  # 创建实例
    return _DEFAULT_MANAGER  # 返回实例