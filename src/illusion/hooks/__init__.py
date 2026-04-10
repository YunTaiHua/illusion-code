"""
钩子模块
========

本模块提供 IllusionCode 钩子系统功能。

主要组件：
    - HookEvent: 钩子事件
    - HookExecutionContext: 钩子执行上下文
    - HookExecutor: 钩子执行器
    - HookRegistry: 钩子注册表
    - HookResult: 钩子结果
    - AggregatedHookResult: 聚合钩子结果
    - load_hook_registry: 加载钩子注册表

使用示例：
    >>> from illusion.hooks import HookRegistry, HookExecutor
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from illusion.hooks.events import HookEvent
    from illusion.hooks.executor import HookExecutionContext, HookExecutor
    from illusion.hooks.loader import HookRegistry
    from illusion.hooks.types import AggregatedHookResult, HookResult

__all__ = [
    "AggregatedHookResult",
    "HookEvent",
    "HookExecutionContext",
    "HookExecutor",
    "HookRegistry",
    "HookResult",
    "load_hook_registry",
]


def __getattr__(name: str):
    if name == "HookEvent":
        from illusion.hooks.events import HookEvent

        return HookEvent
    if name in {"HookExecutionContext", "HookExecutor"}:
        from illusion.hooks.executor import HookExecutionContext, HookExecutor

        return {
            "HookExecutionContext": HookExecutionContext,
            "HookExecutor": HookExecutor,
        }[name]
    if name in {"HookRegistry", "load_hook_registry"}:
        from illusion.hooks.loader import HookRegistry, load_hook_registry

        return {
            "HookRegistry": HookRegistry,
            "load_hook_registry": load_hook_registry,
        }[name]
    if name in {"AggregatedHookResult", "HookResult"}:
        from illusion.hooks.types import AggregatedHookResult, HookResult

        return {
            "AggregatedHookResult": AggregatedHookResult,
            "HookResult": HookResult,
        }[name]
    raise AttributeError(name)
