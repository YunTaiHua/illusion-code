"""Tests for the React backend host protocol."""

from __future__ import annotations

import io
import json

import pytest

from illusion.api.client import ApiMessageCompleteEvent
from illusion.api.usage import UsageSnapshot
from illusion.engine.messages import ConversationMessage, TextBlock
from illusion.ui.backend_host import BackendHostConfig, ReactBackendHost
from illusion.ui.permission_store import add_always_allowed_tool, load_always_allowed_tools
from illusion.ui.protocol import BackendEvent
from illusion.ui.runtime import build_runtime, close_runtime, start_runtime


class StaticApiClient:
    """Fake streaming client for backend host tests."""

    def __init__(self, text: str) -> None:
        self._text = text

    async def stream_message(self, request):
        del request
        yield ApiMessageCompleteEvent(
            message=ConversationMessage(role="assistant", content=[TextBlock(text=self._text)]),
            usage=UsageSnapshot(input_tokens=2, output_tokens=3),
            stop_reason=None,
        )


class FakeBinaryStdout:
    """Capture protocol writes through a binary stdout buffer."""

    def __init__(self) -> None:
        self.buffer = io.BytesIO()

    def flush(self) -> None:
        return None


@pytest.mark.asyncio
async def test_backend_host_processes_command(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ILLUSION_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("ILLUSION_DATA_DIR", str(tmp_path / "data"))

    host = ReactBackendHost(BackendHostConfig(api_client=StaticApiClient("unused")))
    host._bundle = await build_runtime(api_client=StaticApiClient("unused"))
    events = []

    async def _emit(event):
        events.append(event)

    host._emit = _emit  # type: ignore[method-assign]
    await start_runtime(host._bundle)
    try:
        should_continue = await host._process_line("/version")
    finally:
        await close_runtime(host._bundle)

    assert should_continue is True
    assert any(event.type == "transcript_item" and event.item and event.item.role == "user" for event in events)
    assert any(
        event.type == "transcript_item"
        and event.item
        and event.item.role == "system"
        and "IllusionCode" in event.item.text
        for event in events
    )
    assert any(event.type == "state_snapshot" for event in events)


@pytest.mark.asyncio
async def test_backend_host_processes_model_turn(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ILLUSION_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("ILLUSION_DATA_DIR", str(tmp_path / "data"))

    host = ReactBackendHost(BackendHostConfig(api_client=StaticApiClient("hello from react backend")))
    host._bundle = await build_runtime(api_client=StaticApiClient("hello from react backend"))
    events = []

    async def _emit(event):
        events.append(event)

    host._emit = _emit  # type: ignore[method-assign]
    await start_runtime(host._bundle)
    try:
        should_continue = await host._process_line("hi")
    finally:
        await close_runtime(host._bundle)

    assert should_continue is True
    assert any(
        event.type == "assistant_complete" and event.message == "hello from react backend"
        for event in events
    )
    assert any(
        event.type == "assistant_complete"
        and event.item
        and event.item.role == "assistant"
        and "hello from react backend" in event.item.text
        for event in events
    )


@pytest.mark.asyncio
async def test_backend_host_command_does_not_reset_cli_overrides(tmp_path, monkeypatch):
    """Regression: slash commands should not snap model/provider back to persisted defaults.

    When the session is launched with CLI overrides (e.g. --provider openai -m 5.4),
    issuing a command like /fast triggers a UI state refresh. That refresh must
    preserve the effective session settings, not reload ~/.illusion/settings.json
    verbatim.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ILLUSION_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("ILLUSION_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)

    host = ReactBackendHost(BackendHostConfig(api_client=StaticApiClient("unused")))
    host._bundle = await build_runtime(
        api_client=StaticApiClient("unused"),
        model="5.4",
        api_format="openai",
    )
    events = []

    async def _emit(event):
        events.append(event)

    host._emit = _emit  # type: ignore[method-assign]
    await start_runtime(host._bundle)
    try:
        # Sanity: the initial session state reflects CLI overrides.
        assert host._bundle.app_state.get().model == "5.4"
        provider = host._bundle.app_state.get().provider
        assert provider in ("openai-compatible", "openai", "zhipu")

        # Run a command that triggers sync_app_state.
        await host._process_line("/fast show")

        # CLI overrides should remain in effect.
        assert host._bundle.app_state.get().model == "5.4"
        assert host._bundle.app_state.get().provider == provider
    finally:
        await close_runtime(host._bundle)


@pytest.mark.asyncio
async def test_backend_host_emits_utf8_protocol_bytes(monkeypatch):
    host = ReactBackendHost(BackendHostConfig())
    fake_stdout = FakeBinaryStdout()
    monkeypatch.setattr("illusion.ui.backend_host.sys.stdout", fake_stdout)

    await host._emit(BackendEvent(type="assistant_delta", message="你好😊"))

    raw = fake_stdout.buffer.getvalue()
    assert raw.startswith(b"OHJSON:")
    decoded = raw.decode("utf-8").strip()
    payload = json.loads(decoded.removeprefix("OHJSON:"))
    assert payload["type"] == "assistant_delta"
    assert payload["message"] == "你好😊"


@pytest.mark.asyncio
async def test_backend_host_phase_transitions_on_model_turn(tmp_path, monkeypatch):
    """纯文本对话（无工具）时 phase 流转: idle → thinking → idle。"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ILLUSION_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("ILLUSION_DATA_DIR", str(tmp_path / "data"))

    host = ReactBackendHost(BackendHostConfig(api_client=StaticApiClient("phase test")))
    host._bundle = await build_runtime(api_client=StaticApiClient("phase test"))
    events = []

    async def _emit(event):
        events.append(event)

    host._emit = _emit  # type: ignore[method-assign]
    await start_runtime(host._bundle)
    try:
        await host._process_line("hello")
    finally:
        await close_runtime(host._bundle)

    # 最终 phase 应为 idle
    assert host._bundle.app_state.get().phase == "idle"
    # line_complete 事件必须存在
    line_complete_events = [e for e in events if e.type == "line_complete"]
    assert len(line_complete_events) == 1
    # state_snapshot 中应包含 phase
    snapshots = [e for e in events if e.type == "state_snapshot" and e.state]
    assert any(s.state.get("phase") == "idle" for s in snapshots)


@pytest.mark.asyncio
async def test_backend_host_loads_workspace_always_allow_tools(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ILLUSION_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("ILLUSION_DATA_DIR", str(tmp_path / "data"))
    add_always_allowed_tool(tmp_path, "bash")

    host = ReactBackendHost(BackendHostConfig(api_client=StaticApiClient("unused")))
    host._bundle = await build_runtime(api_client=StaticApiClient("unused"))
    await start_runtime(host._bundle)
    try:
        host._always_allowed_tools = load_always_allowed_tools(host._bundle.cwd)
        allowed = await host._ask_permission("bash", "test")
    finally:
        await close_runtime(host._bundle)
    assert allowed is True


@pytest.mark.asyncio
async def test_backend_host_does_not_treat_stop_text_as_special_command(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ILLUSION_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("ILLUSION_DATA_DIR", str(tmp_path / "data"))

    host = ReactBackendHost(BackendHostConfig(api_client=StaticApiClient("handled as normal text")))
    host._bundle = await build_runtime(api_client=StaticApiClient("handled as normal text"))
    events = []

    async def _emit(event):
        events.append(event)

    host._emit = _emit  # type: ignore[method-assign]
    await start_runtime(host._bundle)
    try:
        should_continue = await host._process_line("/stop")
    finally:
        await close_runtime(host._bundle)

    assert should_continue is True
    assert any(
        event.type == "assistant_complete" and event.message == "handled as normal text"
        for event in events
    )


@pytest.mark.asyncio
async def test_backend_resume_keeps_restored_session_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ILLUSION_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("ILLUSION_DATA_DIR", str(tmp_path / "data"))

    from illusion.services.session_storage import save_session_snapshot
    from illusion.ui.backend_host import BackendHostConfig, ReactBackendHost

    host = ReactBackendHost(BackendHostConfig(api_client=StaticApiClient("unused")))
    host._bundle = await build_runtime(api_client=StaticApiClient("unused"))
    await start_runtime(host._bundle)
    try:
        host._bundle.engine.load_messages([
            ConversationMessage(role="user", content=[TextBlock(text="hello")]),
            ConversationMessage(role="assistant", content=[TextBlock(text="world")]),
        ])
        save_session_snapshot(
            cwd=tmp_path,
            model="claude-test",
            system_prompt="system",
            messages=host._bundle.engine.messages,
            usage=UsageSnapshot(),
            session_id="sid-old-001",
        )
        await host._process_line("/resume sid-old-001")
        assert host._bundle.session_id == "sid-old-001"
    finally:
        await close_runtime(host._bundle)


@pytest.mark.asyncio
async def test_resume_replay_has_no_session_restored_system_banner(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ILLUSION_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("ILLUSION_DATA_DIR", str(tmp_path / "data"))

    host = ReactBackendHost(BackendHostConfig(api_client=StaticApiClient("unused")))
    host._bundle = await build_runtime(api_client=StaticApiClient("unused"))
    events = []

    async def _emit(event):
        events.append(event)

    host._emit = _emit  # type: ignore[method-assign]
    await start_runtime(host._bundle)
    try:
        from illusion.api.usage import UsageSnapshot
        from illusion.services.session_storage import save_session_snapshot
        host._bundle.engine.load_messages([
            ConversationMessage(role="user", content=[TextBlock(text="u")]),
            ConversationMessage(role="assistant", content=[TextBlock(text="a")]),
        ])
        save_session_snapshot(
            cwd=tmp_path,
            model="claude-test",
            system_prompt="system",
            messages=host._bundle.engine.messages,
            usage=UsageSnapshot(),
            session_id="sid-banner-001",
        )
        await host._process_line("/resume sid-banner-001")
    finally:
        await close_runtime(host._bundle)

    assert not any(
        e.type == "transcript_item" and e.item and e.item.role == "system" and e.item.text == "Session restored:"
        for e in events
    )


@pytest.mark.asyncio
async def test_resume_replay_skips_empty_user_transcript_rows(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ILLUSION_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("ILLUSION_DATA_DIR", str(tmp_path / "data"))

    host = ReactBackendHost(BackendHostConfig(api_client=StaticApiClient("unused")))
    host._bundle = await build_runtime(api_client=StaticApiClient("unused"))
    events = []

    async def _emit(event):
        events.append(event)

    host._emit = _emit  # type: ignore[method-assign]
    await start_runtime(host._bundle)
    try:
        from illusion.api.usage import UsageSnapshot
        from illusion.engine.messages import ToolResultBlock
        from illusion.services.session_storage import save_session_snapshot

        host._bundle.engine.load_messages([
            ConversationMessage(role="assistant", content=[]),
            ConversationMessage(role="user", content=[ToolResultBlock(tool_use_id="x", content="ok", is_error=False)]),
        ])
        save_session_snapshot(
            cwd=tmp_path,
            model="claude-test",
            system_prompt="system",
            messages=host._bundle.engine.messages,
            usage=UsageSnapshot(),
            session_id="sid-empty-user-001",
        )
        await host._process_line("/resume sid-empty-user-001")
    finally:
        await close_runtime(host._bundle)

    assert not any(
        e.type == "transcript_item" and e.item and e.item.role == "user" and e.item.text.strip() == ""
        for e in events
    )
