"""
记忆模块
========

本模块提供 IllusionCode 记忆/上下文管理功能。

主要组件：
    - add_memory_entry: 添加记忆条目
    - find_relevant_memories: 查找相关记忆
    - get_memory_entrypoint: 获取记忆入口点
    - get_project_memory_dir: 获取项目记忆目录
    - list_memory_files: 列出记忆文件
    - load_memory_prompt: 加载记忆提示词
    - remove_memory_entry: 移除记忆条目
    - scan_memory_files: 扫描记忆文件

使用示例：
    >>> from illusion.memory import add_memory_entry, find_relevant_memories
"""

from illusion.memory.memdir import load_memory_prompt
from illusion.memory.manager import add_memory_entry, list_memory_files, remove_memory_entry
from illusion.memory.paths import get_memory_entrypoint, get_project_memory_dir
from illusion.memory.scan import scan_memory_files
from illusion.memory.search import find_relevant_memories

__all__ = [
    "add_memory_entry",
    "find_relevant_memories",
    "get_memory_entrypoint",
    "get_project_memory_dir",
    "list_memory_files",
    "load_memory_prompt",
    "remove_memory_entry",
    "scan_memory_files",
]
