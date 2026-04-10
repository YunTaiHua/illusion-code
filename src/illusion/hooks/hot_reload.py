"""
钩子热重载模块
==============

本模块提供基于设置文件的热重载功能，当设置文件发生变化时自动重新加载钩子。

主要组件：
    - HookReloader: 钩子定义热重载器

使用示例：
    >>> from pathlib import Path
    >>> from illusion.hooks.hot_reload import HookReloader
    >>> reloader = HookReloader(Path("settings.yaml"))
    >>> registry = reloader.current_registry()
"""

from __future__ import annotations

from pathlib import Path

from illusion.config import load_settings
from illusion.hooks.loader import HookRegistry, load_hook_registry


class HookReloader:
    """
    钩子热重载器
    
    监控设置文件变化，在文件修改时自动重新加载钩子注册表。
    
    Attributes:
        _settings_path: 设置文件路径
        _last_mtime_ns: 上次文件修改时间（纳秒）
        _registry: 当前钩子注册表
    
    使用示例：
        >>> reloader = HookReloader(Path("settings.yaml"))
        >>> registry = reloader.current_registry()
    """

    def __init__(self, settings_path: Path) -> None:
        self._settings_path = settings_path  # 设置文件路径
        self._last_mtime_ns = -1  # 初始为无效时间戳
        self._registry = HookRegistry()  # 初始空注册表

    def current_registry(self) -> HookRegistry:
        """
        获取当前注册表，必要时重新加载
        
        检查设置文件的修改时间，如果发生变化则重新加载钩子。
        
        Returns:
            HookRegistry: 当前的钩子注册表
        
        注意：
            - 如果文件不存在，返回空注册表
            - 只有当文件修改时间变化时才重新加载
        """
        try:
            # 获取文件状态信息
            stat = self._settings_path.stat()
        except FileNotFoundError:
            # 文件不存在时，重置注册表
            self._registry = HookRegistry()
            self._last_mtime_ns = -1
            return self._registry

        # 检查文件是否被修改
        if stat.st_mtime_ns != self._last_mtime_ns:
            self._last_mtime_ns = stat.st_mtime_ns  # 更新修改时间
            # 重新加载设置并构建注册表
            self._registry = load_hook_registry(load_settings(self._settings_path))
        
        return self._registry  # 返回当前注册表