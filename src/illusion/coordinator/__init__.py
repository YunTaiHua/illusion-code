"""
协调器模块
==========

本模块提供 IllusionCode 团队协调和管理功能。

主要组件：
    - AgentDefinition: 代理定义
    - TeamRecord: 团队记录
    - TeamRegistry: 团队注册表
    - get_builtin_agent_definitions: 获取内置代理定义
    - get_team_registry: 获取团队注册表

使用示例：
    >>> from illusion.coordinator import TeamRegistry, get_team_registry
"""

from illusion.coordinator.agent_definitions import AgentDefinition, get_builtin_agent_definitions
from illusion.coordinator.coordinator_mode import TeamRecord, TeamRegistry, get_team_registry

__all__ = [
    "AgentDefinition",
    "TeamRecord",
    "TeamRegistry",
    "get_builtin_agent_definitions",
    "get_team_registry",
]
