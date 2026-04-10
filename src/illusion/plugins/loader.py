"""
插件发现和加载模块
==================

本模块实现插件的发现和加载功能。

主要功能：
    - 发现用户和项目插件目录
    - 加载插件清单和配置
    - 解析插件技能、命令、钩子和 MCP 服务器

使用示例：
    >>> from illusion.plugins.loader import load_plugins, get_user_plugins_dir
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from illusion.config.paths import get_config_dir
from illusion.plugins.schemas import PluginManifest
from illusion.plugins.types import LoadedPlugin
from illusion.skills.loader import _parse_skill_markdown
from illusion.skills.types import SkillDefinition

logger = logging.getLogger(__name__)


def get_user_plugins_dir() -> Path:
    """获取用户插件目录
    
    返回用户级别的插件目录，如果不存在则创建。
    
    Returns:
        Path: 用户插件目录路径
    """
    path = get_config_dir() / "plugins"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_project_plugins_dir(cwd: str | Path) -> Path:
    """获取项目插件目录
    
    返回项目级别的插件目录。
    
    Args:
        cwd: 工作目录
    
    Returns:
        Path: 项目插件目录路径
    """
    path = Path(cwd).resolve() / ".illusion" / "plugins"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _find_manifest(plugin_dir: Path) -> Path | None:
    """查找插件清单文件
    
    在标准位置或 .claude-plugin/ 目录下查找 plugin.json。
    
    Args:
        plugin_dir: 插件目录
    
    Returns:
        Path | None: 找到的清单文件路径，不存在则返回 None
    """
    for candidate in [
        plugin_dir / "plugin.json",
        plugin_dir / ".claude-plugin" / "plugin.json",
    ]:
        if candidate.exists():
            return candidate
    return None


def discover_plugin_paths(cwd: str | Path) -> list[Path]:
    """发现插件目录
    
    从用户和项目位置查找所有插件目录。
    
    Args:
        cwd: 工作目录
    
    Returns:
        list[Path]: 插件目录路径列表
    """
    roots = [get_user_plugins_dir(), get_project_plugins_dir(cwd)]
    paths: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.iterdir()):
            if path.is_dir() and _find_manifest(path) is not None:
                paths.append(path)
    return paths


def load_plugins(settings, cwd: str | Path) -> list[LoadedPlugin]:
    """从磁盘加载所有插件
    
    Args:
        settings: 设置对象
        cwd: 工作目录
    
    Returns:
        list[LoadedPlugin]: 已加载的插件列表
    """
    plugins: list[LoadedPlugin] = []
    for path in discover_plugin_paths(cwd):
        plugin = load_plugin(path, settings.enabled_plugins)
        if plugin is not None:
            plugins.append(plugin)
    return plugins


def load_plugin(path: Path, enabled_plugins: dict[str, bool]) -> LoadedPlugin | None:
    """加载单个插件目录
    
    Args:
        path: 插件目录路径
        enabled_plugins: 启用的插件配置
    
    Returns:
        LoadedPlugin | None: 已加载的插件，未找到清单则返回 None
    """
    manifest_path = _find_manifest(path)
    if manifest_path is None:
        return None
    try:
        manifest = PluginManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.debug("Failed to load plugin manifest from %s: %s", manifest_path, exc)
        return None
    enabled = enabled_plugins.get(manifest.name, manifest.enabled_by_default)

    # 从多个位置发现技能
    skills = _load_plugin_skills(path / manifest.skills_dir)

    # 从 plugin commands/ 目录发现命令
    commands_dir = path / "commands"
    if commands_dir.exists():
        skills.extend(_load_plugin_skills(commands_dir))

    # 从 plugin agents/ 目录发现智能体
    agents_dir = path / "agents"
    if agents_dir.exists():
        skills.extend(_load_plugin_skills(agents_dir))

    # 从 hooks/ 目录或根 hooks.json 发现钩子
    hooks = _load_plugin_hooks(path / manifest.hooks_file)
    hooks_dir_file = path / "hooks" / "hooks.json"
    if not hooks and hooks_dir_file.exists():
        hooks = _load_plugin_hooks_structured(hooks_dir_file, path)

    mcp = _load_plugin_mcp(path / manifest.mcp_file)
    mcp_json = path / ".mcp.json"
    if not mcp and mcp_json.exists():
        mcp = _load_plugin_mcp(mcp_json)

    return LoadedPlugin(
        manifest=manifest,
        path=path,
        enabled=enabled,
        skills=skills,
        hooks=hooks,
        mcp_servers=mcp,
        commands=[s for s in skills if s.source == "plugin"],
    )


def _load_plugin_skills(path: Path) -> list[SkillDefinition]:
    """从目录中的 markdown 文件加载技能定义
    
    Args:
        path: 包含 .md 技能文件的目录
    
    Returns:
        list[SkillDefinition]: 解析后的技能定义列表，如果路径不存在则返回空列表
    """
    if not path.exists():
        return []
    skills: list[SkillDefinition] = []
    for skill_path in sorted(path.glob("*.md")):
        content = skill_path.read_text(encoding="utf-8")
        name, description = _parse_skill_markdown(skill_path.stem, content)
        skills.append(
            SkillDefinition(
                name=name,
                description=description,
                content=content,
                source="plugin",
                path=str(skill_path),
            )
        )
    return skills


def _load_plugin_hooks(path: Path) -> dict[str, list]:
    """从平面 hooks.json 文件加载钩子
    
    Args:
        path: hooks JSON 文件路径
    
    Returns:
        dict[str, list]: 事件名称到钩子定义对象列表的字典
    """
    if not path.exists():
        return {}
    from illusion.hooks.schemas import (
        AgentHookDefinition,
        CommandHookDefinition,
        HttpHookDefinition,
        PromptHookDefinition,
    )

    raw = json.loads(path.read_text(encoding="utf-8"))
    parsed: dict[str, list] = {}
    for event, hooks in raw.items():
        parsed[event] = []
        for hook in hooks:
            hook_type = hook.get("type")
            if hook_type == "command":
                parsed[event].append(CommandHookDefinition.model_validate(hook))
            elif hook_type == "prompt":
                parsed[event].append(PromptHookDefinition.model_validate(hook))
            elif hook_type == "http":
                parsed[event].append(HttpHookDefinition.model_validate(hook))
            elif hook_type == "agent":
                parsed[event].append(AgentHookDefinition.model_validate(hook))
    return parsed


def _load_plugin_hooks_structured(path: Path, plugin_root: Path) -> dict[str, list]:
    """从结构化 hooks.json 格式加载钩子
    
    Args:
        path: hooks.json 文件路径
        plugin_root: 插件根目录
    
    Returns:
        dict[str, list]: 解析后的钩子字典
    """
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    hooks_data = raw.get("hooks", raw)
    if not isinstance(hooks_data, dict):
        return {}
    parsed: dict[str, list] = {}
    for event, entries in hooks_data.items():
        if not isinstance(entries, list):
            continue
        parsed[event] = []
        for entry in entries:
            hook_list = entry.get("hooks", [])
            matcher = entry.get("matcher", "")
            for hook in hook_list:
                # 将 ${CLAUDE_PLUGIN_ROOT} 替换为实际路径
                cmd = hook.get("command", "")
                cmd = cmd.replace("${CLAUDE_PLUGIN_ROOT}", str(plugin_root))
                parsed[event].append({
                    "type": hook.get("type", "command"),
                    "command": cmd,
                    "matcher": matcher,
                    "timeout": hook.get("timeout"),
                })
    return parsed


def _load_plugin_mcp(path: Path) -> dict[str, object]:
    """从 JSON 文件加载 MCP 服务器配置
    
    Args:
        path: MCP 配置文件路径（例如 .mcp.json）
    
    Returns:
        dict[str, object]: 服务器名称到配置对象的字典
    """
    if not path.exists():
        return {}
    from illusion.mcp.types import McpJsonConfig

    raw = json.loads(path.read_text(encoding="utf-8"))
    parsed = McpJsonConfig.model_validate(raw)
    return parsed.mcpServers
