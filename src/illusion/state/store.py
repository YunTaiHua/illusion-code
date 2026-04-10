"""
状态存储模块
===========

本模块实现可观察的应用状态存储容器。

主要功能：
    - 提供响应式状态管理
    - 支持状态变更监听和通知

类说明：
    - AppStateStore: 应用状态存储容器
    - Listener: 状态监听器类型

使用示例：
    >>> from illusion.state import AppState, AppStateStore
    >>> store = AppStateStore(AppState(model="claude", permission_mode="default", theme="default"))
    >>> state = store.get()
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from illusion.state.app_state import AppState


# 状态监听器类型别名：接收AppState并返回None的Callable
Listener = Callable[[AppState], None]


class AppStateStore:
    """可观察的应用状态存储容器
    
    提供 immutable 风格的状态更新，通过监听器模式通知状态变更。
    
    Attributes:
        _state: 当前的应用状态快照
        _listeners: 注册的状态监听器列表
    
    Example:
        >>> store = AppStateStore(initial_state)
        >>> store.subscribe(lambda state: print(f"State changed: {state.model}"))
        >>> store.set(model="new-model")  # 触发所有监听器
    """

    def __init__(self, initial_state: AppState) -> None:
        """初始化状态存储容器
        
        Args:
            initial_state: 初始的应用状态
        """
        self._state = initial_state  # 内部状态存储
        self._listeners: list[Listener] = []  # 监听器列表初始化

    def get(self) -> AppState:
        """获取当前状态的快照
        
        Returns:
            AppState: 当前应用状态的副本
        """
        return self._state  # 返回当前状态

    def set(self, **updates) -> AppState:
        """更新状态并通知所有监听器
        
        Keyword Args:
            updates: 要更新的状态属性
        Returns:
            AppState: 更新后的新状态
        """
        self._state = replace(self._state, **updates)  # 使用dataclasses.replace创建新状态
        for listener in list(self._listeners):  # 通知所有监听器
            listener(self._state)
        return self._state  # 返回更新后的状态

    def subscribe(self, listener: Listener) -> Callable[[], None]:
        """注册状态监听器并返回取消订阅的回调函数
        
        Args:
            listener: 状态变更时调用的监听器函数
        Returns:
            Callable[[], None]: 用于取消订阅的回调函数
        """
        self._listeners.append(listener)  # 添加监听器

        def _unsubscribe() -> None:
            """取消订阅的内部函数"""
            if listener in self._listeners:  # 检查监听器是否存在
                self._listeners.remove(listener)  # 移除监听器

        return _unsubscribe  # 返回取消订阅函数