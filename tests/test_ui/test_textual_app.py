"""Tests for the Textual terminal UI."""

from __future__ import annotations

import pytest

from illusion.api.client import ApiMessageCompleteEvent
from illusion.api.usage import UsageSnapshot
from illusion.engine.messages import ConversationMessage, TextBlock, ToolUseBlock
from illusion.ui.textual_app import IllusionCodeTerminalApp


class StaticApiClient:
    """Fake streaming client for UI tests."""

    def __init__(self, text: str) -> None:
        self._text = text

    async def stream_message(self, request):
        del request
        yield ApiMessageCompleteEvent(
            message=ConversationMessage(role="assistant", content=[TextBlock(text=self._text)]),
            usage=UsageSnapshot(input_tokens=2, output_tokens=3),
            stop_reason=None,
        )


class ScriptedApiClient:
    """Fake client that yields a scripted sequence of assistant turns."""

    def __init__(self, messages) -> None:
        self._messages = list(messages)

    async def stream_message(self, request):
        del request
        message = self._messages.pop(0)
        yield ApiMessageCompleteEvent(
            message=message,
            usage=UsageSnapshot(input_tokens=2, output_tokens=3),
            stop_reason=None,
        )


@pytest.mark.asyncio
async def test_textual_app_handles_commands(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ILLUSION_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("ILLUSION_DATA_DIR", str(tmp_path / "data"))

    app = IllusionCodeTerminalApp(api_client=StaticApiClient("unused"))
    async with app.run_test() as pilot:
        composer = app.query_one("#composer")
        composer.value = "/version"
        await pilot.press("enter")
        await pilot.pause()

    assert any("IllusionCode" in line for line in app.transcript_lines)


@pytest.mark.asyncio
async def test_textual_app_runs_one_model_turn(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ILLUSION_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("ILLUSION_DATA_DIR", str(tmp_path / "data"))

    app = IllusionCodeTerminalApp(api_client=StaticApiClient("hello from textual"))
    async with app.run_test() as pilot:
        composer = app.query_one("#composer")
        composer.value = "hi"
        await pilot.press("enter")
        await pilot.pause()

    assert any("user> hi" in line for line in app.transcript_lines)
    assert any("assistant> hello from textual" in line for line in app.transcript_lines)


@pytest.mark.asyncio
async def test_textual_app_handles_ask_user_tool(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ILLUSION_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("ILLUSION_DATA_DIR", str(tmp_path / "data"))

    app = IllusionCodeTerminalApp(
        api_client=ScriptedApiClient(
            [
                ConversationMessage(
                    role="assistant",
                    content=[
                        ToolUseBlock(
                            id="toolu_ask",
                            name="ask_user_question",
                            input={"question": "Pick a color"},
                        )
                    ],
                ),
                ConversationMessage(
                    role="assistant",
                    content=[TextBlock(text="chosen green")],
                ),
            ]
        )
    )

    async def _answer(question: str) -> str:
        assert question == "Pick a color"
        return "green"

    app._ask_question = _answer
    async with app.run_test() as pilot:
        composer = app.query_one("#composer")
        composer.value = "hi"
        await pilot.press("enter")
        await pilot.pause()

    assert any("tool-result> ask_user_question: green" in line for line in app.transcript_lines)
    assert any("assistant> chosen green" in line for line in app.transcript_lines)
