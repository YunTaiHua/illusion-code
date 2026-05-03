"""
Skill 模块导出
=============

本模块导出 skills 子目录中的公共接口。

导出内容：
    - SkillDefinition: Skill 定义数据类
    - SkillRegistry: Skill 注册表
    - get_user_skills_dir: 用户 skills 目录
    - load_skill_registry: 加载 skill 注册表
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from illusion.skills.registry import SkillRegistry
    from illusion.skills.types import SkillDefinition

__all__ = [
    "SkillDefinition",
    "SkillRegistry",
    "get_project_rules_dir",
    "get_project_skills_dir",
    "get_user_skills_dir",
    "load_skill_registry",
]


def __getattr__(name: str):
    if name in {
        "get_user_skills_dir",
        "get_project_skills_dir",
        "get_project_rules_dir",
        "load_skill_registry",
    }:
        from illusion.skills.loader import (
            get_project_rules_dir,
            get_project_skills_dir,
            get_user_skills_dir,
            load_skill_registry,
        )

        return {
            "get_user_skills_dir": get_user_skills_dir,
            "get_project_skills_dir": get_project_skills_dir,
            "get_project_rules_dir": get_project_rules_dir,
            "load_skill_registry": load_skill_registry,
        }[name]
    if name == "SkillRegistry":
        from illusion.skills.registry import SkillRegistry

        return SkillRegistry
    if name == "SkillDefinition":
        from illusion.skills.types import SkillDefinition

        return SkillDefinition
    raise AttributeError(name)