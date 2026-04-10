"""
从配置加载按键绑定模块
======================

本模块实现从配置文件加载按键绑定的功能。

主要功能：
    - 获取用户按键绑定文件路径
    - 加载并合并按键绑定配置

使用示例：
    >>> from illusion.keybindings.loader import get_keybindings_path, load_keybindings
    >>> path = get_keybindings_path()
    >>> bindings = load_keybindings()
"""

from __future__ import annotations

from pathlib import Path

from illusion.config.paths import get_config_dir
from illusion.keybindings.parser import parse_keybindings
from illusion.keybindings.resolver import resolve_keybindings


def get_keybindings_path() -> Path:
    """获取用户按键绑定文件路径
    
    Returns:
        Path: 配置文件路径（~/.illusion/keybindings.json）
    """
    return get_config_dir() / "keybindings.json"


def load_keybindings() -> dict[str, str]:
    """加载并合并按键绑定
    
    如果配置文件存在则加载用户配置，否则使用默认配置。
    
    Returns:
        dict[str, str]: 按键到动作的映射字典
    """
    path = get_keybindings_path()
    if not path.exists():
        return resolve_keybindings()
    return resolve_keybindings(parse_keybindings(path.read_text(encoding="utf-8")))
