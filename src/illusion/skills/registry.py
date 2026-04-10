"""
Skill 注册表模块
================

本模块提供 Skill 注册表功能，按名称存储已加载的 skills。

类说明：
    - SkillRegistry: 按名称存储已加载的 skills

使用示例：
    >>> from illusion.skills import SkillRegistry
    >>> registry = SkillRegistry()
    >>> # 注册 skill
    >>> registry.register(skill_definition)
    >>> # 获取 skill
    >>> skill = registry.get("my_skill")
"""

from __future__ import annotations

from illusion.skills.types import SkillDefinition


class SkillRegistry:
    """按名称存储已加载的 skills。"""

    def __init__(self) -> None:
        self._skills: dict[str, SkillDefinition] = {}

    def register(self, skill: SkillDefinition) -> None:
        """注册一个 skill。"""
        self._skills[skill.name] = skill

    def get(self, name: str) -> SkillDefinition | None:
        """按名称返回 skill。"""
        return self._skills.get(name)

    def list_skills(self) -> list[SkillDefinition]:
        """返回所有 skills，按名称排序。"""
        return sorted(self._skills.values(), key=lambda skill: skill.name)