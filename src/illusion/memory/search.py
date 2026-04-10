"""
记忆搜索模块
===========

本模块提供基于启发式的记忆文件搜索功能。

主要功能：
    - 支持多语言token提取 (ASCII + 汉字)
    - 根据元数据和内容相关性评分排序

函数说明：
    - find_relevant_memories: 查找相关记忆文件
    - _tokenize: 提取搜索token

使用示例：
    >>> from illusion.memory import find_relevant_memories
    >>> results = find_relevant_memories("测试查询", cwd=".", max_results=5)
"""

from __future__ import annotations

import re
from pathlib import Path

from illusion.memory.scan import scan_memory_files
from illusion.memory.types import MemoryHeader


def find_relevant_memories(
    query: str,
    cwd: str | Path,
    *,
    max_results: int = 5,
) -> list[MemoryHeader]:
    """查找与查询相关的记忆文件
    
    评分权重：元数据匹配 2x，body内容匹配 1x，确保标注良好的记忆优先返回。
    
    Args:
        query: 搜索查询字符串
        cwd: 当前工作目录
        max_results: 最大返回结果数量
    
    Returns:
        list[MemoryHeader]: 按相关性排序的记忆文件列表
    """
    tokens = _tokenize(query)  # 提取搜索token
    if not tokens:  # 无有效token则返回空列表
        return []

    scored: list[tuple[float, MemoryHeader]] = []  # 评分结果列表
    for header in scan_memory_files(cwd, max_files=100):  # 扫描记忆文件
        meta = f"{header.title} {header.description}".lower()  # 元数据文本
        body = header.body_preview.lower()  # 内容预览文本

        # 元数据匹配权重2x，内容匹配权重1x
        meta_hits = sum(1 for t in tokens if t in meta)  # 元数据命中数
        body_hits = sum(1 for t in tokens if t in body)  # body命中数
        score = meta_hits * 2.0 + body_hits  # 计算总分
        if score > 0:  # 有匹配则加入评分列表
            scored.append((score, header))

    scored.sort(key=lambda item: (-item[0], -item[1].modified_at))  # 按分数和时间排序
    return [header for _, header in scored[:max_results]]  # 返回Top N结果


def _tokenize(text: str) -> set[str]:
    """从文本中提取搜索token，同时处理ASCII和汉字
    
    - ASCII单词token (3字符及以上)
    - 汉字单字 (每个汉字独立表示含义)
    
    Args:
        text: 输入文本
    
    Returns:
        set[str]: token集合
    """
    # ASCII单词token (3+字符)
    ascii_tokens = {t for t in re.findall(r"[A-Za-z0-9_]+", text.lower()) if len(t) >= 3}
    # 汉字字符 (每个字符独立表达含义)
    han_chars = set(re.findall(r"[\u4e00-\u9fff\u3400-\u4dbf]", text))
    return ascii_tokens | han_chars  # 返回合并后的token集合