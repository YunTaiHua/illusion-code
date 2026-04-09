"""Input helpers built on prompt_toolkit."""

from __future__ import annotations

from prompt_toolkit import PromptSession


class InputSession:
    """Async prompt wrapper."""

    def __init__(self) -> None:
        self._session = PromptSession()
        self._prompt = "> "

    def set_modes(self, *, vim_enabled: bool = False, voice_enabled: bool = False) -> None:
        """Compatibility no-op; modes are removed from UI prompt decorations."""
        del vim_enabled, voice_enabled
        self._prompt = "> "

    async def prompt(self) -> str:
        """Prompt the user for one line of input."""
        return await self._session.prompt_async(self._prompt)

    async def ask(self, question: str) -> str:
        """Prompt the user for an ad-hoc answer."""
        prompt = f"[question] {question}\n> "
        return await self._session.prompt_async(prompt)
