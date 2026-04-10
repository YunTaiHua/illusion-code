"""
运行时钩子结果类型
==================

本模块定义钩子执行后的结果类型，包括单个钩子结果和聚合结果。

主要类型：
    - HookResult: 单个钩子的执行结果
    - AggregatedHookResult: 多个钩子结果的聚合

使用示例：
    >>> from illusion.hooks.types import HookResult, AggregatedHookResult
    >>> result = HookResult(hook_type="command", success=True, output="done")
    >>> aggregated = AggregatedHookResult(results=[result])
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class HookResult:
    """
    单个钩子执行结果
    
    存储一个钩子执行后的状态和输出信息。
    
    Attributes:
        hook_type: 钩子类型（command/prompt/http/agent）
        success: 是否成功执行
        output: 钩子输出内容
        blocked: 是否阻止继续执行
        reason: 阻止原因（当 blocked 为 True 时）
        metadata: 附加元数据字典
    """

    hook_type: str  # 钩子类型标识
    success: bool  # 执行是否成功
    output: str = ""  # 钩子输出内容
    blocked: bool = False  # 是否阻止后续操作
    reason: str = ""  # 阻止原因描述
    metadata: dict[str, Any] = field(default_factory=dict)  # 额外元数据


@dataclass(frozen=True)
class AggregatedHookResult:
    """
    聚合钩子结果
    
    聚合多个钩子的执行结果，提供统一的 blocked 和 reason 属性。
    
    Attributes:
        results: 钩子结果列表
    
    使用示例：
        >>> aggregated = AggregatedHookResult(results=[result1, result2])
        >>> if aggregated.blocked:
        ...     print(aggregated.reason)
    """

    results: list[HookResult] = field(default_factory=list)  # 钩子结果列表

    @property
    def blocked(self) -> bool:
        """
        检查是否有任何钩子阻止继续执行
        
        Returns:
            bool: 如果任意一个钩子 blocked 为 True，返回 True
        """
        return any(result.blocked for result in self.results)

    @property
    def reason(self) -> str:
        """
        获取第一个阻止原因
        
        Returns:
            str: 第一个 blocked=True 的钩子的 reason，如果没有则返回空字符串
        """
        for result in self.results:
            if result.blocked:
                return result.reason or result.output
        return ""