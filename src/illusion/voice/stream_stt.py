"""Placeholder streaming STT interface."""

from __future__ import annotations


async def transcribe_stream(_: bytes) -> str:
    """Return a placeholder message for unimplemented STT."""
    return "Streaming STT is not configured in this build."
