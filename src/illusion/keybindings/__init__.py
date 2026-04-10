"""
按键绑定模块
============

本模块提供 IllusionCode 按键绑定的解析和管理功能。

主要组件：
    - DEFAULT_KEYBINDINGS: 默认按键绑定
    - get_keybindings_path: 获取按键绑定文件路径
    - load_keybindings: 加载按键绑定
    - parse_keybindings: 解析按键绑定
    - resolve_keybindings: 解析按键绑定

使用示例：
    >>> from illusion.keybindings import DEFAULT_KEYBINDINGS, load_keybindings
"""

from illusion.keybindings.default_bindings import DEFAULT_KEYBINDINGS
from illusion.keybindings.loader import get_keybindings_path, load_keybindings
from illusion.keybindings.parser import parse_keybindings
from illusion.keybindings.resolver import resolve_keybindings

__all__ = [
    "DEFAULT_KEYBINDINGS",
    "get_keybindings_path",
    "load_keybindings",
    "parse_keybindings",
    "resolve_keybindings",
]
