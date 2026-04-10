"""
统一认证管理器模块
==================

本模块为 IllusionCode 提供统一的认证状态管理功能。

主要功能：
    - 管理提供商认证状态
    - 切换和配置提供商配置文件
    - 存储和加载凭据
    - 获取认证源配置状态

类说明：
    - AuthManager: 认证管理器类，负责所有认证相关的操作

使用示例：
    >>> from illusion.auth import AuthManager
    >>> manager = AuthManager()
    >>> status = manager.get_auth_status()
    >>> print(status)
"""

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

# 模块级日志记录器
log = logging.getLogger(__name__)

# Illusion 已知的提供商列表
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

# 支持的认证源列表
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

# 提供商到配置文件的映射关系
_PROFILE_BY_PROVIDER = {
    "anthropic": "claude-api",
    "anthropic_claude": "claude-subscription",
    "openai": "openai-compatible",
    "openai_codex": "codex",
    "copilot": "copilot",
}


class AuthManager:
    """认证管理器
    
    提供商认证状态的中央管理类。
    通过 :mod:`illusion.auth.storage` 读写凭据，
    并通过设置跟踪当前活动的提供商。
    
    Attributes:
        _settings: 设置对象（延迟加载）
    
    使用示例：
        >>> manager = AuthManager()
        >>> provider = manager.get_active_provider()
        >>> print(f"当前提供商: {provider}")
    """

    def __init__(self, settings: Any | None = None) -> None:
        # 延迟加载设置，以便管理器可以在不导入完整配置子系统的情况下实例化
        self._settings = settings

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------

    @property
    def settings(self) -> Any:
        """获取设置对象（延迟加载）"""
        if self._settings is None:
            from illusion.config import load_settings

            self._settings = load_settings()
        return self._settings

    def _provider_from_settings(self) -> str:
        """从设置中获取当前的提供商名称
        
        Returns:
            str: 提供商名称
        """
        _, profile = self.settings.resolve_profile()
        return profile.provider

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def get_active_provider(self) -> str:
        """获取当前活动的提供商名称
        
        Returns:
            str: 提供商名称
        """
        return self._provider_from_settings()

    def get_active_profile(self) -> str:
        """获取当前活动的提供商配置文件名称
        
        Returns:
            str: 配置文件名称
        """
        return self.settings.resolve_profile()[0]

    def list_profiles(self) -> dict[str, ProviderProfile]:
        """获取配置的提供商配置文件列表
        
        Returns:
            dict[str, ProviderProfile]: 配置文件字典
        """
        return self.settings.merged_profiles()

    def get_auth_source_statuses(self) -> dict[str, Any]:
        """获取认证源配置状态
        
        Returns:
            dict[str, Any]: 认证源状态字典
        """
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
        """获取所有已知提供商的认证状态
        
        返回以提供商名称为键的字典，结构如下::
        
            {
                "anthropic": {
                    "configured": True,
                    "source": "env",   # "env", "file", "keyring", 或 "missing"
                    "active": True,
                },
                ...
            }
        
        Returns:
            dict[str, Any]: 提供商认证状态字典
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
                # 这些通常使用环境级凭据（AWS/GCP）
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
        """获取可用的提供商配置文件及其认证配置状态
        
        Returns:
            dict[str, Any]: 配置文件状态字典
        """
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
        """保存内存中的设置到持久化存储"""
        from illusion.config import save_settings

        save_settings(self.settings)

    def use_profile(self, name: str) -> None:
        """激活指定的提供商配置文件
        
        Args:
            name: 配置文件名称
        
        Raises:
            ValueError: 配置文件不存在
        """
        profiles = self.settings.merged_profiles()
        if name not in profiles:
            raise ValueError(f"Unknown provider profile: {name!r}")
        updated = self.settings.model_copy(update={"active_profile": name}).materialize_active_profile()
        self._settings = updated
        self.save_settings()
        log.info("Switched active profile to %s", name)

    def upsert_profile(self, name: str, profile: ProviderProfile) -> None:
        """创建或替换提供商配置文件
        
        Args:
            name: 配置文件名称
            profile: 配置文件对象
        """
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
        """原地更新配置文件
        
        Args:
            name: 配置文件名称
            label: 显示标签
            provider: 提供商名称
            api_format: API 格式
            base_url: 基础 URL
            auth_source: 认证源
            default_model: 默认模型
            last_model: 上次使用的模型
        
        Raises:
            ValueError: 配置文件不存在
        """
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
        """移除非内置的提供商配置文件
        
        Args:
            name: 配置文件名称
        
        Raises:
            ValueError: 配置文件不存在、正在使用或为内置配置
        """
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
        """切换配置文件的认证源
        
        Args:
            auth_source: 认证源名称
            profile_name: 配置文件名称（可选，默认当前活动配置）
        
        Raises:
            ValueError: 认证源不存在
        """
        if auth_source not in _AUTH_SOURCES:
            raise ValueError(f"Unknown auth source: {auth_source!r}. Known auth sources: {_AUTH_SOURCES}")
        target = profile_name or self.get_active_profile()
        self.update_profile(target, auth_source=auth_source)

    def switch_provider(self, name: str) -> None:
        """向后兼容的切换入口，用于配置文件/提供商/认证源名称
        
        Args:
            name: 提供商名称、认证源名称或配置文件名称
        
        Raises:
            ValueError: 名称不存在
        """
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
        """存储给定提供商的凭据
        
        Args:
            provider: 提供商名称
            key: 键名
            value: 凭据值
        """
        store_credential(provider, key, value)
        # 保持扁平化的活动设置快照同步以保持兼容性
        if key == "api_key" and provider == auth_source_provider_name(self.settings.resolve_profile()[1].auth_source):
            try:
                updated = self.settings.model_copy(update={"api_key": value})
                self._settings = updated.materialize_active_profile()
                self.save_settings()
            except Exception as exc:
                log.warning("Could not sync api_key to settings: %s", exc)

    def clear_credential(self, provider: str) -> None:
        """删除给定提供商的所有存储凭据
        
        Args:
            provider: 提供商名称
        """
        clear_provider_credentials(provider)
        # 如果这是活动提供商，也清除设置中的 api_key
        if provider == auth_source_provider_name(self.settings.resolve_profile()[1].auth_source):
            try:
                updated = self.settings.model_copy(update={"api_key": ""})
                self._settings = updated.materialize_active_profile()
                self.save_settings()
            except Exception as exc:
                log.warning("Could not clear api_key from settings: %s", exc)
