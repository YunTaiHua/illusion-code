"""
Settings 模型和加载逻辑模块
===========================

本模块提供 IllusionCode 的设置管理功能，包括：
- Settings: 主设置模型
- ProviderProfile: 提供商配置
- 各种设置加载和保存函数

设置解析优先级（从高到低）：
    1. CLI 参数
    2. 环境变量（ANTHROPIC_API_KEY, illusion_MODEL 等）
    3. 配置文件（~/.illusion/settings.json）
    4. 默认值

类说明：
    - Settings: 主设置模型，包含 API 配置、权限、钩子等
    - ProviderProfile: 提供商工作流配置
    - PermissionSettings: 权限模式配置
    - MemorySettings: 记忆系统配置
    - SandboxSettings: 沙箱运行时配置

使用示例：
    >>> from illusion.config.settings import load_settings, Settings
    >>> settings = load_settings()
    >>> profile_name, profile = settings.resolve_profile()
    >>> print(f"当前提供商: {profile.provider}")
"""

from __future__ import annotations

import json  # 导入 json 模块用于配置文件读写
import os  # 导入 os 模块用于环境变量访问
from dataclasses import dataclass  # 导入 dataclass 用于创建不可变数据结构
from pathlib import Path  # 导入 Path 用于路径处理
from typing import Any  # 导入 Any 类型用于泛型

from pydantic import BaseModel, Field  # 导入 pydantic 模型基类

from illusion.hooks.schemas import HookDefinition  # 导入钩子定义
from illusion.mcp.types import McpServerConfig  # 导入 MCP 服务器配置
from illusion.permissions.modes import PermissionMode  # 导入权限模式


class PathRuleConfig(BaseModel):
    """路径权限规则配置
    
    使用 glob 模式定义路径级别的权限规则。
    
    Attributes:
        pattern: glob 模式字符串
        allow: 是否允许访问，默认为 True
    """

    pattern: str  # glob 模式，用于匹配路径
    allow: bool = True  # 默认为允许访问


class PermissionSettings(BaseModel):
    """权限模式配置
    
    配置系统的权限控制和行为限制。
    
    Attributes:
        mode: 权限模式
        allowed_tools: 允许的工具列表
        denied_tools: 拒绝的工具列表
        path_rules: 路径规则列表
        denied_commands: 拒绝的命令列表
    """

    mode: PermissionMode = PermissionMode.DEFAULT  # 权限模式，默认为默认模式
    allowed_tools: list[str] = Field(default_factory=list)  # 允许的工具列表
    denied_tools: list[str] = Field(default_factory=list)  # 拒绝的工具列表
    path_rules: list[PathRuleConfig] = Field(default_factory=list)  # 路径权限规则
    denied_commands: list[str] = Field(default_factory=list)  # 拒绝的命令列表


class MemorySettings(BaseModel):
    """记忆系统配置
    
    配置 AI 记忆系统的行为和限制。
    
    Attributes:
        enabled: 是否启用记忆功能
        max_files: 最大记忆文件数
        max_entrypoint_lines: 最大入口文件行数
    """

    enabled: bool = True  # 默认启用记忆功能
    max_files: int = 5  # 默认最多记忆 5 个文件
    max_entrypoint_lines: int = 200  # 默认入口文件最多 200 行


class SandboxNetworkSettings(BaseModel):
    """沙箱网络限制配置
    
    传递给沙箱运行时的操作系统级网络限制配置。
    
    Attributes:
        allowed_domains: 允许访问的域名列表
        denied_domains: 拒绝访问的域名列表
    """

    allowed_domains: list[str] = Field(default_factory=list)  # 允许的域名
    denied_domains: list[str] = Field(default_factory=list)  # 拒绝的域名


class SandboxFilesystemSettings(BaseModel):
    """沙箱文件系统限制配置
    
    传递给沙箱运行时的操作系统级文件系统限制配置。
    
    Attributes:
        allow_read: 允许读取的路径列表
        deny_read: 拒绝读取的路径列表
        allow_write: 允许写入的路径列表
        deny_write: 拒绝写入的路径列表
    """

    allow_read: list[str] = Field(default_factory=list)  # 允许读取的路径
    deny_read: list[str] = Field(default_factory=list)  # 拒绝读取的路径
    allow_write: list[str] = Field(default_factory=lambda: ["."])  # 默认允许写入当前目录
    deny_write: list[str] = Field(default_factory=list)  # 拒绝写入的路径


