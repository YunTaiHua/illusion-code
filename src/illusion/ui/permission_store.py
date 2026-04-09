"""Workspace-local persistence for always-allow tool permissions."""

from __future__ import annotations

import json
from pathlib import Path


_PERMISSIONS_PATH = Path(".illusion") / "permissions.json"


def _file_path(cwd: str | Path) -> Path:
    return Path(cwd).resolve() / _PERMISSIONS_PATH


def load_always_allowed_tools(cwd: str | Path) -> set[str]:
    """Load always-allow tools from the workspace permission file."""
    path = _file_path(cwd)
    if not path.exists():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    tools = payload.get("always_allow_tools", [])
    if not isinstance(tools, list):
        return set()
    return {str(item).strip() for item in tools if str(item).strip()}


def save_always_allowed_tools(cwd: str | Path, tools: set[str]) -> None:
    """Persist always-allow tools to the workspace permission file."""
    path = _file_path(cwd)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"always_allow_tools": sorted({tool.strip() for tool in tools if tool.strip()})}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def add_always_allowed_tool(cwd: str | Path, tool_name: str) -> set[str]:
    """Add one tool to workspace always-allow permissions and persist."""
    tools = load_always_allowed_tools(cwd)
    name = tool_name.strip()
    if not name:
        return tools
    tools.add(name)
    save_always_allowed_tools(cwd, tools)
    return tools
