"""
按键绑定解析模块
================

本模块实现按键绑定的解析和合并功能。

主要功能：
    - 将用户覆盖与默认按键绑定合并
    - 允许用户自定义快捷键行为

使用示例：
    >>> from illusion.keybindings.resolver import resolve_keybindings
    >>> bindings = resolve_keybindings({"ctrl+l": "custom_action"})
"""

from __future__ import annotations

from illusion.keybindings.default_bindings import DEFAULT_KEYBINDINGS


def resolve_keybindings(overrides: dict[str, str] | None = None) -> dict[str, str]:
    """合并用户覆盖到默认按键绑定
    
    Args:
        overrides: 用户自定义的按键绑定覆盖
    
    Returns:
        dict[str, str]: 合并后的完整按键绑定字典
    """
    resolved = dict(DEFAULT_KEYBINDINGS)
    if overrides:
        resolved.update(overrides)
    return resolved
