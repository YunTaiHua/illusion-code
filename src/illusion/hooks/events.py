"""
钩子事件定义模块
================

本模块定义 IllusionCode 支持的钩子事件类型。

支持的事件：
    - SESSION_START: 会话开始时触发
    - SESSION_END: 会话结束时触发
    - PRE_TOOL_USE: 工具使用前触发
    - POST_TOOL_USE: 工具使用后触发

使用示例：
    >>> from illusion.hooks.events import HookEvent
    >>> event = HookEvent.PRE_TOOL_USE
"""

from __future__ import annotations

from enum import Enum


class HookEvent(str, Enum):
    """
    钩子事件枚举
    
    定义可以触发钩子的所有事件类型。
    
    枚举值：
        SESSION_START: 会话开始事件
        SESSION_END: 会话结束事件
        PRE_TOOL_USE: 工具使用前事件
        POST_TOOL_USE: 工具使用后事件
    
    使用示例：
        >>> event = HookEvent.PRE_TOOL_USE
        >>> print(event.value)  # 输出: "pre_tool_use"
    """

    SESSION_START = "session_start"  # 会话开始
    SESSION_END = "session_end"  # 会话结束
    PRE_TOOL_USE = "pre_tool_use"  # 工具使用前
    POST_TOOL_USE = "post_tool_use"  # 工具使用后