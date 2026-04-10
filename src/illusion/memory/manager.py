"""
记忆管理模块
==========

本模块提供记忆文件的管理操作功能。

主要功能：
    - 列出项目记忆文件
    - 添加/移除记忆条目

函数说明：
    - list_memory_files: 列出记忆文件
    - add_memory_entry: 添加记忆条目
    - remove_memory_entry: 移除记忆条目

使用示例：
    >>> from illusion.memory import list_memory_files, add_memory_entry, remove_memory_entry
    >>> files = list_memory_files(".")
    >>> path = add_memory_entry(".", "Test", "# Test memory content")
    >>> remove_memory_entry(".", "test")
"""

from __future__ import annotations

from pathlib import Path
from re import sub

from illusion.memory.paths import get_memory_entrypoint, get_project_memory_dir


def list_memory_files(cwd: str | Path) -> list[Path]:
    """列出项目的所有记忆markdown文件
    
    Args:
        cwd: 当前工作目录
    
    Returns:
        list[Path]: 排序后的记忆文件路径列表
    """
    memory_dir = get_project_memory_dir(cwd)  # 获取记忆目录
    return sorted(path for path in memory_dir.glob("*.md"))  # 返回排序后的文件列表


def add_memory_entry(cwd: str | Path, title: str, content: str) -> Path:
    """创建记忆文件并添加到MEMORY.md索引
    
    Args:
        cwd: 当前工作目录
        title: 记忆标题
        content: 记忆内容
    
    Returns:
        Path: 创建的记忆文件路径
    """
    memory_dir = get_project_memory_dir(cwd)  # 获取记忆目录
    slug = sub(r"[^a-zA-Z0-9]+", "_", title.strip().lower()).strip("_") or "memory"  # 转换为slug
    path = memory_dir / f"{slug}.md"  # 构建文件路径
    path.write_text(content.strip() + "\n", encoding="utf-8")  # 写入内容

    entrypoint = get_memory_entrypoint(cwd)  # 获取入口点
    existing = entrypoint.read_text(encoding="utf-8") if entrypoint.exists() else "# Memory Index\n"  # 读取现有内容
    if path.name not in existing:  # 如果不存在
        existing = existing.rstrip() + f"\n- [{title}]({path.name})\n"  # 添加索引条目
        entrypoint.write_text(existing, encoding="utf-8")  # 写入索引
    return path  # 返回创建的文件路径


def remove_memory_entry(cwd: str | Path, name: str) -> bool:
    """删除记忆文件及其在MEMORY.md中的索引条目
    
    Args:
        cwd: 当前工作目录
        name: 记忆文件名称 (不带.md扩展名)
    
    Returns:
        bool: 是否成功删除
    """
    memory_dir = get_project_memory_dir(cwd)  # 获取记忆目录
    matches = [path for path in memory_dir.glob("*.md") if path.stem == name or path.name == name]  # 查找匹配文件
    if not matches:  # 没有匹配
        return False
    path = matches[0]  # 取第一个匹配
    if path.exists():  # 文件存在
        path.unlink()  # 删除文件

    entrypoint = get_memory_entrypoint(cwd)  # 获取入口点
    if entrypoint.exists():  # 入口点存在
        lines = [
            line  # 保留的行
            for line in entrypoint.read_text(encoding="utf-8").splitlines()
            if path.name not in line  # 排除包含删除文件名的行
        ]
        entrypoint.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")  # 重写入口点
    return True  # 返回成功