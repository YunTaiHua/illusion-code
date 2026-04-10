"""
主题加载工具模块
================

本模块实现主题的加载和管理功能。

主要功能：
    - 获取自定义主题目录
    - 加载自定义主题
    - 列出所有可用主题
    - 按名称加载主题

使用示例：
    >>> from illusion.themes.loader import load_theme, list_themes, load_custom_themes
    >>> themes = list_themes()
    >>> theme = load_theme("dark")
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from illusion.themes.builtin import BUILTIN_THEMES
from illusion.themes.schema import ThemeConfig

logger = logging.getLogger(__name__)


def get_custom_themes_dir() -> Path:
    """获取用户自定义主题目录
    
    Returns:
        Path: 自定义主题目录路径（~/.illusion/themes）
    """
    path = Path.home() / ".illusion" / "themes"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_custom_themes() -> dict[str, ThemeConfig]:
    """从 ~/.illusion/themes/*.json 加载自定义主题
    
    Returns:
        dict[str, ThemeConfig]: 主题名称到配置的字典
    """
    themes: dict[str, ThemeConfig] = {}
    for path in sorted(get_custom_themes_dir().glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            theme = ThemeConfig.model_validate(data)
            themes[theme.name] = theme
        except Exception as exc:
            logger.debug("跳过无效的主题文件 %s: %s", path, exc)
    return themes


def list_themes() -> list[str]:
    """列出所有可用主题的名称（内置 + 自定义）
    
    Returns:
        list[str]: 主题名称列表
    """
    names = list(BUILTIN_THEMES.keys())
    for name in load_custom_themes():
        if name not in names:
            names.append(name)
    return names


def load_theme(name: str) -> ThemeConfig:
    """按名称加载主题
    
    首先查找自定义主题，然后回退到内置主题。
    
    Args:
        name: 主题名称
    
    Returns:
        ThemeConfig: 主题配置对象
    
    Raises:
        KeyError: 如果主题不存在
    """
    custom = load_custom_themes()
    if name in custom:
        return custom[name]
    if name in BUILTIN_THEMES:
        return BUILTIN_THEMES[name]
    raise KeyError(f"Unknown theme: {name!r}. Available: {list_themes()}")
