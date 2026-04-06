"""API error types for IllusionCode."""

from __future__ import annotations


class IllusionCodeApiError(RuntimeError):
    """Base class for upstream API failures."""


class AuthenticationFailure(IllusionCodeApiError):
    """Raised when the upstream service rejects the provided credentials."""


class RateLimitFailure(IllusionCodeApiError):
    """Raised when the upstream service rejects the request due to rate limits."""


class RequestFailure(IllusionCodeApiError):
    """Raised for generic request or transport failures."""