class SandboxSettings(BaseModel):
    """沙箱运行时集成配置
    
    配置与沙箱运行时的集成选项。
    
    Attributes:
        enabled: 是否启用沙箱
        fail_if_unavailable: 沙箱不可用时是否失败
        enabled_platforms: 启用的平台列表
        network: 网络限制配置
        filesystem: 文件系统限制配置
    """

    enabled: bool = False  # 默认不启用沙箱
    fail_if_unavailable: bool = False  # 沙箱不可用时不失败
    enabled_platforms: list[str] = Field(default_factory=list)  # 启用的平台
    network: SandboxNetworkSettings = Field(default_factory=SandboxNetworkSettings)  # 网络配置
    filesystem: SandboxFilesystemSettings = Field(default_factory=SandboxFilesystemSettings)  # 文件系统配置


class ProviderProfile(BaseModel):
    """命名提供商工作流配置
    
    定义一个完整的提供商配置，包括 API 格式、认证方式、默认模型等。
    
    Attributes:
        label: 显示标签
        provider: 提供商名称
        api_format: API 格式（anthropic、openai、copilot）
        auth_source: 认证来源
        default_model: 默认模型
        base_url: 可选的 base URL
        last_model: 上次使用的模型
    """

    label: str  # 显示名称
    provider: str  # 提供商标识符
    api_format: str  # API 格式
    auth_source: str  # 认证来源
    default_model: str  # 默认模型
    base_url: str | None = None  # 可选的 base URL
    last_model: str | None = None  # 上次使用的模型

    @property
    def resolved_model(self) -> str:
        """返回此配置文件的活跃模型
        
        根据 last_model 和 default_model 解析出实际使用的模型名称。
        
        Returns:
            str: 解析后的模型名称
        """
        return resolve_model_setting(
            (self.last_model or "").strip() or self.default_model,
            self.provider,
            default_model=self.default_model,
        )


@dataclass(frozen=True)
class ResolvedAuth:
    """规范化的认证材料
    
    用于构造 API 客户端的标准化认证信息。
    
    Attributes:
        provider: 提供商名称
        auth_kind: 认证类型
        value: 认证值
        source: 认证来源
        state: 状态（默认为 "configured"）
    """

    provider: str  # 提供商
    auth_kind: str  # 认证类型（api_key、oauth 等）
    value: str  # 认证值
    source: str  # 来源描述
    state: str = "configured"  # 配置状态


# Claude 模型别名选项元组，包含（值、显示名、描述）的三元组
CLAUDE_MODEL_ALIAS_OPTIONS: tuple[tuple[str, str, str], ...] = (
    ("default", "Default", "Recommended model for this profile"),  # 默认选项
    ("best", "Best", "Most capable available model"),  # 最佳模型
    ("sonnet", "Sonnet", "Latest Sonnet for everyday coding"),  # 最新 Sonnet
    ("opus", "Opus", "Latest Opus for complex reasoning"),  # 最新 Opus
    ("haiku", "Haiku", "Fastest Claude model"),  # 最快的 Haiku
    ("sonnet[1m]", "Sonnet (1M context)", "Latest Sonnet with 1M context"),  # 1M 上下文 Sonnet
    ("opus[1m]", "Opus (1M context)", "Latest Opus with 1M context"),  # 1M 上下文 Opus
    ("opusplan", "Opus Plan Mode", "Use Opus in plan mode and Sonnet otherwise"),  # 计划模式
)

# Claude 别名到实际模型名称的映射字典
_CLAUDE_ALIAS_TARGETS: dict[str, str] = {
    "sonnet": "claude-sonnet-4-6",  # Sonnet 别名
    "opus": "claude-opus-4-6",  # Opus 别名
    "haiku": "claude-haiku-4-5",  # Haiku 别名
    "sonnet[1m]": "claude-sonnet-4-6[1m]",  # 1M 上下文 Sonnet
    "opus[1m]": "claude-opus-4-6[1m]",  # 1M 上下文 Opus
}


def normalize_anthropic_model_name(model: str) -> str:
    """标准化 Anthropic 模型名称
    
    与 Hermes 一样标准化模型名称：
    - 去除 "anthropic/" 前缀（如果存在）
    - 将点分隔的 Claude 版本号转换为 Anthropic 的连字符形式
    
    Args:
        model: 原始模型名称
    
    Returns:
        str: 标准化后的模型名称
    """
    normalized = model.strip()  # 去除首尾空白
    lower = normalized.lower()  # 转换为小写用于比较
    # 去除 anthropic/ 前缀
    if lower.startswith("anthropic/"):
        normalized = normalized[len("anthropic/"):]
        lower = normalized.lower()
    # 如果以 claude- 开头，将点转换为连字符
    if lower.startswith("claude-"):
        return normalized.replace(".", "-")
    return normalized


