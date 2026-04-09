"""Tests for workspace-local permission persistence."""

from __future__ import annotations

from illusion.ui.permission_store import add_always_allowed_tool, load_always_allowed_tools


def test_permission_store_creates_and_updates_file(tmp_path):
    tools = add_always_allowed_tool(tmp_path, "bash")
    assert "bash" in tools

    tools = add_always_allowed_tool(tmp_path, "read")
    assert tools == {"bash", "read"}

    loaded = load_always_allowed_tools(tmp_path)
    assert loaded == {"bash", "read"}
