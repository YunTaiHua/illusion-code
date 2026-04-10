"""
记忆提示词模块
=============

本模块提供记忆相关的提示词构建功能。

主要功能：
    - 加载项目记忆提示词段落
    - 格式化记忆目录信息

函数说明：
    - load_memory_prompt: 加载记忆提示词

使用示例：
    >>> from illusion.memory import load_memory_prompt
    >>> prompt = load_memory_prompt(".", max_entrypoint_lines=200)
"""

from __future__ import annotations

from pathlib import Path

from illusion.memory.paths import get_memory_entrypoint, get_project_memory_dir


def load_memory_prompt(cwd: str | Path, *, max_entrypoint_lines: int = 200) -> str | None:
    """构建当前项目的记忆提示词段落
    
    Args:
        cwd: 当前工作目录
        max_entrypoint_lines: 入口点文件最大行数
    
    Returns:
        str | None: 格式化后的记忆提示词，如果失败返回None
    """
    memory_dir = get_project_memory_dir(cwd)  # 获取记忆目录
    entrypoint = get_memory_entrypoint(cwd)  # 获取入口点文件
    lines = [
        "# Memory",  # 标题
        f"- Persistent memory directory: {memory_dir}",  # 记忆目录
        "- Use this directory to store durable user or project context that should survive future sessions.",  # 说明1
        "- Prefer concise topic files plus an index entry in MEMORY.md.",  # 说明2
    ]

    if entrypoint.exists():  # 入口点文件存在
        content_lines = entrypoint.read_text(encoding="utf-8").splitlines()[:max_entrypoint_lines]  # 读取内容
        if content_lines:  # 有内容
            lines.extend(["", "## MEMORY.md", "```md", *content_lines, "```"])  # 添加到提示词
    else:  # 入口点不存在
        lines.extend(
            [
                "",  # 空行
                "## MEMORY.md",  # 标题
                "(not created yet)",  # 提示未创建
            ]
        )

    return "\n".join(lines)  # 返回合并后的字符串