def default_provider_profiles() -> dict[str, ProviderProfile]:
    """返回内置的提供商工作流目录
    
    Returns:
        dict[str, ProviderProfile]: 提供商名称到配置文件的映射
    """
    return {
        "claude-api": ProviderProfile(
            label="Claude API",  # Claude API 配置
            provider="anthropic",
            api_format="anthropic",
            auth_source="anthropic_api_key",
            default_model="claude-sonnet-4-6",
        ),
        "claude-subscription": ProviderProfile(
            label="Claude Subscription",  # Claude 订阅配置
            provider="anthropic_claude",
            api_format="anthropic",
            auth_source="claude_subscription",
            default_model="claude-sonnet-4-6",
        ),
        "openai-compatible": ProviderProfile(
            label="OpenAI Compatible",  # OpenAI 兼容配置
            provider="openai",
            api_format="openai",
            auth_source="openai_api_key",
            default_model="gpt-5.4",
        ),
        "codex": ProviderProfile(
            label="Codex Subscription",  # Codex 订阅配置
            provider="openai_codex",
            api_format="openai",
            auth_source="codex_subscription",
            default_model="gpt-5.4",
        ),
        "copilot": ProviderProfile(
            label="GitHub Copilot",  # GitHub Copilot 配置
            provider="copilot",
            api_format="copilot",
            auth_source="copilot_oauth",
            default_model="gpt-5.4",
        ),
    }


def builtin_provider_profile_names() -> set[str]:
    """返回内置提供商配置文件的名称集合
    
    Returns:
        set[str]: 内置配置文件名称集合
    """
    return set(default_provider_profiles())


def is_claude_family_provider(provider: str) -> bool:
    """返回该提供商是否为 Claude/Anthropic 工作流
    
    Args:
        provider: 提供商标识符
    
    Returns:
        bool: 是否为 Claude 家族提供商
    """
    return provider in {"anthropic", "anthropic_claude"}


def display_model_setting(profile: ProviderProfile) -> str:
    """返回配置文件的用户面向模型设置
    
    Args:
        profile: 提供商配置文件
    
    Returns:
        str: 显示用的模型设置字符串
    """
    configured = (profile.last_model or "").strip()  # 获取已配置的模型
    # 如果未配置且是 Claude 家族，返回 "default"
    if not configured and is_claude_family_provider(profile.provider):
        return "default"
    return configured or profile.default_model


def resolve_model_setting(
    model_setting: str,
    provider: str,
    *,
    default_model: str | None = None,
    permission_mode: str | None = None,
) -> str:
    """将用户面向的模型设置解析为具体的运行时模型 ID
    
    Args:
        model_setting: 用户配置的模型名称或别名
        provider: 提供商标识符
        default_model: 可选的默认模型
        permission_mode: 可选的权限模式
    
    Returns:
        str: 解析后的具体模型 ID
    """
    configured = model_setting.strip()  # 去除空白
    normalized = configured.lower()  # 转换为小写

    # 处理 "default" 或空值
    if not configured or normalized == "default":
        fallback = (default_model or "").strip()  # 获取备用模型
        if fallback and fallback.lower() != "default":
            # 递归解析备用模型
            return resolve_model_setting(
                fallback,
                provider,
                default_model=None,
                permission_mode=permission_mode,
            )
        # Claude 家族默认使用 sonnet
        if is_claude_family_provider(provider):
            return _CLAUDE_ALIAS_TARGETS["sonnet"]
        return "gpt-5.4"

    # 处理 Claude 家族提供商的别名
    if is_claude_family_provider(provider):
        if normalized == "best":
            return _CLAUDE_ALIAS_TARGETS["opus"]  # best 返回 opus
        if normalized == "opusplan":
            # 根据权限模式决定使用 opus 还是 sonnet
            if permission_mode == PermissionMode.PLAN.value:
                return _CLAUDE_ALIAS_TARGETS["opus"]
            return _CLAUDE_ALIAS_TARGETS["sonnet"]
        if normalized in _CLAUDE_ALIAS_TARGETS:
            return _CLAUDE_ALIAS_TARGETS[normalized]  # 直接映射别名
        return normalize_anthropic_model_name(configured)  # 标准化模型名

    # 处理 OpenAI 系列提供商的 default/best
    if provider in {"openai", "openai_codex", "copilot"} and normalized in {"default", "best"}:
        return "gpt-5.4"

    return configured  # 直接返回原始配置


