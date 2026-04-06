"""Unified authentication manager for IllusionCode providers."""

from __future__ import annotations

import logging
from typing import Any

from illusion.auth.storage import (
    clear_provider_credentials,
    load_credential,
    store_credential,
)

log = logging.getLogger(__name__)

# Providers that IllusionCode knows about.
_KNOWN_PROVIDERS = [
    "anthropic",
    "openai",
    "copilot",
    "dashscope",
    "bedrock",
    "vertex",
]


class AuthManager:
    """Central authority for provider authentication state.

    Reads/writes credentials via :mod:`illusion.auth.storage` and keeps
    track of the currently active provider via settings.
    """

    def __init__(self, settings: Any | None = None) -> None:
        # Lazy-load settings when not provided so that the manager can be
        # instantiated without importing the full config subsystem.
        self._settings = settings

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @property
    def settings(self) -> Any:
        if self._settings is None:
            from illusion.config import load_settings

            self._settings = load_settings()
        return self._settings

    def _provider_from_settings(self) -> str:
        """Return the provider name derived from current settings."""
        api_format = getattr(self.settings, "api_format", "anthropic")
        if api_format == "copilot":
            return "copilot"
        if api_format == "openai":
            base_url = (getattr(self.settings, "base_url", "") or "").lower()
            model = (getattr(self.settings, "model", "") or "").lower()
            if "dashscope" in base_url or model.startswith("qwen"):
                return "dashscope"
            if "bedrock" in base_url:
                return "bedrock"
            if "vertex" in base_url or "aiplatform" in base_url:
                return "vertex"
            return "openai"
        return "anthropic"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_active_provider(self) -> str:
        """Return the name of the currently active provider."""
        return self._provider_from_settings()

    def get_auth_status(self) -> dict[str, Any]:
        """Return authentication status for all known providers.

        Returns a dict keyed by provider name with the following structure::

            {
                "anthropic": {
                    "configured": True,
                    "source": "env",   # "env", "file", "keyring", or "missing"
                    "active": True,
                },
                ...
            }
        """
        import os

        active = self.get_active_provider()
        result: dict[str, Any] = {}

        for provider in _KNOWN_PROVIDERS:
            configured = False
            source = "missing"

            if provider == "anthropic":
                if os.environ.get("ANTHROPIC_API_KEY"):
                    configured = True
                    source = "env"
                elif load_credential("anthropic", "api_key") or getattr(self.settings, "api_key", ""):
                    configured = True
                    source = "file"

            elif provider == "openai":
                if os.environ.get("OPENAI_API_KEY"):
                    configured = True
                    source = "env"
                elif load_credential("openai", "api_key"):
                    configured = True
                    source = "file"

            elif provider == "copilot":
                from illusion.api.copilot_auth import load_copilot_auth

                if load_copilot_auth():
                    configured = True
                    source = "file"

            elif provider == "dashscope":
                if os.environ.get("DASHSCOPE_API_KEY"):
                    configured = True
                    source = "env"
                elif load_credential("dashscope", "api_key"):
                    configured = True
                    source = "file"

            elif provider in ("bedrock", "vertex"):
                # These typically use environment-level credentials (AWS/GCP).
                cred = load_credential(provider, "api_key")
                if cred:
                    configured = True
                    source = "file"

            result[provider] = {
                "configured": configured,
                "source": source,
                "active": provider == active,
            }

        return result

    def switch_provider(self, name: str) -> None:
        """Switch the active provider by updating settings.

        Persists the ``api_format`` (and clears ``base_url`` for standard
        providers) so subsequent runs use the new provider.
        """
        from illusion.config import save_settings

        if name not in _KNOWN_PROVIDERS:
            raise ValueError(f"Unknown provider: {name!r}. Known providers: {_KNOWN_PROVIDERS}")

        fmt_map = {
            "anthropic": "anthropic",
            "openai": "openai",
            "copilot": "copilot",
            "dashscope": "openai",
            "bedrock": "openai",
            "vertex": "openai",
        }
        new_format = fmt_map[name]
        updated = self.settings.model_copy(update={"api_format": new_format})
        save_settings(updated)
        self._settings = updated
        log.info("Switched active provider to %s (api_format=%s)", name, new_format)

    def store_credential(self, provider: str, key: str, value: str) -> None:
        """Store a credential for the given provider."""
        store_credential(provider, key, value)
        # If this is a primary API key for a known provider, also sync to
        # settings so existing code that reads settings.api_key still works.
        if key == "api_key" and provider == self.get_active_provider():
            try:
                from illusion.config import save_settings

                updated = self.settings.model_copy(update={"api_key": value})
                save_settings(updated)
                self._settings = updated
            except Exception as exc:
                log.warning("Could not sync api_key to settings: %s", exc)

    def clear_credential(self, provider: str) -> None:
        """Remove all stored credentials for the given provider."""
        clear_provider_credentials(provider)
        # Also clear api_key in settings if this is the active provider.
        if provider == self.get_active_provider():
            try:
                from illusion.config import save_settings

                updated = self.settings.model_copy(update={"api_key": ""})
                save_settings(updated)
                self._settings = updated
            except Exception as exc:
                log.warning("Could not clear api_key from settings: %s", exc)
