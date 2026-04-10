"""
按键绑定文件解析模块
====================

本模块实现按键绑定文件的 JSON 解析功能。

主要功能：
    - 解析 JSON 格式的按键绑定映射
    - 验证按键绑定的键值类型

使用示例：
    >>> from illusion.keybindings.parser import parse_keybindings
    >>> bindings = parse_keybindings('{"ctrl+l": "clear"}')
"""

from __future__ import annotations

import json


def parse_keybindings(text: str) -> dict[str, str]:
    """解析 JSON 按键绑定映射
    
    Args:
        text: JSON 格式的按键绑定文本
    
    Returns:
        dict[str, str]: 按键到动作的映射字典
    
    Raises:
        ValueError: 如果格式不正确
    """
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("keybindings file must be a JSON object")
    parsed: dict[str, str] = {}
    for key, value in data.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("keybindings keys and values must be strings")
        parsed[key] = value
    return parsed
