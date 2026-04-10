"""
Permission Store 权限存储模块
=====================

本模块实现工作空间本地的"总是允许"工具权限持久化存储。

主要功能：
    - 从工作空间加载"总是允许"的工具列表
    - 保存"总是允许"的工具列表到工作空间
    - 添加单个工具到"总是允许"列表

使用示例：
    >>> from illusion.ui.permission_store import load_always_allowed_tools, save_always_allowed_tools, add_always_allowed_tool
    >>> 
    >>> # 加载工具列表
    >>> tools = load_always_allowed_tools("/path/to/workspace")
    >>> 
    >>> # 添加工具
    >>> tools = add_always_allowed_tool("/path/to/workspace", "Bash")
"""

from __future__ import annotations

import json
from pathlib import Path

# 权限文件路径：.illusion/permissions.json
_PERMISSIONS_PATH = Path(".illusion") / "permissions.json"


def _file_path(cwd: str | Path) -> Path:
    """获取权限文件的完整路径。

    Args:
        cwd: 工作目录路径

    Returns:
        Path: 权限文件的完整路径
    """
    return Path(cwd).resolve() / _PERMISSIONS_PATH


def load_always_allowed_tools(cwd: str | Path) -> set[str]:
    """从工作空间权限文件加载"总是允许"的工具列表。

    Args:
        cwd: 工作目录路径

    Returns:
        set[str]: "总是允许"的工具名称集合
    """
    path = _file_path(cwd)
    if not path.exists():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    tools = payload.get("always_allow_tools", [])
    if not isinstance(tools, list):
        return set()
    return {str(item).strip() for item in tools if str(item).strip()}


def save_always_allowed_tools(cwd: str | Path, tools: set[str]) -> None:
    """将"总是允许"的工具列表持久化到工作空间权限文件。

    Args:
        cwd: 工作目录路径
        tools: "总是允许"的工具名称集合
    """
    path = _file_path(cwd)
    # 创建父目录（如果不存在）
    path.parent.mkdir(parents=True, exist_ok=True)
    # 序列化并写入文件
    payload = {"always_allow_tools": sorted({tool.strip() for tool in tools if tool.strip()})}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def add_always_allowed_tool(cwd: str | Path, tool_name: str) -> set[str]:
    """将一个工具添加到工作空间"总是允许"权限列表并持久化。

    Args:
        cwd: 工作目录路径
        tool_name: 工具名称

    Returns:
        set[str]: 更新后的"总是允许"工具集合
    """
    # 加载现有工具列表
    tools = load_always_allowed_tools(cwd)
    name = tool_name.strip()
    if not name:
        return tools
    # 添加新工具
    tools.add(name)
    # 保存更新后的列表
    save_always_allowed_tools(cwd, tools)
    return tools