def auth_source_provider_name(auth_source: str) -> str:
    """将认证来源映射到存储/运行时提供商名称
    
    Args:
        auth_source: 认证来源标识符
    
    Returns:
        str: 映射后的提供商名称
    """
    mapping = {
        "anthropic_api_key": "anthropic",  # Anthropic API 密钥
        "openai_api_key": "openai",  # OpenAI API 密钥
        "codex_subscription": "openai_codex",  # Codex 订阅
        "claude_subscription": "anthropic_claude",  # Claude 订阅
        "copilot_oauth": "copilot",  # Copilot OAuth
        "dashscope_api_key": "dashscope",  # 阿里 DashScope
        "bedrock_api_key": "bedrock",  # AWS Bedrock
        "vertex_api_key": "vertex",  # Google Vertex
    }
    return mapping.get(auth_source, auth_source)


def default_auth_source_for_provider(provider: str, api_format: str | None = None) -> str:
    """推断提供商的默认认证来源
    
    Args:
        provider: 提供商标识符
        api_format: 可选的 API 格式
    
    Returns:
        str: 默认认证来源
    """
    if provider == "anthropic_claude":
        return "claude_subscription"
    if provider == "openai_codex":
        return "codex_subscription"
    if provider == "copilot":
        return "copilot_oauth"
    if provider == "dashscope":
        return "dashscope_api_key"
    if provider == "bedrock":
        return "bedrock_api_key"
    if provider == "vertex":
        return "vertex_api_key"
    if provider == "openai" or api_format == "openai":
        return "openai_api_key"
    return "anthropic_api_key"


def _slugify_profile_name(value: str) -> str:
    """将配置文件名转换为 URL 友好的 slug 格式
    
    Args:
        value: 原始名称
    
    Returns:
        str: slug 格式的名称
    """
    # 保留字母数字，将其他字符替换为连字符
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")
    # 替换连续出现的连字符
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned or "custom"


def _infer_profile_name_from_flat_settings(settings: "Settings") -> str:
    """从扁平设置推断配置文件名称
    
    Args:
        settings: 扁平设置的 Settings 实例
    
    Returns:
        str: 推断的配置文件名称
    """
    provider = (settings.provider or "").strip()  # 获取提供商
    if provider == "openai_codex":
        return "codex"
    if provider == "anthropic_claude":
        return "claude-subscription"
    if provider == "copilot" or settings.api_format == "copilot":
        return "copilot"
    if provider == "openai" and not settings.base_url:
        return "openai-compatible"
    if provider == "anthropic" and not settings.base_url:
        return "claude-api"
    if settings.base_url:
        # 从 base URL 提取名称
        return _slugify_profile_name(Path(settings.base_url).name or settings.base_url)
    if provider:
        return _slugify_profile_name(provider)
    return "claude-api"


def _profile_from_flat_settings(settings: "Settings") -> tuple[str, ProviderProfile]:
    """从扁平设置创建配置文件
    
    如果存在匹配的内置配置文件，则使用它；否则创建新的配置文件。
    
    Args:
        settings: 扁平设置的 Settings 实例
    
    Returns:
        tuple[str, ProviderProfile]: (配置文件名, 配置文件对象)
    """
    defaults = default_provider_profiles()  # 获取内置配置
    name = _infer_profile_name_from_flat_settings(settings)  # 推断名称
    existing = defaults.get(name)  # 检查是否存在
    # 如果存在匹配的内置配置
    if existing is not None and (
        existing.provider == settings.provider or not settings.provider
    ) and (
        existing.api_format == settings.api_format
    ) and (
        existing.base_url == settings.base_url
    ):
        profile = existing.model_copy(
            update={
                "last_model": settings.model or existing.resolved_model,  # 更新最后使用的模型
            }
        )
        return name, profile

    # 创建新的配置文件
    provider = settings.provider or ("copilot" if settings.api_format == "copilot" else ("openai" if settings.api_format == "openai" else "anthropic"))
    profile = ProviderProfile(
        label=f"Imported {provider}",  # 导入的提供商
        provider=provider,
        api_format=settings.api_format,
        auth_source=default_auth_source_for_provider(provider, settings.api_format),  # 默认认证来源
        default_model=settings.model or defaults.get("claude-api", ProviderProfile(
            label="Claude API",
            provider="anthropic",
            api_format="anthropic",
            auth_source="anthropic_api_key",
            default_model="sonnet",
        )).default_model,
        last_model=settings.model or None,
        base_url=settings.base_url,
    )
    return name, profile


