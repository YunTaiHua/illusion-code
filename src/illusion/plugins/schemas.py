"""
插件清单模式模块
================

本模块定义插件清单的数据模型。

主要组件：
    - PluginManifest: 插件清单

使用示例：
    >>> from illusion.plugins.schemas import PluginManifest
"""

from __future__ import annotations

from pydantic import BaseModel


class PluginManifest(BaseModel):
    """插件清单
    
    定义插件的元数据，存储在 plugin.json 或 .claude-plugin/plugin.json 文件中。
    
    Attributes:
        name: 插件名称
        version: 插件版本
        description: 插件描述
        enabled_by_default: 默认是否启用
        skills_dir: 技能目录名称
        hooks_file: 钩子文件名
        mcp_file: MCP 配置文件名
        author: 作者信息
        commands: 命令配置
        agents: 智能体配置
        skills: 技能配置
        hooks: 钩子配置
    """

    name: str  # 插件名称
    version: str = "0.0.0"  # 插件版本
    description: str = ""  # 插件描述
    enabled_by_default: bool = True  # 默认是否启用
    skills_dir: str = "skills"  # 技能目录名称
    hooks_file: str = "hooks.json"  # 钩子文件名
    mcp_file: str = "mcp.json"  # MCP 配置文件名
    # 扩展字段：可选的 author, commands, agents 等
    author: dict | None = None  # 作者信息
    commands: str | list | dict | None = None  # 命令配置
    agents: str | list | None = None  # 智能体配置
    skills: str | list | None = None  # 技能配置
    hooks: str | dict | list | None = None  # 钩子配置
