"""
状态管理模块
============

本模块提供 IllusionCode 应用状态管理功能。

主要组件：
    - AppState: 应用状态
    - AppStateStore: 应用状态存储

使用示例：
    >>> from illusion.state import AppState, AppStateStore
"""

from illusion.state.app_state import AppState
from illusion.state.store import AppStateStore

__all__ = ["AppState", "AppStateStore"]
