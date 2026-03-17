from __future__ import annotations


class LLMError(Exception):
    """Base class for all LLM provider errors."""


class LLMConnectionError(LLMError):
    """Raised on network failures or non-auth HTTP errors (5xx, connection refused)."""


class LLMAuthError(LLMError):
    """Raised on 401/403 authentication failures.

    This error is *never* retried — a wrong key will not fix itself.
    """


class LLMRateLimitError(LLMError):
    """Raised on 429 Too Many Requests."""


class LLMTimeoutError(LLMError):
    """Raised when a request exceeds the configured timeout."""
