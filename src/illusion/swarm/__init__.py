"""
Swarm 后端抽象模块
==================

本模块提供队友执行的后端抽象功能。

主要组件：
    - SubprocessBackend: 子进程后端
    - BackendRegistry: 后端注册表
    - get_backend_registry: 获取后端注册表
    - TeammateExecutor: 队友执行器
    - TeammateIdentity: 队友身份
    - TeammateMessage: 队友消息
    - TeammateSpawnConfig: 队友生成配置
    - SpawnResult: 生成结果
    - BackendType: 后端类型

使用示例：
    >>> from illusion.swarm import SubprocessBackend, BackendRegistry
"""

from __future__ import annotations

from importlib import import_module

# 导入核心组件
from illusion.swarm.registry import BackendRegistry, get_backend_registry
from illusion.swarm.subprocess_backend import SubprocessBackend
from illusion.swarm.types import (
    BackendType,
    SpawnResult,
    TeammateExecutor,
    TeammateIdentity,
    TeammateMessage,
    TeammateSpawnConfig,
)

# 延迟加载的导出（仅 POSIX）
# 这些组件在 POSIX 系统上可用，在 Windows 上不可用
_LAZY_EXPORTS = {
    "MailboxMessage": ("illusion.swarm.mailbox", "MailboxMessage"),
    "TeammateMailbox": ("illusion.swarm.mailbox", "TeammateMailbox"),
    "create_idle_notification": ("illusion.swarm.mailbox", "create_idle_notification"),
    "create_shutdown_request": ("illusion.swarm.mailbox", "create_shutdown_request"),
    "create_user_message": ("illusion.swarm.mailbox", "create_user_message"),
    "get_agent_mailbox_dir": ("illusion.swarm.mailbox", "get_agent_mailbox_dir"),
    "get_team_dir": ("illusion.swarm.mailbox", "get_team_dir"),
    "SwarmPermissionRequest": ("illusion.swarm.permission_sync", "SwarmPermissionRequest"),
    "SwarmPermissionResponse": ("illusion.swarm.permission_sync", "SwarmPermissionResponse"),
    "create_permission_request": ("illusion.swarm.permission_sync", "create_permission_request"),
    "handle_permission_request": ("illusion.swarm.permission_sync", "handle_permission_request"),
    "poll_permission_response": ("illusion.swarm.permission_sync", "poll_permission_response"),
    "send_permission_request": ("illusion.swarm.permission_sync", "send_permission_request"),
    "send_permission_response": ("illusion.swarm.permission_sync", "send_permission_response"),
}

# 导出列表：定义公开 API
__all__ = [
    "BackendRegistry",
    "BackendType",
    "MailboxMessage",
    "SpawnResult",
    "SubprocessBackend",
    "SwarmPermissionRequest",
    "SwarmPermissionResponse",
    "TeammateExecutor",
    "TeammateIdentity",
    "TeammateMailbox",
    "TeammateMessage",
    "TeammateSpawnConfig",
    "create_idle_notification",
    "create_permission_request",
    "create_shutdown_request",
    "create_user_message",
    "get_agent_mailbox_dir",
    "get_backend_registry",
    "get_team_dir",
    "handle_permission_request",
    "poll_permission_response",
    "send_permission_request",
    "send_permission_response",
]


def __getattr__(name: str):
    """延迟加载仅 POSIX 的 swarm 辅助函数

    当访问 POSIX 专用组件时，按需导入对应的模块。
    这样可以避免在 Windows 上导入失败。
    """
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    # 动态导入模块并获取属性
    module_name, attr_name = target
    value = getattr(import_module(module_name), attr_name)
    # 缓存到全局字典，避免重复导入
    globals()[name] = value
    return value
