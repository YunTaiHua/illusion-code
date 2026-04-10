"""
主题系统模块
============

本模块提供 IllusionCode 主题系统的加载和管理功能。

主要组件：
    - ThemeConfig: 主题配置
    - BorderConfig: 边框配置
    - ColorsConfig: 颜色配置
    - IconConfig: 图标配置
    - LayoutConfig: 布局配置
    - list_themes: 列出主题
    - load_custom_themes: 加载自定义主题
    - load_theme: 加载主题

使用示例：
    >>> from illusion.themes import list_themes, load_theme
"""

from illusion.themes.loader import list_themes, load_custom_themes, load_theme
from illusion.themes.schema import (
    BorderConfig,
    ColorsConfig,
    IconConfig,
    LayoutConfig,
    ThemeConfig,
)

__all__ = [
    "BorderConfig",
    "ColorsConfig",
    "IconConfig",
    "LayoutConfig",
    "ThemeConfig",
    "list_themes",
    "load_custom_themes",
    "load_theme",
]
