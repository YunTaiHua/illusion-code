"""
Skill 加载模块 — 从内置和用户目录加载 Skills
=========================================

本模块提供从内置目录和用户配置目录加载 Skills 的功能。

主要功能：
    - 获取用户 skills 目录
    - 加载 skill 注册表
    - 加载用户 skills
    - 解析 skill markdown 文件

类说明：
    - get_user_skills_dir: 获取用户 skills 目录
    - load_skill_registry: 加载内置和用户定义的 skills
    - load_user_skills: 从用户配置目录加载 markdown skills

使用示例：
    >>> from illusion.skills.loader import get_user_skills_dir, load_skill_registry
    >>> # 获取用户 skills 目录
    >>> skills_dir = get_user_skills_dir()
    >>> # 加载 skill 注册表
    >>> registry = load_skill_registry(cwd="/path/to/project")
"""

from __future__ import annotations

from pathlib import Path

from illusion.config.paths import get_config_dir, get_project_config_dir
from illusion.config.settings import load_settings
from illusion.skills.bundled import get_bundled_skills
from illusion.skills.registry import SkillRegistry
from illusion.skills.types import SkillDefinition


def get_user_skills_dir() -> Path:
    """返回用户 skills 目录。"""
    path = get_config_dir() / "skills"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_project_skills_dir(cwd: str | Path) -> Path:
    """返回项目级 skills 目录（.illusion/skills/）。"""
    path = get_project_config_dir(cwd) / "skills"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_project_rules_dir(cwd: str | Path) -> Path:
    """返回项目级 rules 目录（.illusion/rules/）。"""
    path = get_project_config_dir(cwd) / "rules"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_skill_registry(cwd: str | Path | None = None) -> SkillRegistry:
    """加载内置和用户定义的 skills。"""
    registry = SkillRegistry()
    # 注册内置 skills
    for skill in get_bundled_skills():
        registry.register(skill)
    # 注册用户 skills
    for skill in load_user_skills():
        registry.register(skill)
    # 如果提供了工作目录，加载项目级 skills 和插件 skills
    if cwd is not None:
        # 项目级 skills（同名时覆盖全局）
        for skill in load_project_skills(cwd):
            registry.register(skill)
        from illusion.plugins.loader import load_plugins

        settings = load_settings()
        for plugin in load_plugins(settings, cwd):
            if not plugin.enabled:
                continue
            for skill in plugin.skills:
                registry.register(skill)
    return registry


def load_user_skills() -> list[SkillDefinition]:
    """从用户配置目录加载 markdown skills。"""
    skills: list[SkillDefinition] = []
    for path in sorted(get_user_skills_dir().glob("*.md")):
        content = path.read_text(encoding="utf-8")
        name, description = _parse_skill_markdown(path.stem, content)
        skills.append(
            SkillDefinition(
                name=name,
                description=description,
                content=content,
                source="user",
                path=str(path),
            )
        )
    return skills


def load_project_skills(cwd: str | Path) -> list[SkillDefinition]:
    """从项目目录加载 markdown skills。

    目录结构: <project>/.illusion/skills/<skill_name>/<skill_name>.md
    """
    skills: list[SkillDefinition] = []
    skills_dir = get_project_skills_dir(cwd)
    for sub in sorted(skills_dir.iterdir()):
        if not sub.is_dir():
            continue
        for path in sorted(sub.glob("*.md")):
            content = path.read_text(encoding="utf-8")
            name, description = _parse_skill_markdown(path.stem, content)
            skills.append(
                SkillDefinition(
                    name=name,
                    description=description,
                    content=content,
                    source="project",
                    path=str(path),
                )
            )
    return skills


def _parse_skill_markdown(default_name: str, content: str) -> tuple[str, str]:
    """解析 skill markdown 文件的名称和描述，支持 YAML frontmatter。"""
    name = default_name
    description = ""

    lines = content.splitlines()

    # 先尝试 YAML frontmatter（--- ... ---）
    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                # 解析 frontmatter 字段
                for fm_line in lines[1:i]:
                    fm_stripped = fm_line.strip()
                    if fm_stripped.startswith("name:"):
                        val = fm_stripped[5:].strip().strip("'\"")
                        if val:
                            name = val
                    elif fm_stripped.startswith("description:"):
                        val = fm_stripped[12:].strip().strip("'\"")
                        if val:
                            description = val
                break

    # 回退：从标题和第一段提取
    if not description:
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("# "):
                if not name or name == default_name:
                    name = stripped[2:].strip() or default_name
                continue
            if stripped and not stripped.startswith("---") and not stripped.startswith("#"):
                description = stripped[:200]
                break

    if not description:
        description = f"Skill: {name}"
    return name, description