class Settings(BaseModel):
    """IllusionCode 主设置模型
    
    包含所有应用配置选项，包括 API 配置、权限设置、钩子、记忆系统等。
    
    Attributes:
        api_key: API 密钥
        model: 默认模型
        max_tokens: 最大 token 数
        base_url: API base URL
        api_format: API 格式（anthropic/openai/copilot）
        provider: 提供商标识符
        active_profile: 活跃的配置文件名
        profiles: 所有配置文件字典
        max_turns: 最大对话轮数
        system_prompt: 系统提示词
        permission: 权限设置
        hooks: 钩子字典
        memory: 记忆设置
        sandbox: 沙箱设置
        enabled_plugins: 启用的插件字典
        mcp_servers: MCP 服务器配置字典
        theme: UI 主题
        ui_language: UI 语言
        output_style: 输出样式
        fast_mode: 是否启用快速模式
        effort: 工作量级别
        passes: 运行次数
        verbose: 是否详细输出
    """

    # API 配置
    api_key: str = ""  # API 密钥
    model: str = "claude-sonnet-4-6"  # 默认模型
    max_tokens: int = 16384  # 最大 token 数
    base_url: str | None = None  # API base URL
    api_format: str = "anthropic"  # API 格式
    provider: str = ""  # 提供商
    active_profile: str = "claude-api"  # 活跃配置文件
    profiles: dict[str, ProviderProfile] = Field(default_factory=dict)  # 用户配置的配置文件（不包含内置默认）
    max_turns: int = 200  # 最大对话轮数

    # 行为配置
    system_prompt: str | None = None  # 系统提示词
    permission: PermissionSettings = Field(default_factory=PermissionSettings)  # 权限设置
    hooks: dict[str, list[HookDefinition]] = Field(default_factory=dict)  # 钩子
    memory: MemorySettings = Field(default_factory=MemorySettings)  # 记忆设置
    sandbox: SandboxSettings = Field(default_factory=SandboxSettings)  # 沙箱设置
    enabled_plugins: dict[str, bool] = Field(default_factory=dict)  # 启用的插件
    mcp_servers: dict[str, McpServerConfig] = Field(default_factory=dict)  # MCP 服务器配置

    # UI 配置
    theme: str = "default"  # UI 主题
    ui_language: str = "zh-CN"  # UI 语言
    output_style: str = "default"  # 输出样式
    fast_mode: bool = False  # 快速模式
    effort: str = "medium"  # 工作量级别
    passes: int = 1  # 运行次数
    verbose: bool = False  # 详细输出

    def merged_profiles(self) -> dict[str, ProviderProfile]:
        """返回保存的配置文件中合并了内置目录的配置文件字典
        
        内置配置文件会被用户保存的配置覆盖。
        
        Returns:
            dict[str, ProviderProfile]: 合并后的配置文件字典
        """
        merged = default_provider_profiles()  # 从内置配置开始
        # 用保存的配置覆盖
        merged.update(
            {
                name: (
                    profile.model_copy(deep=True)  # 深拷贝配置文件
                    if isinstance(profile, ProviderProfile)
                    else ProviderProfile.model_validate(profile)  # 验证配置
                )
                for name, profile in self.profiles.items()
            }
        )
        return merged

    def resolve_profile(self, name: str | None = None) -> tuple[str, ProviderProfile]:
        """返回活跃的提供商配置文件
        
        如果指定的名称不存在，会从扁平字段推断并创建配置文件。
        
        Args:
            name: 可选的配置文件名称，默认使用 active_profile
        
        Returns:
            tuple[str, ProviderProfile]: (配置文件名, 配置文件对象)
        """
        profiles = self.merged_profiles()  # 获取合并后的配置文件
        profile_name = (name or self.active_profile or "").strip() or "claude-api"
        if profile_name not in profiles:
            # 从扁平设置创建配置文件
            fallback_name, fallback = _profile_from_flat_settings(self)
            profiles[fallback_name] = fallback
            profile_name = fallback_name
        return profile_name, profiles[profile_name].model_copy(deep=True)

    def materialize_active_profile(self) -> Settings:
        """将活跃配置文件投影回传统的扁平设置字段
        
        用于保持与仍在使用扁平字段的调用者的兼容性。
        
        Returns:
            Settings: 更新后的 Settings 实例
        """
        profile_name, profile = self.resolve_profile()
        configured_model = (profile.last_model or "").strip() or profile.default_model
        return self.model_copy(
            update={
                "active_profile": profile_name,  # 更新活跃配置文件名
                "profiles": self.merged_profiles(),  # 更新配置文件字典
                "provider": profile.provider,  # 更新提供商
                "api_format": profile.api_format,  # 更新 API 格式
                "base_url": profile.base_url,  # 更新 base URL
                "model": resolve_model_setting(  # 解析模型名称
                    configured_model,
                    profile.provider,
                    default_model=profile.default_model,
                    permission_mode=self.permission.mode.value,
                ),
            }
        )

    def sync_active_profile_from_flat_fields(self) -> Settings:
        """将传统的扁平提供商字段同步回活跃配置文件
        
        这保持了与仍在直接设置顶层 provider/api_format/base_url/model
        的调用者的兼容性。
        
        Returns:
            Settings: 更新后的 Settings 实例
        """
        profile_name, profile = self.resolve_profile()
        next_provider = (self.provider or "").strip() or profile.provider
        next_api_format = (self.api_format or "").strip() or profile.api_format
        next_base_url = self.base_url if self.base_url is not None else profile.base_url
        flat_model = (self.model or "").strip()
        resolved_profile_model = resolve_model_setting(
            (profile.last_model or "").strip() or profile.default_model,
            profile.provider,
            default_model=profile.default_model,
            permission_mode=self.permission.mode.value,
        )
        # 如果扁平模型与解析后的模型不同，使用扁平模型
        if flat_model and flat_model != resolved_profile_model:
            next_model = flat_model
        else:
            next_model = profile.last_model
        # 确定认证来源
        current_default_auth = default_auth_source_for_provider(profile.provider, profile.api_format)
        next_auth_source = profile.auth_source
        if not next_auth_source or next_auth_source == current_default_auth:
            next_auth_source = default_auth_source_for_provider(next_provider, next_api_format)

        # 创建更新后的配置文件
        updated_profile = profile.model_copy(
            update={
                "provider": next_provider,
                "api_format": next_api_format,
                "base_url": next_base_url,
                "auth_source": next_auth_source,
                "last_model": next_model,
            }
        )
        profiles = self.merged_profiles()
        profiles[profile_name] = updated_profile
        return self.model_copy(
            update={
                "active_profile": profile_name,
                "profiles": profiles,
            }
        )

    def resolve_api_key(self) -> str:
        """解析 API 密钥，优先级：实例值 > 环境变量 > 空
        
        对于 copilot 格式，密钥通过 oh auth copilot-login 单独管理，
        此方法不会被调用。
        
        Returns:
            str: API 密钥字符串
        
        Raises:
            ValueError: 未找到密钥时抛出
        """
        profile_name, profile = self.resolve_profile()
        del profile_name
        # Codex 使用单独的认证方式
        if profile.provider == "openai_codex":
            return self.resolve_auth().value
        # Claude 订阅使用 token 而非 API 密钥
        if profile.provider == "anthropic_claude":
            raise ValueError(
                "Current provider uses Anthropic auth tokens instead of API keys. "
                "Use resolve_auth() for runtime credential resolution."
            )
        # Copilot 格式管理自己的认证
        if profile.api_format == "copilot":
            return "copilot-managed"

        # 检查实例级别的 api_key
        if self.api_key:
            return self.api_key

        # 检查环境变量 ANTHROPIC_API_KEY
        env_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if env_key:
            return env_key

        # 对于 openai 格式的提供商，也检查 OPENAI_API_KEY
        openai_key = os.environ.get("OPENAI_API_KEY", "")
        if openai_key:
            return openai_key

        raise ValueError(
            "No API key found. Set ANTHROPIC_API_KEY (or OPENAI_API_KEY for openai-format "
            "providers) environment variable, or configure api_key in "
            "~/.illusion/settings.json"
        )

    def resolve_auth(self) -> ResolvedAuth:
        """解析当前提供商的认证，包括订阅桥接
        
        Returns:
            ResolvedAuth: 解析后的认证对象
        
        Raises:
            ValueError: 认证配置错误时抛出
        """
        _, profile = self.resolve_profile()
        provider = profile.provider.strip()  # 清理提供商名称
        auth_source = profile.auth_source.strip() or default_auth_source_for_provider(provider, profile.api_format)
        
        # 处理第三方订阅（codex、claude）
        if auth_source in {"codex_subscription", "claude_subscription"}:
            from illusion.auth.external import (
                is_third_party_anthropic_endpoint,
                load_external_credential,
            )
            from illusion.auth.storage import load_external_binding

            # Claude 订阅只支持直接 Anthropic/Claude 端点
            if auth_source == "claude_subscription" and is_third_party_anthropic_endpoint(profile.base_url):
                raise ValueError(
                    "Claude subscription auth only supports direct Anthropic/Claude endpoints. "
                    "Use an API-key-backed Anthropic-compatible profile for third-party base URLs."
                )
            # 加载外部绑定
            binding = load_external_binding(auth_source_provider_name(auth_source))
            if binding is None:
                raise ValueError(
                    f"No external auth binding found for {auth_source}. Run 'oh auth "
                    f"{'codex-login' if auth_source == 'codex_subscription' else 'claude-login'}' first."
                )
            # 加载外部凭证，必要时刷新
            credential = load_external_credential(
                binding,
                refresh_if_needed=(auth_source == "claude_subscription"),
            )
            return ResolvedAuth(
                provider=provider,
                auth_kind=credential.auth_kind,
                value=credential.value,
                source=f"external:{credential.source_path}",
                state="configured",
            )

        # Copilot OAuth 认证
        if auth_source == "copilot_oauth":
            return ResolvedAuth(
                provider="copilot",
                auth_kind="oauth_device",
                value="copilot-managed",
                source="copilot",
                state="configured",
            )

        # 从存储提供商加载
        storage_provider = auth_source_provider_name(auth_source)
        explicit_key = self.api_key  # 检查显式密钥
        if explicit_key:
            return ResolvedAuth(
                provider=provider or storage_provider,
                auth_kind="api_key",
                value=explicit_key,
                source="settings_or_env",
                state="configured",
            )

        # 检查环境变量
        env_var = {
            "anthropic_api_key": "ANTHROPIC_API_KEY",
            "openai_api_key": "OPENAI_API_KEY",
            "dashscope_api_key": "DASHSCOPE_API_KEY",
        }.get(auth_source)
        if env_var:
            env_value = os.environ.get(env_var, "")
            if env_value:
                return ResolvedAuth(
                    provider=provider or storage_provider,
                    auth_kind="api_key",
                    value=env_value,
                    source=f"env:{env_var}",
                    state="configured",
                )

        # 从文件存储加载
        from illusion.auth.storage import load_credential

        stored = load_credential(storage_provider, "api_key")
        if stored:
            return ResolvedAuth(
                provider=provider or storage_provider,
                auth_kind="api_key",
                value=stored,
                source=f"file:{storage_provider}",
                state="configured",
            )

        raise ValueError(
            f"No credentials found for auth source '{auth_source}'. "
            "Configure the matching provider or environment variable first."
        )

    def merge_cli_overrides(self, **overrides: Any) -> Settings:
        """返回应用了 CLI 覆盖的新 Settings（仅非 None 值）
        
        Args:
            **overrides: 要覆盖的字段
        
        Returns:
            Settings: 应用覆盖后的新实例
        """
        updates = {k: v for k, v in overrides.items() if v is not None}  # 过滤掉 None 值
        merged = self.model_copy(update=updates)  # 应用更新
        if not updates:
            return merged
        # 检查是否有配置文件相关的键
        profile_keys = {"model", "base_url", "api_format", "provider", "api_key", "active_profile", "profiles"}
        if profile_keys.isdisjoint(updates):
            return merged
        return merged.sync_active_profile_from_flat_fields().materialize_active_profile()


