"""
记忆数据类型模块
==============

本模块定义 IllusionCode 记忆系统的数据类型。

主要功能：
    - 定义记忆文件的元数据结构
    - 支持 YAML frontmatter 解析

类说明：
    - MemoryHeader: 记忆文件元数据

使用示例：
    >>> from illusion.memory import MemoryHeader
    >>> header = MemoryHeader(path=Path("test.md"), title="Test", description="A test", modified_at=1234567890.0)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MemoryHeader:
    """记忆文件的元数据信息
    
    Attributes:
        path: 记忆文件的路径
        title: 记忆文件标题
        description: 记忆文件描述
        modified_at: 最后修改时间戳
        memory_type: 记忆类型 (可选)
        body_preview: 内容预览文本 (可选)
    """

    path: Path  # 记忆文件路径
    title: str  # 标题
    description: str  # 描述
    modified_at: float  # 修改时间戳
    memory_type: str = ""  # 记忆类型
    body_preview: str = ""  # 内容预览