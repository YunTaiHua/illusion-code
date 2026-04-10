"""
Skill 数据模型模块
================

本模块定义 Skill 相关的数据模型。

类说明：
    - SkillDefinition: 已加载的 Skill 数据类
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SkillDefinition:
    """已加载的 Skill。"""

    name: str
    description: str
    content: str
    source: str
    path: str | None = None