def _apply_env_overrides(settings: Settings) -> Settings:
    """在加载的设置上应用支持的环境变量覆盖
    
    Args:
        settings: 原始设置
    
    Returns:
        Settings: 应用环境变量覆盖后的设置
    """
    updates: dict[str, Any] = {}  # 更新字典
    
    # 模型覆盖：ANTHROPIC_MODEL 或 illusion_MODEL
    model = os.environ.get("ANTHROPIC_MODEL") or os.environ.get("illusion_MODEL")
    if model:
        updates["model"] = model

    # base URL 覆盖
    base_url = os.environ.get("ANTHROPIC_BASE_URL") or os.environ.get("illusion_BASE_URL")
    if base_url:
        updates["base_url"] = base_url

    # max_tokens 覆盖
    max_tokens = os.environ.get("illusion_MAX_TOKENS")
    if max_tokens:
        updates["max_tokens"] = int(max_tokens)

    # max_turns 覆盖
    max_turns = os.environ.get("illusion_MAX_TURNS")
    if max_turns:
        updates["max_turns"] = int(max_turns)

    # API 密钥覆盖
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if api_key:
        updates["api_key"] = api_key

    # API 格式覆盖
    api_format = os.environ.get("illusion_API_FORMAT")
    if api_format:
        updates["api_format"] = api_format

    # 提供商覆盖
    provider = os.environ.get("illusion_PROVIDER")
    if provider:
        updates["provider"] = provider

    # 沙箱设置覆盖
    sandbox_enabled = os.environ.get("illusion_SANDBOX_ENABLED")
    sandbox_fail = os.environ.get("illusion_SANDBOX_FAIL_IF_UNAVAILABLE")
    sandbox_updates: dict[str, Any] = {}
    if sandbox_enabled is not None:
        sandbox_updates["enabled"] = _parse_bool_env(sandbox_enabled)
    if sandbox_fail is not None:
        sandbox_updates["fail_if_unavailable"] = _parse_bool_env(sandbox_fail)
    if sandbox_updates:
        updates["sandbox"] = settings.sandbox.model_copy(update=sandbox_updates)

    if not updates:
        return settings
    return settings.model_copy(update=updates)


