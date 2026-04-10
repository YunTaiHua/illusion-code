"""
使用量追踪模块
==============

本模块提供 API 使用量追踪的数据模型。

主要功能：
    - 记录输入/输出令牌数
    - 计算总令牌数

类说明：
    - UsageSnapshot: 模型提供商返回的使用量快照

使用示例：
    >>> from illusion.api.usage import UsageSnapshot
    >>> usage = UsageSnapshot(input_tokens=1000, output_tokens=500)
    >>> print(f"总令牌数: {usage.total_tokens}")
"""

from __future__ import annotations

from pydantic import BaseModel


class UsageSnapshot(BaseModel):
    """模型提供商返回的令牌使用量
    
    记录一次 API 调用消耗的输入和输出令牌数量。
    
    Attributes:
        input_tokens: 输入令牌数量（默认 0）
        output_tokens: 输出令牌数量（默认 0）
    """

    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """返回总令牌数量
        
        Returns:
            int: 输入令牌与输出令牌之和
        """
        return self.input_tokens + self.output_tokens
