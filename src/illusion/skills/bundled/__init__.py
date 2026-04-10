"""
内置 Skill 定义模块
==================

本模块从 .md 文件加载内置 skill 定义。

主要功能：
    - 从 content 目录加载所有内置 skills
    - 解析 Markdown 文件的前 matter

类说明：
    - get_bundled_skills: 加载所有内置 skills

使用示例：
    >>> from illusion.skills.bundled import get_bundled_skills
    >>> # 加载内置 skills
    >>> skills = get_bundled_skills()
"""

from __future__ import annotations

from pathlib import Path

from illusion.skills.types import SkillDefinition

# 内置 skill 内容目录
_CONTENT_DIR = Path(__file__).parent / "content"


def get_bundled_skills() -> list[SkillDefinition]:
    """从 content 目录加载所有内置 skills。"""
    skills: list[SkillDefinition] = []
    if not _CONTENT_DIR.exists():
        return skills
    for path in sorted(_CONTENT_DIR.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        name, description = _parse_frontmatter(path.stem, content)
        skills.append(
            SkillDefinition(
                name=name,
                description=description,
                content=content,
                source="bundled",
                path=str(path),
            )
        )
    return skills


def _parse_frontmatter(default_name: str, content: str) -> tuple[str, str]:
    """从 skill markdown 文件中提取名称和描述。

    支持 YAML frontmatter（--- 分隔），并回退到标题/段落解析。
    """
    name = default_name
    description = ""
    lines = content.splitlines()

    # 先尝试 YAML frontmatter
    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                for fm_line in lines[1:i]:
                    fm = fm_line.strip()
                    if fm.startswith("name:"):
                        val = fm[5:].strip().strip("'\"")
                        if val:
                            name = val
                    elif fm.startswith("description:"):
                        val = fm[12:].strip().strip("'\"")
                        if val:
                            description = val
                break
        if description:
            return name, description

    # 回退：标题 + 第一段
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# "):
            name = stripped[2:].strip() or default_name
            continue
        if stripped and not stripped.startswith("---") and not stripped.startswith("#"):
            description = stripped[:200]
            break
    return name, description or f"Bundled skill: {name}"