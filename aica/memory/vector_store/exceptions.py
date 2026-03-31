from __future__ import annotations


class VectorStoreError(Exception):
    """Base class for all vector store errors."""


class VectorStoreConnectionError(VectorStoreError):
    """Raised on network failures or service unavailability."""


class VectorStoreAuthError(VectorStoreError):
    """Raised on authentication failures — never retried."""


class VectorStoreQueryError(VectorStoreError):
    """Raised on query syntax or runtime execution errors."""


class VectorStoreTimeoutError(VectorStoreError):
    """Raised when a request exceeds the configured timeout."""


class VectorStoreRateLimitError(VectorStoreError):
    """Raised on rate limit errors (429 Too Many Requests)."""
