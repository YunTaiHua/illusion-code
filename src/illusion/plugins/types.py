"""
插件运行时类型模块
==================

本模块定义插件运行时使用的类型。

主要组件：
    - LoadedPlugin: 已加载的插件

使用示例：
    >>> from illusion.plugins.types import LoadedPlugin
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from illusion.mcp.types import McpServerConfig
from illusion.plugins.schemas import PluginManifest
from illusion.skills.types import SkillDefinition


@dataclass(frozen=True)
class LoadedPlugin:
    """已加载的插件及其贡献的内容
    
    表示一个已加载的插件，包含清单、路径、启用状态、技能、钩子等。
    
    Attributes:
        manifest: 插件清单
        path: 插件目录路径
        enabled: 是否启用
        skills: 技能定义列表
        hooks: 钩子字典
        mcp_servers: MCP 服务器配置字典
        commands: 命令技能列表
    """

    manifest: PluginManifest  # 插件清单
    path: Path  # 插件目录路径
    enabled: bool  # 是否启用
    skills: list[SkillDefinition] = field(default_factory=list)  # 技能列表
    hooks: dict[str, list] = field(default_factory=dict)  # 钩子字典
    mcp_servers: dict[str, McpServerConfig] = field(default_factory=dict)  # MCP 服务器配置
    commands: list[SkillDefinition] = field(default_factory=list)  # 命令列表

    @property
    def name(self) -> str:
        """获取插件名称"""
        return self.manifest.name

    @property
    def description(self) -> str:
        """获取插件描述"""
        return self.manifest.description
