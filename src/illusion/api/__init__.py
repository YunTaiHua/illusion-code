"""API exports."""

from illusion.api.client import AnthropicApiClient
from illusion.api.copilot_client import CopilotClient
from illusion.api.errors import IllusionCodeApiError
from illusion.api.openai_client import OpenAICompatibleClient
from illusion.api.provider import ProviderInfo, auth_status, detect_provider
from illusion.api.usage import UsageSnapshot

__all__ = [
    "AnthropicApiClient",
    "CopilotClient",
    "OpenAICompatibleClient",
    "IllusionCodeApiError",
    "ProviderInfo",
    "UsageSnapshot",
    "auth_status",
    "detect_provider",
]
