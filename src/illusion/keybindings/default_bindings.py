"""
默认按键绑定定义模块
====================

本模块定义 IllusionCode 的默认按键绑定。

主要功能：
    - 定义控制台快捷键映射
    - 提供默认的按键行为配置

使用示例：
    >>> from illusion.keybindings.default_bindings import DEFAULT_KEYBINDINGS
    >>> DEFAULT_KEYBINDINGS["ctrl+l"]
"""

from __future__ import annotations


DEFAULT_KEYBINDINGS: dict[str, str] = {
    "ctrl+l": "clear",  # 清除屏幕
    "ctrl+x": "stop",  # 停止当前操作
    "ctrl+t": "tasks",  # 显示任务列表
}
