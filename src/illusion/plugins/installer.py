"""
插件安装辅助模块
================

本模块提供插件安装和卸载功能。

主要功能：
    - 从路径安装插件到用户插件目录
    - 卸载用户插件

使用示例：
    >>> from illusion.plugins.installer import install_plugin_from_path, uninstall_plugin
    >>> install_plugin_from_path("/path/to/plugin")
    >>> uninstall_plugin("my_plugin")
"""

from __future__ import annotations

import shutil
from pathlib import Path

from illusion.plugins.loader import get_user_plugins_dir


def install_plugin_from_path(source: str | Path) -> Path:
    """安装插件目录到用户插件目录
    
    将源插件目录复制到用户插件目录。
    
    Args:
        source: 插件源目录路径
    
    Returns:
        Path: 安装后的插件目录路径
    """
    src = Path(source).resolve()
    dest = get_user_plugins_dir() / src.name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    return dest


def uninstall_plugin(name: str) -> bool:
    """卸载用户插件
    
    根据目录名称删除用户插件。
    
    Args:
        name: 插件名称（目录名）
    
    Returns:
        bool: 是否成功卸载
    """
    path = get_user_plugins_dir() / name
    if not path.exists():
        return False
    shutil.rmtree(path)
    return True
