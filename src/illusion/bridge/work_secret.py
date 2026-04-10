"""
工作密钥处理模块
================

本模块提供工作密钥的编码、解码和URL构建功能，用于客户端与后端服务的安全通信。

主要功能：
    - 编码工作密钥为 Base64URL 格式
    - 解码并验证 Base64URL 格式的工作密钥
    - 构建会话入口 WebSocket URL

函数说明：
    - encode_work_secret: 将 WorkSecret 对象编码为字符串
    - decode_work_secret: 将字符串解码为 WorkSecret 对象
    - build_sdk_url: 构建会话入口 WebSocket URL

使用示例：
    >>> from illusion.bridge.types import WorkSecret
    >>> from illusion.bridge.work_secret import encode_work_secret, decode_work_secret, build_sdk_url
    >>> 
    >>> # 编码工作密钥
    >>> secret = WorkSecret(version=1, session_ingress_token="token", api_base_url="https://api.example.com")
    >>> encoded = encode_work_secret(secret)
    >>> 
    >>> # 解码工作密钥
    >>> decoded = decode_work_secret(encoded)
    >>> 
    >>> # 构建 WebSocket URL
    >>> ws_url = build_sdk_url("https://api.example.com", "session-123")
"""

from __future__ import annotations

import base64
import json

from illusion.bridge.types import WorkSecret


def encode_work_secret(secret: WorkSecret) -> str:
    """
    编码工作密钥
    
    将 WorkSecret 对象序列化为 JSON 字符串，然后进行 Base64URL 编码。
    
    Args:
        secret: WorkSecret 对象，包含版本、令牌和 API 地址
    
    Returns:
        str: Base64URL 编码后的字符串（不包含填充字符）
    
    使用示例：
        >>> secret = WorkSecret(version=1, session_ingress_token="token", api_base_url="https://api.example.com")
        >>> encoded = encode_work_secret(secret)
    """
    # 将 WorkSecret 对象转换为字典并序列化为 JSON 格式
    data = json.dumps(secret.__dict__, separators=(",", ":")).encode("utf-8")
    # 使用 Base64URL 编码并移除填充字符
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def decode_work_secret(secret: str) -> WorkSecret:
    """
    解码并验证工作密钥
    
    将 Base64URL 编码的字符串解码为 WorkSecret 对象，并进行版本和字段验证。
    
    Args:
        secret: Base64URL 编码的工作密钥字符串
    
    Returns:
        WorkSecret: 解码后的 WorkSecret 对象
    
    Raises:
        ValueError: 当密钥版本不支持或缺少必需字段时
    
    使用示例：
        >>> decoded = decode_work_secret("eyJ2ZXJzaW9uIjoxLCJzZXNzaW9uX2luZ3Jlc3NfdG9rZW4iOiJ0b2tlbiIsImFwaV9iYXNlX3VybCI6Imh0dHBzOi8vYXBpLmV4YW1wbGUuY29tIn0")
    """
    # 计算并添加缺失的填充字符
    padding = "=" * (-len(secret) % 4)
    # 解码 Base64URL 数据
    raw = base64.urlsafe_b64decode((secret + padding).encode("utf-8"))
    # 解析 JSON 数据
    data = json.loads(raw.decode("utf-8"))
    # 验证密钥版本
    if data.get("version") != 1:
        raise ValueError(f"Unsupported work secret version: {data.get('version')}")
    # 验证会话入口令牌
    if not data.get("session_ingress_token"):
        raise ValueError("Invalid work secret: missing session_ingress_token")
    # 验证 API 基础地址
    if not isinstance(data.get("api_base_url"), str):
        raise ValueError("Invalid work secret: missing api_base_url")
    # 创建 WorkSecret 对象
    return WorkSecret(
        version=data["version"],
        session_ingress_token=data["session_ingress_token"],
        api_base_url=data["api_base_url"],
    )


def build_sdk_url(api_base_url: str, session_id: str) -> str:
    """
    构建会话入口 WebSocket URL
    
    根据 API 基础地址和会话 ID 构建完整的 WebSocket 连接 URL。
    本地环境使用 ws 协议和 v2 版本，生产环境使用 wss 协议和 v1 版本。
    
    Args:
        api_base_url: API 基础地址，如 "https://api.example.com"
        session_id: 会话唯一标识符
    
    Returns:
        str: 完整的 WebSocket URL
    
    使用示例：
        >>> url = build_sdk_url("https://api.example.com", "session-123")
        >>> # 本地: ws://api.example.com/v2/session_ingress/ws/session-123
        >>> # 生产: wss://api.example.com/v1/session_ingress/ws/session-123
    """
    # 判断是否为本地环境
    is_local = "localhost" in api_base_url or "127.0.0.1" in api_base_url
    # 根据环境选择 WebSocket 协议
    protocol = "ws" if is_local else "wss"
    # 根据环境选择版本
    version = "v2" if is_local else "v1"
    # 提取主机地址（移除协议前缀和尾部斜杠）
    host = api_base_url.replace("https://", "").replace("http://", "").rstrip("/")
    # 构建完整的 WebSocket URL
    return f"{protocol}://{host}/{version}/session_ingress/ws/{session_id}"
