"""
MCP 服务器配置加载模块
=====================

本模块提供从设置和插件加载 MCP 服务器配置的功能。

主要功能：
    - 从全局设置中加载 MCP 服务器配置
    - 从已加载的插件中合并 MCP 服务器配置
    - 插件配置优先级高于全局设置（同名配置）

函数说明：
    - load_mcp_server_configs: 加载并合并 MCP 服务器配置

使用示例：
    >>> from illusion.mcp.config import load_mcp_server_configs
    >>> configs = load_mcp_server_configs(settings, plugins)
"""

from __future__ import annotations

from illusion.plugins.types import LoadedPlugin


def load_mcp_server_configs(settings, plugins: list[LoadedPlugin]) -> dict[str, object]:
    """
    加载 MCP 服务器配置
    
    从全局设置和已加载的插件中合并 MCP 服务器配置。
    插件中的配置会与全局设置合并，如果存在同名配置，插件配置优先。
    
    Args:
        settings: 全局设置对象，包含 mcp_servers 属性
        plugins: 已加载的插件列表，每个插件包含 mcp_servers 属性
    
    Returns:
        dict[str, object]: 服务器名称到配置的映射字典
                         键的格式为 "插件名:服务器名"（来自插件）或仅"服务器名"（来自全局设置）
    
    使用示例：
        >>> configs = load_mcp_server_configs(settings, plugins)
        >>> for name, config in configs.items():
        ...     print(f"{name}: {config}")
    """
    # 从全局设置中获取 MCP 服务器配置
    servers = dict(settings.mcp_servers)
    # 遍历所有已加载的插件
    for plugin in plugins:
        # 跳过未启用的插件
        if not plugin.enabled:
            continue
        # 将插件的 MCP 服务器配置合并到结果中
        for name, config in plugin.mcp_servers.items():
            # 使用 "插件名:服务器名" 格式作为键，避免与全局设置冲突
            servers.setdefault(f"{plugin.manifest.name}:{name}", config)
    return servers
