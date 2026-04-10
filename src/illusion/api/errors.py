"""
API 错误类型模块
================

本模块定义 IllusionCode API 相关的自定义异常类型。

主要功能：
    - 定义基础 API 异常类
    - 提供认证失败、速率限制、请求失败等具体异常

类说明：
    - IllusionCodeApiError: 所有 API 异常的基类
    - AuthenticationFailure: 认证失败异常
    - RateLimitFailure: 速率限制异常
    - RequestFailure: 请求失败异常

使用示例：
    >>> from illusion.api.errors import AuthenticationFailure, RateLimitFailure
    >>> try:
    >>>     # API 调用
    >>> except AuthenticationFailure as e:
    >>>     print(f"认证失败: {e}")
"""

from __future__ import annotations


class IllusionCodeApiError(RuntimeError):
    """API 异常基类
    
    所有上游 API 失败异常的基类，继承自 RuntimeError。
    用于统一处理来自不同 API 提供商的错误。
    """


class AuthenticationFailure(IllusionCodeApiError):
    """认证失败异常
    
    当上游服务拒绝提供的凭据时抛出此异常。
    可能的原因包括：API 密钥无效、令牌过期、权限不足等。
    """


class RateLimitFailure(IllusionCodeApiError):
    """速率限制异常
    
    当上游服务因请求频率超限而拒绝请求时抛出此异常。
    通常包含重试建议信息。
    """


class RequestFailure(IllusionCodeApiError):
    """请求失败异常
    
    用于通用的请求或传输失败情况。
    可能的原因包括：网络连接错误、服务不可用、超时等。
    """
