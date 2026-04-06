"""Unified authentication management for IllusionCode."""

from illusion.auth.flows import ApiKeyFlow, BrowserFlow, DeviceCodeFlow
from illusion.auth.manager import AuthManager
from illusion.auth.storage import (
    clear_provider_credentials,
    decrypt,
    encrypt,
    load_credential,
    store_credential,
)

__all__ = [
    "AuthManager",
    "ApiKeyFlow",
    "BrowserFlow",
    "DeviceCodeFlow",
    "store_credential",
    "load_credential",
    "clear_provider_credentials",
    "encrypt",
    "decrypt",
]
