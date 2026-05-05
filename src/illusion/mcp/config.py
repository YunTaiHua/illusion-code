"""
MCP 服务器配置加载模块
=====================

本模块提供从设置、插件和项目目录加载 MCP 服务器配置的功能。

主要功能：
    - 从全局设置中加载 MCP 服务器配置
    - 从已加载的插件中合并 MCP 服务器配置
    - 从项目级配置目录加载 MCP 服务器配置
    - 插件配置优先级高于全局设置（同名配置）

函数说明：
    - load_mcp_server_configs: 加载并合并 MCP 服务器配置
    - load_project_mcp_configs: 从项目目录加载 MCP 配置

使用示例：
    >>> from illusion.mcp.config import load_mcp_server_configs
    >>> configs = load_mcp_server_configs(settings, plugins, cwd="/path/to/project")
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from illusion.plugins.types import LoadedPlugin

logger = logging.getLogger(__name__)


def load_project_mcp_configs(cwd: str | Path) -> dict[str, object]:
    """
    从项目目录加载 MCP 服务器配置

    扫描 <project>/.illusion/mcp/ 目录下的所有 JSON 文件，
    每个文件可以包含一个或多个 MCP 服务器配置。

    文件格式支持：
    1. 单个服务器配置（文件名作为服务器名）：
       {"type": "stdio", "command": "python", "args": ["server.py"]}

    2. 多个服务器配置（使用 mcpServers 键）：
       {"mcpServers": {"server1": {...}, "server2": {...}}}

    Args:
        cwd: 当前工作目录

    Returns:
        dict[str, object]: 服务器名称到配置的映射字典
    """
    from illusion.config.paths import get_project_mcp_dir
    from illusion.mcp.types import McpJsonConfig, McpServerConfig

    servers: dict[str, object] = {}
    mcp_dir = get_project_mcp_dir(cwd)

    if not mcp_dir.exists():
        return servers

    for json_file in sorted(mcp_dir.glob("*.json")):
        try:
            raw = json.loads(json_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read MCP config %s: %s", json_file, exc)
            continue

        # 尝试解析为多服务器格式（mcpServers 键）
        if "mcpServers" in raw:
            try:
                parsed = McpJsonConfig.model_validate(raw)
                for name, config in parsed.mcpServers.items():
                    servers[name] = config
            except Exception as exc:
                logger.warning("Failed to parse MCP config %s: %s", json_file, exc)
            continue

        # 尝试解析为单服务器格式（文件名作为服务器名）
        try:
            config = McpServerConfig.model_validate(raw)
            server_name = json_file.stem
            servers[server_name] = config
        except Exception as exc:
            logger.warning("Failed to parse MCP config %s: %s", json_file, exc)

    return servers


def load_mcp_server_configs(settings, plugins: list[LoadedPlugin], cwd: str | Path | None = None) -> dict[str, object]:
    """
    加载 MCP 服务器配置

    从全局设置、项目目录和已加载的插件中合并 MCP 服务器配置。
    优先级（从高到低）：插件 > 项目级 > 全局设置

    Args:
        settings: 全局设置对象，包含 mcp_servers 属性
        plugins: 已加载的插件列表，每个插件包含 mcp_servers 属性
        cwd: 当前工作目录，用于加载项目级配置

    Returns:
        dict[str, object]: 服务器名称到配置的映射字典
                         键的格式为 "插件名:服务器名"（来自插件）或仅"服务器名"（来自其他来源）

    使用示例：
        >>> configs = load_mcp_server_configs(settings, plugins, cwd="/path/to/project")
        >>> for name, config in configs.items():
        ...     print(f"{name}: {config}")
    """
    # 从全局设置中获取 MCP 服务器配置
    servers = dict(settings.mcp_servers)

    # 从项目目录加载 MCP 配置（覆盖全局设置）
    if cwd is not None:
        project_configs = load_project_mcp_configs(cwd)
        servers.update(project_configs)

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
