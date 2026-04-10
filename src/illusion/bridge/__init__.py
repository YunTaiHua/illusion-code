"""
桥接模块
========

本模块提供 IllusionCode 桥接会话管理功能。

主要组件：
    - BridgeSessionManager: 桥接会话管理器
    - BridgeSessionRecord: 桥接会话记录
    - BridgeConfig: 桥接配置
    - SessionHandle: 会话句柄
    - WorkData: 工作数据
    - WorkSecret: 工作密钥
    - get_bridge_manager: 获取桥接管理器
    - spawn_session: 生成会话

使用示例：
    >>> from illusion.bridge import BridgeSessionManager, spawn_session
"""

from illusion.bridge.manager import BridgeSessionManager, BridgeSessionRecord, get_bridge_manager
from illusion.bridge.session_runner import SessionHandle, spawn_session
from illusion.bridge.types import BridgeConfig, WorkData, WorkSecret
from illusion.bridge.work_secret import build_sdk_url, decode_work_secret, encode_work_secret

__all__ = [
    "BridgeSessionManager",
    "BridgeSessionRecord",
    "BridgeConfig",
    "SessionHandle",
    "WorkData",
    "WorkSecret",
    "build_sdk_url",
    "decode_work_secret",
    "encode_work_secret",
    "get_bridge_manager",
    "spawn_session",
]
