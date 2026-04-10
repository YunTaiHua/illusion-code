"""
子进程后端模块
==============

本模块实现基于子进程的 TeammateExecutor 接口。
使用现有的 :class:`~illusion.tasks.manager.BackgroundTaskManager` 
来创建和管理子进程，通过 stdin/stdout 进行通信。

主要组件：
    - SubprocessBackend: 子进程执行后端

使用示例：
    >>> from illusion.swarm import SubprocessBackend
    >>> backend = SubprocessBackend()
    >>> result = await backend.spawn(config)
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

# 导入工具函数和类型定义
from illusion.swarm.spawn_utils import (
    build_inherited_cli_flags,
    build_inherited_env_vars,
    get_teammate_command,
)
from illusion.swarm.types import (
    BackendType,
    SpawnResult,
    TeammateMessage,
    TeammateSpawnConfig,
)
from illusion.tasks.manager import get_task_manager

if TYPE_CHECKING:
    pass

# 配置模块级日志记录器
logger = logging.getLogger(__name__)


class SubprocessBackend:
    """TeammateExecutor 实现，每个队友作为独立子进程运行。

    使用现有的 :class:`~illusion.tasks.manager.BackgroundTaskManager`
    来创建和管理子进程，通过 stdin/stdout 进行通信。
    """

    # 后端类型标识
    type: BackendType = "subprocess"

    # 映射 agent_id -> task_id，用于跟踪活跃的代理
    _agent_tasks: dict[str, str]

    def __init__(self) -> None:
        """初始化子进程后端。"""
        self._agent_tasks = {}

    def is_available(self) -> bool:
        """子进程后端始终可用。"""
        return True

    async def spawn(self, config: TeammateSpawnConfig) -> SpawnResult:
        """通过任务管理器作为子进程生成新队友。

        构建适当的 CLI 命令并创建 ``local_agent`` 任务，
        该任务通过 stdin 接受初始提示词。
        """
        # 构建代理 ID，格式为 name@team
        agent_id = f"{config.name}@{config.team}"

        # 构建继承的 CLI 标志
        flags = build_inherited_cli_flags(
            model=config.model,
            plan_mode_required=config.plan_mode_required,
        )
        # 构建继承的环境变量
        extra_env = build_inherited_env_vars()

        # 为 shell 调用构建环境导出前缀
        env_prefix = " ".join(f"{k}={v!r}" for k, v in extra_env.items())

        # 获取队友命令
        teammate_cmd = get_teammate_command()
        cmd_parts = [teammate_cmd, "-m", "illusion"] + flags
        command = f"{env_prefix} {' '.join(cmd_parts)}" if env_prefix else " ".join(cmd_parts)

        # 获取任务管理器并创建任务
        manager = get_task_manager()
        try:
            record = await manager.create_agent_task(
                prompt=config.prompt,
                description=f"Teammate: {agent_id}",
                cwd=config.cwd,
                task_type="in_process_teammate",
                model=config.model,
                command=command,
            )
        except Exception as exc:
            logger.error("Failed to spawn teammate %s: %s", agent_id, exc)
            return SpawnResult(
                task_id="",
                agent_id=agent_id,
                backend_type=self.type,
                success=False,
                error=str(exc),
            )

        # 记录 agent_id -> task_id 映射
        self._agent_tasks[agent_id] = record.id
        logger.debug("Spawned teammate %s as task %s", agent_id, record.id)
        return SpawnResult(
            task_id=record.id,
            agent_id=agent_id,
            backend_type=self.type,
        )

    async def send_message(self, agent_id: str, message: TeammateMessage) -> None:
        """通过其 stdin 管道向运行中的队友发送消息。

        消息序列化为单个 JSON 行，以便队友可以区分
        结构化消息和纯提示词。
        """
        task_id = self._agent_tasks.get(agent_id)
        if task_id is None:
            raise ValueError(f"No active subprocess for agent {agent_id!r}")

        # 构建消息载荷
        payload = {
            "text": message.text,
            "from": message.from_agent,
            "timestamp": message.timestamp,
        }
        if message.color:
            payload["color"] = message.color
        if message.summary:
            payload["summary"] = message.summary

        # 写入任务 stdin
        manager = get_task_manager()
        await manager.write_to_task(task_id, json.dumps(payload))
        logger.debug("Sent message to %s (task %s)", agent_id, task_id)

    async def shutdown(self, agent_id: str, *, force: bool = False) -> bool:
        """终止子进程队友。

        Args:
            agent_id: 要终止的代理。
            force: 对于子进程后端被忽略；始终发送 SIGTERM，
                   然后在短暂等待后发送 SIGKILL（由任务管理器处理）。

        Returns:
            如果找到任务并终止返回 True。
        """
        task_id = self._agent_tasks.get(agent_id)
        if task_id is None:
            logger.warning("shutdown() called for unknown agent %s", agent_id)
            return False

        manager = get_task_manager()
        try:
            await manager.stop_task(task_id)
        except ValueError as exc:
            logger.debug("stop_task for %s: %s", task_id, exc)
            # 任务可能已经完成 —— 仍然清理映射
        finally:
            self._agent_tasks.pop(agent_id, None)

        logger.debug("Shut down teammate %s (task %s)", agent_id, task_id)
        return True

    def get_task_id(self, agent_id: str) -> str | None:
        """返回给定代理的任务管理器任务 ID（如果已知）。"""
        return self._agent_tasks.get(agent_id)
