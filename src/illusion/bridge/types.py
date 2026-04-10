"""
桥接配置类型模块
================

本模块定义 Illusion Bridge 所需的配置数据类型，用于在组件之间传递配置信息。

主要功能：
    - 定义工作数据类型（WorkData）
    - 定义工作密钥类型（WorkSecret）
    - 定义桥接配置类型（BridgeConfig）

类说明：
    - WorkData: 工作项元数据，包含类型和ID
    - WorkSecret: 解码后的工作密钥，包含版本、令牌和API地址
    - BridgeConfig: 桥接配置，包含目录、机器名、会话数等

使用示例：
    >>> from illusion.bridge.types import WorkData, WorkSecret, BridgeConfig
    >>> 
    >>> # 创建工作数据
    >>> work = WorkData(type="session", id="abc123")
    >>> 
    >>> # 创建工作密钥
    >>> secret = WorkSecret(version=1, session_ingress_token="token", api_base_url="https://api.example.com")
    >>> 
    >>> # 创建桥接配置
    >>> config = BridgeConfig(dir="/tmp/bridge", machine_name="machine-1")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


# 默认会话超时时间：24小时（毫秒）
DEFAULT_SESSION_TIMEOUT_MS = 24 * 60 * 60 * 1000


@dataclass(frozen=True)
class WorkData:
    """
    工作项元数据
    
    用于标识工作项的类型和唯一标识符。
    
    Attributes:
        type: 工作类型，可选值为 "session"（会话）或 "healthcheck"（健康检查）
        id: 工作项的唯一标识符
    
    使用示例：
        >>> WorkData(type="session", id="abc123")
    """

    # 工作类型：session 或 healthcheck
    type: Literal["session", "healthcheck"]
    # 工作项唯一标识符
    id: str


@dataclass(frozen=True)
class WorkSecret:
    """
    解码后的工作密钥
    
    包含与后端服务建立连接所需的认证信息。
    
    Attributes:
        version: 密钥版本号，目前仅支持版本 1
        session_ingress_token: 会话入口令牌，用于身份验证
        api_base_url: API 基础地址，服务端点
    
    使用示例：
        >>> WorkSecret(version=1, session_ingress_token="token", api_base_url="https://api.example.com")
    """

    # 密钥版本号
    version: int
    # 会话入口令牌
    session_ingress_token: str
    # API 基础地址
    api_base_url: str


@dataclass(frozen=True)
class BridgeConfig:
    """
    桥接配置
    
    定义桥接服务的基本配置信息。
    
    Attributes:
        dir: 桥接目录路径
        machine_name: 机器名称，用于标识当前节点
        max_sessions: 最大会话数，默认为 1
        verbose: 是否启用详细输出，默认为 False
        session_timeout_ms: 会话超时时间（毫秒），默认为 24 小时
    
    使用示例：
        >>> config = BridgeConfig(dir="/tmp/bridge", machine_name="machine-1")
        >>> config = BridgeConfig(dir="/tmp/bridge", machine_name="machine-1", max_sessions=5, verbose=True)
    """

    # 桥接目录路径
    dir: str
    # 机器名称
    machine_name: str
    # 最大会话数
    max_sessions: int = 1
    # 是否启用详细输出
    verbose: bool = False
    # 会话超时时间（毫秒）
    session_timeout_ms: int = DEFAULT_SESSION_TIMEOUT_MS