def _parse_bool_env(value: str) -> bool:
    """解析布尔环境变量
    
    Args:
        value: 环境变量值字符串
    
    Returns:
        bool: 解析后的布尔值
    """
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_settings(config_path: Path | None = None) -> Settings:
    """从配置文件加载设置，与默认值合并
    
    如果配置文件不存在或缺少必要字段，会使用默认值并创建配置文件。
    
    Args:
        config_path: settings.json 的路径。如果为 None，使用默认位置。
    
    Returns:
        Settings: 文件值与默认值合并后的 Settings 实例
    """
    if config_path is None:
        from illusion.config.paths import get_config_file_path

        config_path = get_config_file_path()

    if config_path.exists():
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        settings = Settings.model_validate(raw)
        # 如果缺少配置文件相关字段，从扁平设置创建
        if "profiles" not in raw or "active_profile" not in raw:
            profile_name, profile = _profile_from_flat_settings(settings)
            merged_profiles = settings.merged_profiles()
            merged_profiles[profile_name] = profile
            settings = settings.model_copy(
                update={
                    "active_profile": profile_name,
                    "profiles": merged_profiles,
                }
            )
        # 应用环境变量覆盖并激活配置文件
        return _apply_env_overrides(settings.materialize_active_profile())

    # 返回默认值并应用环境变量覆盖
    return _apply_env_overrides(Settings().materialize_active_profile())


def save_settings(settings: Settings, config_path: Path | None = None) -> None:
    """将设置持久化到配置文件
    
    在保存前会同步配置文件字段并激活配置文件。
    保存时会剥离与内置默认完全相同的profiles，避免冗余配置。
    
    Args:
        settings: 要保存的 Settings 实例
        config_path: 写入路径。如果为 None，使用默认位置
    """
    if config_path is None:
        from illusion.config.paths import get_config_file_path

        config_path = get_config_file_path()

    # 同步并激活配置文件
    settings = settings.sync_active_profile_from_flat_fields().materialize_active_profile()
    
    # 剥离与内置默认完全相同的profiles，只保留用户实际配置过的
    builtin_defaults = default_provider_profiles()
    user_profiles: dict[str, ProviderProfile] = {}
    for name, profile in settings.profiles.items():
        builtin = builtin_defaults.get(name)
        # 如果该profile不是内置默认，或者用户修改过它，则保留
        if builtin is None or profile != builtin:
            user_profiles[name] = profile
    
    settings = settings.model_copy(update={"profiles": user_profiles})
    
    config_path.parent.mkdir(parents=True, exist_ok=True)  # 确保目录存在
    # 写入 JSON 格式的配置
    config_path.write_text(
        settings.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
