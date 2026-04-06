"""Unified authentication manager for illusion providers."""

from __future__ import annotations

import logging
from typing import Any

from illusion.config.settings import (
    ProviderProfile,
    auth_source_provider_name,
    builtin_provider_profile_names,
    default_auth_source_for_provider,
    display_model_setting,
)
from illusion.auth.storage import (
    clear_provider_credentials,
    load_external_binding,
    load_credential,
    store_credential,
)

log = logging.getLogger(__name__)

# Providers that illusion knows about.
_KNOWN_PROVIDERS = [
    "anthropic",
    "anthropic_claude",
    "openai",
    "openai_codex",
    "copilot",
    "dashscope",
    "bedrock",
    "vertex",
]

_AUTH_SOURCES = [
    "anthropic_api_key",
    "openai_api_key",
    "codex_subscription",
    "claude_subscription",
    "copilot_oauth",
    "dashscope_api_key",
    "bedrock_api_key",
    "vertex_api_key",
]

_PROFILE_BY_PROVIDER = {
    "anthropic": "claude-api",
    "anthropic_claude": "claude-subscription",
    "openai": "openai-compatible",
    "openai_codex": "codex",
    "copilot": "copilot",
}


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
        """Return the provider name derived from the active profile."""
        _, profile = self.settings.resolve_profile()
        return profile.provider

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_active_provider(self) -> str:
        """Return the name of the currently active provider."""
        return self._provider_from_settings()

    def get_active_profile(self) -> str:
        """Return the active provider profile name."""
        return self.settings.resolve_profile()[0]

    def list_profiles(self) -> dict[str, ProviderProfile]:
        """Return the configured provider profiles."""
        return self.settings.merged_profiles()

    def get_auth_source_statuses(self) -> dict[str, Any]:
        """Return auth source configuration status."""
        import os

        from illusion.auth.external import describe_external_binding

        active_profile_name, active_profile = self.settings.resolve_profile()
        result: dict[str, Any] = {}
        for source in _AUTH_SOURCES:
            configured = False
            origin = "missing"
            state = "missing"
            detail = ""
            storage_provider = auth_source_provider_name(source)
            if source == "anthropic_api_key":
                if os.environ.get("ANTHROPIC_API_KEY"):
                    configured = True
                    origin = "env"
                    state = "configured"
                elif load_credential(storage_provider, "api_key") or getattr(self.settings, "api_key", ""):
                    configured = True
                    origin = "file"
                    state = "configured"
            elif source == "openai_api_key":
                if os.environ.get("OPENAI_API_KEY"):
                    configured = True
                    origin = "env"
                    state = "configured"
                elif load_credential(storage_provider, "api_key"):
                    configured = True
                    origin = "file"
                    state = "configured"
            elif source in {"codex_subscription", "claude_subscription"}:
                binding = load_external_binding(storage_provider)
                if binding is not None:
                    external_state = describe_external_binding(binding)
                    configured = external_state.configured
                    origin = external_state.source
                    state = external_state.state
                    detail = external_state.detail
            elif source == "copilot_oauth":
                from illusion.api.copilot_auth import load_copilot_auth

                if load_copilot_auth():
                    configured = True
                    origin = "file"
                    state = "configured"
            elif load_credential(storage_provider, "api_key"):
                configured = True
                origin = "file"
                state = "configured"
            result[source] = {
                "configured": configured,
                "source": origin,
                "state": state,
                "detail": detail,
                "active": source == active_profile.auth_source,
                "active_profile": active_profile_name,
            }
        return result

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

            elif provider == "anthropic_claude":
                binding = load_external_binding(provider)
                if binding is not None:
                    configured = True
                    source = "external"

            elif provider == "openai":
                if os.environ.get("OPENAI_API_KEY"):
                    configured = True
                    source = "env"
                elif load_credential("openai", "api_key"):
                    configured = True
                    source = "file"

            elif provider == "openai_codex":
                binding = load_external_binding(provider)
                if binding is not None:
                    configured = True
                    source = "external"

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

    def get_profile_statuses(self) -> dict[str, Any]:
        """Return the available provider profiles and whether their auth is configured."""
        active = self.get_active_profile()
        auth_sources = self.get_auth_source_statuses()
        return {
            name: {
                "label": profile.label,
                "provider": profile.provider,
                "api_format": profile.api_format,
                "auth_source": profile.auth_source,
                "configured": bool(auth_sources.get(profile.auth_source, {}).get("configured")),
                "auth_state": str(auth_sources.get(profile.auth_source, {}).get("state", "missing")),
                "active": name == active,
                "base_url": profile.base_url,
                "model": display_model_setting(profile),
            }
            for name, profile in self.list_profiles().items()
        }

    def save_settings(self) -> None:
        """Persist the in-memory settings."""
        from illusion.config import save_settings

        save_settings(self.settings)

    def use_profile(self, name: str) -> None:
        """Activate a provider profile."""
        profiles = self.settings.merged_profiles()
        if name not in profiles:
            raise ValueError(f"Unknown provider profile: {name!r}")
        updated = self.settings.model_copy(update={"active_profile": name}).materialize_active_profile()
        self._settings = updated
        self.save_settings()
        log.info("Switched active profile to %s", name)

    def upsert_profile(self, name: str, profile: ProviderProfile) -> None:
        """Create or replace a provider profile."""
        profiles = self.settings.merged_profiles()
        profiles[name] = profile
        updated = self.settings.model_copy(update={"profiles": profiles})
        self._settings = updated.materialize_active_profile()
        self.save_settings()

    def update_profile(
        self,
        name: str,
        *,
        label: str | None = None,
        provider: str | None = None,
        api_format: str | None = None,
        base_url: str | None = None,
        auth_source: str | None = None,
        default_model: str | None = None,
        last_model: str | None = None,
    ) -> None:
        """Update a profile in-place."""
        profiles = self.settings.merged_profiles()
        if name not in profiles:
            raise ValueError(f"Unknown provider profile: {name!r}")
        current = profiles[name]
        next_provider = provider or current.provider
        next_format = api_format or current.api_format
        updates = {
            "label": label or current.label,
            "provider": next_provider,
            "api_format": next_format,
            "base_url": base_url if base_url is not None else current.base_url,
            "auth_source": auth_source or current.auth_source or default_auth_source_for_provider(next_provider, next_format),
            "default_model": default_model or current.default_model,
            "last_model": last_model if last_model is not None else current.last_model,
        }
        profiles[name] = current.model_copy(update=updates)
        updated = self.settings.model_copy(update={"profiles": profiles})
        self._settings = updated.materialize_active_profile()
        self.save_settings()

    def remove_profile(self, name: str) -> None:
        """Remove a non-built-in provider profile."""
        if name == self.get_active_profile():
            raise ValueError("Cannot remove the active profile.")
        if name in builtin_provider_profile_names():
            raise ValueError(f"Cannot remove built-in profile: {name}")
        profiles = self.settings.merged_profiles()
        if name not in profiles:
            raise ValueError(f"Unknown provider profile: {name!r}")
        del profiles[name]
        updated = self.settings.model_copy(update={"profiles": profiles})
        self._settings = updated.materialize_active_profile()
        self.save_settings()

    def switch_auth_source(self, auth_source: str, *, profile_name: str | None = None) -> None:
        """Switch the auth source for a profile."""
        if auth_source not in _AUTH_SOURCES:
            raise ValueError(f"Unknown auth source: {auth_source!r}. Known auth sources: {_AUTH_SOURCES}")
        target = profile_name or self.get_active_profile()
        self.update_profile(target, auth_source=auth_source)

    def switch_provider(self, name: str) -> None:
        """Backward-compatible switch entrypoint for profile/provider/auth source names."""
        if name in _AUTH_SOURCES:
            self.switch_auth_source(name)
            return
        profiles = self.list_profiles()
        if name in profiles:
            self.use_profile(name)
            return
        if name in _KNOWN_PROVIDERS:
            self.use_profile(_PROFILE_BY_PROVIDER.get(name, "openai-compatible" if name == "openai" else "claude-api"))
            return
        raise ValueError(
            f"Unknown provider or auth source: {name!r}. "
            f"Known providers: {_KNOWN_PROVIDERS}; auth sources: {_AUTH_SOURCES}"
        )

    def store_credential(self, provider: str, key: str, value: str) -> None:
        """Store a credential for the given provider."""
        store_credential(provider, key, value)
        # Keep the flattened active settings snapshot aligned for compatibility.
        if key == "api_key" and provider == auth_source_provider_name(self.settings.resolve_profile()[1].auth_source):
            try:
                updated = self.settings.model_copy(update={"api_key": value})
                self._settings = updated.materialize_active_profile()
                self.save_settings()
            except Exception as exc:
                log.warning("Could not sync api_key to settings: %s", exc)

    def clear_credential(self, provider: str) -> None:
        """Remove all stored credentials for the given provider."""
        clear_provider_credentials(provider)
        # Also clear api_key in settings if this is the active provider.
        if provider == auth_source_provider_name(self.settings.resolve_profile()[1].auth_source):
            try:
                updated = self.settings.model_copy(update={"api_key": ""})
                self._settings = updated.materialize_active_profile()
                self.save_settings()
            except Exception as exc:
                log.warning("Could not clear api_key from settings: %s", exc)
