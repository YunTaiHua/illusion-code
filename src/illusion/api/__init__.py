"""
API 模块
========

本模块提供 IllusionCode 与各种 LLM 提供商的 API 集成。

主要组件：
    - AnthropicApiClient: Anthropic API 客户端
    - OpenAICompatibleClient: OpenAI 兼容 API 客户端
    - CopilotClient: GitHub Copilot 客户端
    - CodexApiClient: OpenAI Codex 客户端
    - IllusionCodeApiError: API 异常基类
    - ProviderInfo: 提供商元数据
    - UsageSnapshot: 使用量追踪

使用示例：
    >>> from illusion.api import AnthropicApiClient
    >>> client = AnthropicApiClient(api_key="sk-...")
"""

from illusion.api.client import AnthropicApiClient
from illusion.api.codex_client import CodexApiClient
from illusion.api.copilot_client import CopilotClient
from illusion.api.errors import IllusionCodeApiError
from illusion.api.openai_client import OpenAICompatibleClient
from illusion.api.provider import ProviderInfo, auth_status, detect_provider
from illusion.api.usage import UsageSnapshot

__all__ = [
    "AnthropicApiClient",
    "CodexApiClient",
    "CopilotClient",
    "OpenAICompatibleClient",
    "IllusionCodeApiError",
    "ProviderInfo",
    "UsageSnapshot",
    "auth_status",
    "detect_provider",
]
