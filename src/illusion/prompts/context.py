"""
高级系统提示词组装模块
======================

本模块实现运行时系统提示词的组装功能。

主要功能：
    - 构建技能章节
    - 组装包含项目指令和记忆的完整运行时提示词
    - 加载 Claude.md 指令文件

使用示例：
    >>> from illusion.prompts.context import build_runtime_system_prompt
    >>> from illusion.config.settings import Settings
    >>> prompt = build_runtime_system_prompt(settings, cwd="/path/to/project")
"""

from __future__ import annotations

from pathlib import Path

from illusion.config.paths import get_project_issue_file, get_project_pr_comments_file
from illusion.config.settings import Settings
from illusion.memory import find_relevant_memories, load_memory_prompt
from illusion.prompts.claudemd import load_claude_md_prompt
from illusion.prompts.system_prompt import build_system_prompt
from illusion.skills.loader import load_skill_registry


def _build_skills_section(cwd: str | Path) -> str | None:
    """构建技能章节
    
    生成列出可用技能的系统提示词章节。
    
    Args:
        cwd: 工作目录
    
    Returns:
        str | None: 技能章节字符串，如果没有技能则返回 None
    """
    registry = load_skill_registry(cwd)
    skills = registry.list_skills()
    if not skills:
        return None
    lines = [
        "# Available Skills",
        "",
        "The following skills are available via the `skill` tool. "
        "When a user's request matches a skill, invoke it with `skill(name=\"<skill_name>\")` "
        "to load detailed instructions before proceeding.",
        "",
    ]
    for skill in skills:
        lines.append(f"- **{skill.name}**: {skill.description}")
    return "\n".join(lines)


def build_runtime_system_prompt(
    settings: Settings,
    *,
    cwd: str | Path,
    latest_user_prompt: str | None = None,
) -> str:
    """构建运行时系统提示词
    
    组装完整的运行时提示词，包含项目指令和记忆。
    
    Args:
        settings: 设置对象
        cwd: 工作目录
        latest_user_prompt: 最新的用户提示词（用于相关记忆搜索）
    
    Returns:
        str: 完整的运行时系统提示词
    """
    sections = [build_system_prompt(custom_prompt=settings.system_prompt, cwd=str(cwd))]

    # 快速模式
    if settings.fast_mode:
        sections.append(
            "# Session Mode\nFast mode is enabled. Prefer concise replies, minimal tool use, and quicker progress over exhaustive exploration."
        )

    # 推理设置
    sections.append(
        "# Reasoning Settings\n"
        f"- Effort: {settings.effort}\n"
        f"- Passes: {settings.passes}\n"
        "Adjust depth and iteration count to match these settings while still completing the task."
    )

    # 技能章节
    skills_section = _build_skills_section(cwd)
    if skills_section:
        sections.append(skills_section)

    # Claude.md 指令
    claude_md = load_claude_md_prompt(cwd)
    if claude_md:
        sections.append(claude_md)

    # 项目上下文文件
    for title, path in (
        ("Issue Context", get_project_issue_file(cwd)),
        ("Pull Request Comments", get_project_pr_comments_file(cwd)),
    ):
        if path.exists():
            content = path.read_text(encoding="utf-8", errors="replace").strip()
            if content:
                sections.append(f"# {title}\n\n```md\n{content[:12000]}\n```")

    # 记忆功能
    if settings.memory.enabled:
        memory_section = load_memory_prompt(
            cwd,
            max_entrypoint_lines=settings.memory.max_entrypoint_lines,
        )
        if memory_section:
            sections.append(memory_section)

        # 相关记忆
        if latest_user_prompt:
            relevant = find_relevant_memories(
                latest_user_prompt,
                cwd,
                max_results=settings.memory.max_files,
            )
            if relevant:
                lines = ["# Relevant Memories"]
                for header in relevant:
                    content = header.path.read_text(encoding="utf-8", errors="replace").strip()
                    lines.extend(
                        [
                            "",
                            f"## {header.path.name}",
                            "```md",
                            content[:8000],
                            "```",
                        ]
                    )
                sections.append("\n".join(lines))

    return "\n\n".join(section for section in sections if section.strip())
