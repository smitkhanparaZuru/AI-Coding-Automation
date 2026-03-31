from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from aica.memory.vector_store.embedding_provider import (
    OllamaEmbeddingProvider,
    OpenRouterEmbeddingProvider,
)
from aica.memory.vector_store.exceptions import (
    VectorStoreAuthError,
    VectorStoreConnectionError,
    VectorStoreRateLimitError,
    VectorStoreTimeoutError,
)


# ---------------------------------------------------------------------------
# OllamaEmbeddingProvider
# ---------------------------------------------------------------------------


class TestOllamaEmbeddingProvider:
    def test_init_empty_model(self) -> None:
        with pytest.raises(ValueError, match="model name must not be empty"):
            OllamaEmbeddingProvider(model="")

    def test_generate_embedding_success(self) -> None:
        provider = OllamaEmbeddingProvider(model="nomic-embed-text")

        mock_response = MagicMock()
        mock_response.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = provider.generate_embedding("test text")

        assert result == [0.1, 0.2, 0.3]
        assert provider.dimension == 3

    def test_generate_embedding_alternative_format(self) -> None:
        provider = OllamaEmbeddingProvider(model="nomic-embed-text")

        mock_response = MagicMock()
        mock_response.json.return_value = {"embeddings": [[0.1, 0.2, 0.3]]}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = provider.generate_embedding("test text")

        assert result == [0.1, 0.2, 0.3]

    def test_generate_embedding_timeout(self) -> None:
        provider = OllamaEmbeddingProvider(model="nomic-embed-text", max_retries=1)

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = httpx.TimeoutException("Timeout")
            mock_client_class.return_value = mock_client

            with pytest.raises(VectorStoreTimeoutError):
                provider.generate_embedding("test text")

    def test_generate_embedding_connect_error(self) -> None:
        provider = OllamaEmbeddingProvider(model="nomic-embed-text", max_retries=1)

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = httpx.ConnectError("Connection refused")
            mock_client_class.return_value = mock_client

            with pytest.raises(VectorStoreConnectionError):
                provider.generate_embedding("test text")

    def test_generate_batch_success(self) -> None:
        provider = OllamaEmbeddingProvider(model="nomic-embed-text", batch_size=2)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "embeddings": [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = provider.generate_batch(["text1", "text2", "text3"])

        # Should be called twice due to batch size of 2
        assert mock_client.post.call_count == 2
        assert len(result) == 6  # 2 batches of 3 embeddings each

    def test_generate_batch_empty(self) -> None:
        provider = OllamaEmbeddingProvider(model="nomic-embed-text")
        result = provider.generate_batch([])
        assert result == []

    @pytest.mark.asyncio
    async def test_async_generate_embedding_success(self) -> None:
        provider = OllamaEmbeddingProvider(model="nomic-embed-text")

        mock_response = MagicMock()
        mock_response.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await provider.async_generate_embedding("test text")

        assert result == [0.1, 0.2, 0.3]


# ---------------------------------------------------------------------------
# OpenRouterEmbeddingProvider
# ---------------------------------------------------------------------------


class TestOpenRouterEmbeddingProvider:
    def test_init_empty_model(self) -> None:
        with pytest.raises(ValueError, match="model name must not be empty"):
            OpenRouterEmbeddingProvider(model="", api_key="test-key")

    def test_init_empty_api_key(self) -> None:
        with pytest.raises(VectorStoreAuthError, match="API key must not be empty"):
            OpenRouterEmbeddingProvider(model="openai/text-embedding-3-small", api_key="")

    def test_generate_embedding_success(self) -> None:
        provider = OpenRouterEmbeddingProvider(
            model="openai/text-embedding-3-small", api_key="test-key"
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {"data": [{"embedding": [0.1, 0.2, 0.3]}]}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = provider.generate_embedding("test text")

        assert result == [0.1, 0.2, 0.3]
        assert provider.dimension == 3

    def test_generate_embedding_auth_error(self) -> None:
        provider = OpenRouterEmbeddingProvider(
            model="openai/text-embedding-3-small", api_key="test-key", max_retries=1
        )

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = httpx.HTTPStatusError(
                "Unauthorized", request=MagicMock(), response=mock_response
            )
            mock_client_class.return_value = mock_client

            with pytest.raises(VectorStoreAuthError):
                provider.generate_embedding("test text")

    def test_generate_embedding_rate_limit(self) -> None:
        provider = OpenRouterEmbeddingProvider(
            model="openai/text-embedding-3-small", api_key="test-key", max_retries=1
        )

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = httpx.HTTPStatusError(
                "Rate limit", request=MagicMock(), response=mock_response
            )
            mock_client_class.return_value = mock_client

            with pytest.raises(VectorStoreRateLimitError):
                provider.generate_embedding("test text")

    def test_generate_batch_success(self) -> None:
        provider = OpenRouterEmbeddingProvider(
            model="openai/text-embedding-3-small", api_key="test-key", batch_size=2
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = provider.generate_batch(["text1", "text2", "text3"])

        # Should be called twice due to batch size of 2
        assert mock_client.post.call_count == 2
        assert len(result) == 4  # 2 batches of 2 embeddings each

    def test_generate_batch_empty(self) -> None:
        provider = OpenRouterEmbeddingProvider(
            model="openai/text-embedding-3-small", api_key="test-key"
        )
        result = provider.generate_batch([])
        assert result == []

    @pytest.mark.asyncio
    async def test_async_generate_embedding_success(self) -> None:
        provider = OpenRouterEmbeddingProvider(
            model="openai/text-embedding-3-small", api_key="test-key"
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {"data": [{"embedding": [0.1, 0.2, 0.3]}]}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await provider.async_generate_embedding("test text")

        assert result == [0.1, 0.2, 0.3]
