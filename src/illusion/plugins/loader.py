"""Plugin discovery and loading."""

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
    """Return the user plugin directory."""
    path = get_config_dir() / "plugins"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_project_plugins_dir(cwd: str | Path) -> Path:
    """Return the project plugin directory."""
    path = Path(cwd).resolve() / ".illusion" / "plugins"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _find_manifest(plugin_dir: Path) -> Path | None:
    """Find plugin.json in standard or .claude-plugin/ locations."""
    for candidate in [
        plugin_dir / "plugin.json",
        plugin_dir / ".claude-plugin" / "plugin.json",
    ]:
        if candidate.exists():
            return candidate
    return None


def discover_plugin_paths(cwd: str | Path) -> list[Path]:
    """Find plugin directories from user and project locations."""
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
    """Load plugins from disk."""
    plugins: list[LoadedPlugin] = []
    for path in discover_plugin_paths(cwd):
        plugin = load_plugin(path, settings.enabled_plugins)
        if plugin is not None:
            plugins.append(plugin)
    return plugins


def load_plugin(path: Path, enabled_plugins: dict[str, bool]) -> LoadedPlugin | None:
    """Load one plugin directory."""
    manifest_path = _find_manifest(path)
    if manifest_path is None:
        return None
    try:
        manifest = PluginManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.debug("Failed to load plugin manifest from %s: %s", manifest_path, exc)
        return None
    enabled = enabled_plugins.get(manifest.name, manifest.enabled_by_default)

    # Discover skills from multiple locations
    skills = _load_plugin_skills(path / manifest.skills_dir)

    # Discover commands from plugin commands/ directory
    commands_dir = path / "commands"
    if commands_dir.exists():
        skills.extend(_load_plugin_skills(commands_dir))

    # Discover agents from plugin agents/ directory
    agents_dir = path / "agents"
    if agents_dir.exists():
        skills.extend(_load_plugin_skills(agents_dir))

    # Discover hooks from hooks/ dir or root hooks.json
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
    """Load skill definitions from markdown files in a directory.

    Args:
        path: Directory containing ``.md`` skill files.

    Returns:
        List of parsed ``SkillDefinition`` objects, or empty list if path doesn't exist.
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
    """Load hooks from a flat hooks.json file.

    Args:
        path: Path to a hooks JSON file.

    Returns:
        Dictionary mapping event names to lists of hook definition objects.
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
    """Load hooks from structured hooks.json format."""
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
                # Replace ${CLAUDE_PLUGIN_ROOT} with actual path
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
    """Load MCP server configuration from a JSON file.

    Args:
        path: Path to an MCP config file (e.g. ``.mcp.json``).

    Returns:
        Dictionary mapping server names to their configuration objects.
    """
    if not path.exists():
        return {}
    from illusion.mcp.types import McpJsonConfig

    raw = json.loads(path.read_text(encoding="utf-8"))
    parsed = McpJsonConfig.model_validate(raw)
    return parsed.mcpServers
