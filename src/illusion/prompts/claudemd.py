"""
CLAUDE.md 发现和加载模块
========================

本模块实现 CLAUDE.md 指令文件的发现和加载功能。

主要功能：
    - 从当前目录向上查找 CLAUDE.md 文件
    - 发现 .claude/rules 目录下的规则文件
    - 将多个指令文件加载为一个提示词章节

使用示例：
    >>> from illusion.prompts.claudemd import discover_claude_md_files, load_claude_md_prompt
    >>> files = discover_claude_md_files("/path/to/project")
    >>> prompt = load_claude_md_prompt("/path/to/project")
"""

from __future__ import annotations

from pathlib import Path


def discover_claude_md_files(cwd: str | Path) -> list[Path]:
    """发现相关的 CLAUDE.md 指令文件
    
    从当前工作目录向上查找所有 CLAUDE.md 和规则文件。
    
    Args:
        cwd: 工作目录
    
    Returns:
        list[Path]: 找到的指令文件路径列表
    """
    current = Path(cwd).resolve()
    results: list[Path] = []
    seen: set[Path] = set()

    for directory in [current, *current.parents]:
        for candidate in (
            directory / "CLAUDE.md",
            directory / ".claude" / "CLAUDE.md",
        ):
            if candidate.exists() and candidate not in seen:
                results.append(candidate)
                seen.add(candidate)

        # .claude/rules 目录下的规则文件
        rules_dir = directory / ".claude" / "rules"
        if rules_dir.is_dir():
            for rule in sorted(rules_dir.glob("*.md")):
                if rule not in seen:
                    results.append(rule)
                    seen.add(rule)

        if directory.parent == directory:
            break

    return results


def load_claude_md_prompt(cwd: str | Path, *, max_chars_per_file: int = 12000) -> str | None:
    """将发现的指令文件加载为一个提示词章节
    
    Args:
        cwd: 工作目录
        max_chars_per_file: 每个文件的最大字符数
    
    Returns:
        str | None: 格式化的提示词章节，如果没有文件则返回 None
    """
    files = discover_claude_md_files(cwd)
    if not files:
        return None

    lines = ["# Project Instructions"]
    for path in files:
        content = path.read_text(encoding="utf-8", errors="replace")
        if len(content) > max_chars_per_file:
            content = content[:max_chars_per_file] + "\n...[truncated]..."
        lines.extend(["", f"## {path}", "```md", content.strip(), "```"])
    return "\n".join(lines)
