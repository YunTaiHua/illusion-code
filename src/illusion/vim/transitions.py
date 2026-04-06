"""Minimal Vim mode state helpers."""

from __future__ import annotations


def toggle_vim_mode(enabled: bool) -> bool:
    """Toggle Vim mode state."""
    return not enabled
