"""
记忆路径模块
==========

本模块提供持久化项目记忆的路径管理功能。

主要功能：
    - 生成基于项目路径的唯一记忆目录
    - 管理MEMORY.md入口点文件

函数说明：
    - get_project_memory_dir: 获取项目记忆目录
    - get_memory_entrypoint: 获取记忆入口点文件

使用示例：
    >>> from illusion.memory import get_project_memory_dir, get_memory_entrypoint
    >>> mem_dir = get_project_memory_dir(".")
    >>> entrypoint = get_memory_entrypoint(".")
"""

from __future__ import annotations

from hashlib import sha1
from pathlib import Path

from illusion.config.paths import get_data_dir


def get_project_memory_dir(cwd: str | Path) -> Path:
    """获取项目持久化记忆目录
    
    目录名格式: {项目名}-{sha1哈希前12位}
    使用项目路径的哈希确保唯一性
    
    Args:
        cwd: 当前工作目录
    
    Returns:
        Path: 记忆目录的Path对象
    """
    path = Path(cwd).resolve()  # 解析为绝对路径
    digest = sha1(str(path).encode("utf-8")).hexdigest()[:12]  # 计算哈希
    memory_dir = get_data_dir() / "memory" / f"{path.name}-{digest}"  # 构建目录路径
    memory_dir.mkdir(parents=True, exist_ok=True)  # 创建目录
    return memory_dir  # 返回目录


def get_memory_entrypoint(cwd: str | Path) -> Path:
    """获取项目记忆入口点文件
    
    Args:
        cwd: 当前工作目录
    
    Returns:
        Path: MEMORY.md文件的Path对象
    """
    return get_project_memory_dir(cwd) / "MEMORY.md"  # 返回入口点文件路径