"""
认证模块
========

本模块提供 IllusionCode 统一的认证管理功能。

主要组件：
    - AuthManager: 认证管理器
    - ApiKeyFlow: API 密钥认证流程
    - BrowserFlow: 浏览器认证流程
    - DeviceCodeFlow: 设备代码认证流程
    - store_credential/load_credential: 凭据存储/加载
    - store_external_binding/load_external_binding: 外部绑定存储/加载
    - encrypt/decrypt: 加密/解密功能

使用示例：
    >>> from illusion.auth import AuthManager, ApiKeyFlow
    >>> manager = AuthManager()
    >>> flow = ApiKeyFlow(provider="anthropic")
    >>> key = flow.run()
"""

from illusion.auth.flows import ApiKeyFlow, BrowserFlow, DeviceCodeFlow
from illusion.auth.manager import AuthManager
from illusion.auth.storage import (
    clear_provider_credentials,
    decrypt,
    encrypt,
    load_external_binding,
    load_credential,
    store_external_binding,
    store_credential,
)

__all__ = [
    "AuthManager",
    "ApiKeyFlow",
    "BrowserFlow",
    "DeviceCodeFlow",
    "store_credential",
    "load_credential",
    "store_external_binding",
    "load_external_binding",
    "clear_provider_credentials",
    "encrypt",
    "decrypt",
]
