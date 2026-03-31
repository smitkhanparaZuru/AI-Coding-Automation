from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aica.memory.vector_store.embedding_provider import BaseEmbeddingProvider
from aica.memory.vector_store.factory import EmbeddingProvider


# ---------------------------------------------------------------------------
# Test provider for registration
# ---------------------------------------------------------------------------


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """Mock provider for testing registration."""

    def __init__(self, model: str, **kwargs: object) -> None:
        self.model = model
        self._dimension = 128

    def generate_embedding(self, text: str) -> list[float]:
        return [0.1] * 128

    def generate_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 128 for _ in texts]

    async def async_generate_embedding(self, text: str) -> list[float]:
        return [0.1] * 128

    async def async_generate_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 128 for _ in texts]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_settings() -> MagicMock:
    settings = MagicMock()
    settings.embedding_provider = "ollama"
    settings.embedding_model = "nomic-embed-text"
    settings.embedding_batch_size = 32
    settings.embedding_timeout = 60
    settings.embedding_max_retries = 3
    settings.embedding_retry_min_wait = 1.0
    settings.embedding_retry_max_wait = 10.0
    settings.embedding_ollama_base_url = "http://localhost:11434"
    settings.embedding_openrouter_api_key = None
    settings.embedding_openrouter_base_url = "https://openrouter.ai/api/v1"
    return settings


# ---------------------------------------------------------------------------
# EmbeddingProvider
# ---------------------------------------------------------------------------


class TestEmbeddingProvider:
    def test_init_ollama_default(self, mock_settings: MagicMock) -> None:
        with patch("aica.memory.vector_store.factory.get_settings", return_value=mock_settings):
            provider = EmbeddingProvider()

        assert provider.backend.model == "nomic-embed-text"

    def test_init_openrouter(self, mock_settings: MagicMock) -> None:
        mock_settings.embedding_provider = "openrouter"
        mock_settings.embedding_model = "openai/text-embedding-3-small"
        mock_api_key = MagicMock()
        mock_api_key.get_secret_value.return_value = "test-key"
        mock_settings.embedding_openrouter_api_key = mock_api_key

        with patch("aica.memory.vector_store.factory.get_settings", return_value=mock_settings):
            provider = EmbeddingProvider()

        assert provider.backend.model == "openai/text-embedding-3-small"

    def test_init_unknown_provider(self, mock_settings: MagicMock) -> None:
        mock_settings.embedding_provider = "unknown"

        with patch("aica.memory.vector_store.factory.get_settings", return_value=mock_settings):
            with pytest.raises(ValueError, match="Unknown embedding provider"):
                EmbeddingProvider()

    def test_init_override_provider(self, mock_settings: MagicMock) -> None:
        with patch("aica.memory.vector_store.factory.get_settings", return_value=mock_settings):
            provider = EmbeddingProvider(provider="ollama", model="custom-model")

        assert provider.backend.model == "custom-model"

    def test_register_custom_provider(self, mock_settings: MagicMock) -> None:
        # Clear any existing registration first
        from aica.memory.vector_store.factory import _REGISTRY
        
        EmbeddingProvider.register("mock", MockEmbeddingProvider)
        
        # Verify registration
        assert "mock" in _REGISTRY

        mock_settings.embedding_provider = "mock"
        mock_settings.embedding_model = "mock-model"

        with patch("aica.memory.vector_store.factory.get_settings", return_value=mock_settings):
            provider = EmbeddingProvider()

        assert provider.backend.model == "mock-model"
        assert isinstance(provider.backend, MockEmbeddingProvider)

    def test_backend_property(self, mock_settings: MagicMock) -> None:
        with patch("aica.memory.vector_store.factory.get_settings", return_value=mock_settings):
            provider = EmbeddingProvider()

        assert provider.backend is not None
        assert hasattr(provider.backend, "model")

    def test_dimension_property(self, mock_settings: MagicMock) -> None:
        with patch("aica.memory.vector_store.factory.get_settings", return_value=mock_settings):
            provider = EmbeddingProvider()

        # Dimension is None until first embedding is generated
        assert provider.dimension is None

    def test_generate_embedding_delegates(self, mock_settings: MagicMock) -> None:
        with patch("aica.memory.vector_store.factory.get_settings", return_value=mock_settings):
            provider = EmbeddingProvider()
            provider._backend = MagicMock()
            provider._backend.generate_embedding.return_value = [0.1, 0.2, 0.3]

            result = provider.generate_embedding("test")

        assert result == [0.1, 0.2, 0.3]
        provider._backend.generate_embedding.assert_called_once_with("test")

    def test_generate_batch_delegates(self, mock_settings: MagicMock) -> None:
        with patch("aica.memory.vector_store.factory.get_settings", return_value=mock_settings):
            provider = EmbeddingProvider()
            provider._backend = MagicMock()
            provider._backend.generate_batch.return_value = [[0.1, 0.2], [0.3, 0.4]]

            result = provider.generate_batch(["test1", "test2"])

        assert result == [[0.1, 0.2], [0.3, 0.4]]
        provider._backend.generate_batch.assert_called_once_with(["test1", "test2"])

    @pytest.mark.asyncio
    async def test_async_generate_embedding_delegates(self, mock_settings: MagicMock) -> None:
        with patch("aica.memory.vector_store.factory.get_settings", return_value=mock_settings):
            provider = EmbeddingProvider()
            provider._backend = AsyncMock()
            provider._backend.async_generate_embedding.return_value = [0.1, 0.2, 0.3]

            result = await provider.async_generate_embedding("test")

        assert result == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_async_generate_batch_delegates(self, mock_settings: MagicMock) -> None:
        with patch("aica.memory.vector_store.factory.get_settings", return_value=mock_settings):
            provider = EmbeddingProvider()
            provider._backend = AsyncMock()
            provider._backend.async_generate_batch.return_value = [[0.1, 0.2], [0.3, 0.4]]

            result = await provider.async_generate_batch(["test1", "test2"])

        assert result == [[0.1, 0.2], [0.3, 0.4]]
