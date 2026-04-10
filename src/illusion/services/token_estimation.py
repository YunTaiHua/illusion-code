"""
简单 Token 估算工具
================

本模块提供简单的 Token 估算功能，使用基于字符的启发式方法。

主要功能：
    - 估算单个文本的 Token 数量
    - 估算消息列表的总 Token 数量

使用示例：
    >>> from illusion.services.token_estimation import estimate_tokens
    >>> # 估算文本 Token 数
    >>> tokens = estimate_tokens("Hello, world!")
    >>> print(tokens)  # 输出约 4
"""

from __future__ import annotations


def estimate_tokens(text: str) -> int:
    """使用粗略字符启发式方法估算纯文本的 Token 数。"""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def estimate_message_tokens(messages: list[str]) -> int:
    """估算消息字符串集合的 Token 总数。"""
    return sum(estimate_tokens(message) for message in messages)