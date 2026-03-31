from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from aica.memory.vector_store.exceptions import (
    VectorStoreAuthError,
    VectorStoreConnectionError,
    VectorStoreQueryError,
)
from aica.memory.vector_store.qdrant_client import QdrantClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_qdrant_mock() -> MagicMock:
    """Build a mock qdrant_client.QdrantClient."""
    mock_client = MagicMock()
    mock_client.get_collections.return_value = MagicMock()
    mock_client.collection_exists.return_value = True
    mock_client.create_collection.return_value = None
    mock_client.delete_collection.return_value = None
    mock_client.upsert.return_value = None
    mock_client.search.return_value = []
    mock_client.delete.return_value = None
    mock_client.close.return_value = None
    
    # Mock get_collection
    collection_info = MagicMock()
    collection_info.vectors_count = 100
    collection_info.points_count = 100
    collection_info.config.params.vectors.size = 384
    collection_info.config.params.vectors.distance.name = "Cosine"
    mock_client.get_collection.return_value = collection_info
    
    return mock_client


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def qdrant_mock() -> MagicMock:
    return _make_qdrant_mock()


@pytest.fixture()
def connected_client(qdrant_mock: MagicMock) -> QdrantClient:
    """A QdrantClient with a pre-connected mock client."""
    client = QdrantClient(
        url="http://localhost:6333",
        collection_name="test-collection",
        vector_dimension=384,
    )
    client._client = qdrant_mock
    return client


# ---------------------------------------------------------------------------
# connect()
# ---------------------------------------------------------------------------


class TestConnect:
    def test_connect_success(self) -> None:
        qdrant_mock = _make_qdrant_mock()

        with patch("qdrant_client.QdrantClient", return_value=qdrant_mock):
            client = QdrantClient(url="http://localhost:6333")
            client.connect()

        qdrant_mock.get_collections.assert_called_once()

    def test_connect_auth_error(self) -> None:
        qdrant_mock = _make_qdrant_mock()
        qdrant_mock.get_collections.side_effect = Exception("Unauthorized")

        with patch("qdrant_client.QdrantClient", return_value=qdrant_mock):
            client = QdrantClient(url="http://localhost:6333")

            with pytest.raises(VectorStoreAuthError):
                client.connect()

    def test_connect_connection_error(self) -> None:
        qdrant_mock = _make_qdrant_mock()
        qdrant_mock.get_collections.side_effect = Exception("Connection refused")

        with patch("qdrant_client.QdrantClient", return_value=qdrant_mock):
            client = QdrantClient(url="http://localhost:6333")

            with pytest.raises(VectorStoreConnectionError):
                client.connect()

    def test_connect_module_not_found(self) -> None:
        client = QdrantClient(url="http://localhost:6333")

        with patch.dict("sys.modules", {"qdrant_client": None}):
            with pytest.raises(VectorStoreConnectionError, match="not installed"):
                client.connect()


# ---------------------------------------------------------------------------
# close()
# ---------------------------------------------------------------------------


class TestClose:
    def test_close_when_connected(self, connected_client: QdrantClient) -> None:
        connected_client.close()
        assert connected_client._client is None

    def test_close_when_not_connected(self) -> None:
        client = QdrantClient(url="http://localhost:6333")
        client.close()  # Should not raise
        assert client._client is None


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


class TestContextManager:
    def test_context_manager(self, qdrant_mock: MagicMock) -> None:
        with patch("qdrant_client.QdrantClient", return_value=qdrant_mock):
            client = QdrantClient(url="http://localhost:6333")

            with client:
                assert client._client is not None

            assert client._client is None


# ---------------------------------------------------------------------------
# collection_exists()
# ---------------------------------------------------------------------------


class TestCollectionExists:
    def test_collection_exists_true(self, connected_client: QdrantClient) -> None:
        connected_client._client.collection_exists.return_value = True
        assert connected_client.collection_exists() is True

    def test_collection_exists_false(self, connected_client: QdrantClient) -> None:
        connected_client._client.collection_exists.return_value = False
        assert connected_client.collection_exists() is False

    def test_collection_exists_not_connected(self) -> None:
        client = QdrantClient(url="http://localhost:6333")
        with pytest.raises(VectorStoreConnectionError, match="Not connected"):
            client.collection_exists()

    def test_collection_exists_error(self, connected_client: QdrantClient) -> None:
        connected_client._client.collection_exists.side_effect = Exception("Query failed")
        with pytest.raises(VectorStoreConnectionError):
            connected_client.collection_exists()


# ---------------------------------------------------------------------------
# create_collection()
# ---------------------------------------------------------------------------


class TestCreateCollection:
    def test_create_collection_success(self, connected_client: QdrantClient) -> None:
        with patch("qdrant_client.models.Distance"), patch("qdrant_client.models.VectorParams"):
            connected_client.create_collection(vector_dimension=384)
            connected_client._client.create_collection.assert_called_once()

    def test_create_collection_no_dimension(self, connected_client: QdrantClient) -> None:
        connected_client._vector_dimension = None
        with patch("qdrant_client.models.Distance"), patch("qdrant_client.models.VectorParams"):
            with pytest.raises(ValueError, match="vector_dimension must be specified"):
                connected_client.create_collection()

    def test_create_collection_not_connected(self) -> None:
        client = QdrantClient(url="http://localhost:6333", vector_dimension=384)
        with pytest.raises(VectorStoreConnectionError, match="Not connected"):
            client.create_collection()

    def test_create_collection_error(self, connected_client: QdrantClient) -> None:
        connected_client._client.create_collection.side_effect = Exception("Creation failed")
        with patch("qdrant_client.models.Distance"), patch("qdrant_client.models.VectorParams"):
            with pytest.raises(VectorStoreQueryError):
                connected_client.create_collection(vector_dimension=384)


# ---------------------------------------------------------------------------
# delete_collection()
# ---------------------------------------------------------------------------


class TestDeleteCollection:
    def test_delete_collection_success(self, connected_client: QdrantClient) -> None:
        connected_client.delete_collection()
        connected_client._client.delete_collection.assert_called_once()

    def test_delete_collection_not_connected(self) -> None:
        client = QdrantClient(url="http://localhost:6333")
        with pytest.raises(VectorStoreConnectionError, match="Not connected"):
            client.delete_collection()


# ---------------------------------------------------------------------------
# upsert_vectors()
# ---------------------------------------------------------------------------


class TestUpsertVectors:
    def test_upsert_vectors_success(self, connected_client: QdrantClient) -> None:
        vectors = [
            {"id": "1", "vector": [0.1, 0.2, 0.3], "payload": {"text": "test1"}},
            {"id": "2", "vector": [0.4, 0.5, 0.6], "payload": {"text": "test2"}},
        ]
        with patch("qdrant_client.models.PointStruct"):
            result = connected_client.upsert_vectors(vectors)
            assert result == 2
            connected_client._client.upsert.assert_called()

    def test_upsert_vectors_empty(self, connected_client: QdrantClient) -> None:
        with patch("qdrant_client.models.PointStruct"):
            result = connected_client.upsert_vectors([])
            assert result == 0
            connected_client._client.upsert.assert_not_called()

    def test_upsert_vectors_batching(self, connected_client: QdrantClient) -> None:
        # Create more vectors than batch size
        vectors = [
            {"id": str(i), "vector": [0.1, 0.2, 0.3], "payload": {"text": f"test{i}"}}
            for i in range(550)
        ]
        connected_client._batch_size = 500
        with patch("qdrant_client.models.PointStruct"):
            result = connected_client.upsert_vectors(vectors)
            assert result == 550
            # Should be called twice (500 + 50)
            result = connected_client.upsert_vectors(vectors)
        assert result == 550
        # Should be called twice (500 + 50)
        assert connected_client._client.upsert.call_count == 2

    def test_upsert_vectors_not_connected(self) -> None:
        client = QdrantClient(url="http://localhost:6333")
        with pytest.raises(VectorStoreConnectionError, match="Not connected"):
            client.upsert_vectors([{"id": "1", "vector": [0.1, 0.2], "payload": {}}])


# ---------------------------------------------------------------------------
# search()
# ---------------------------------------------------------------------------


class TestSearch:
    def test_search_success(self, connected_client: QdrantClient) -> None:
        mock_result = MagicMock()
        mock_result.id = "1"
        mock_result.score = 0.95
        mock_result.payload = {"text": "test"}
        connected_client._client.search.return_value = [mock_result]

        results = connected_client.search(query_vector=[0.1, 0.2, 0.3], top_k=5)

        assert len(results) == 1
        assert results[0]["id"] == "1"
        assert results[0]["score"] == 0.95
        assert results[0]["payload"]["text"] == "test"

    def test_search_with_filter(self, connected_client: QdrantClient) -> None:
        filter_dict = {"must": [{"key": "text", "match": {"value": "test"}}]}
        connected_client.search(
            query_vector=[0.1, 0.2, 0.3], top_k=10, filter_dict=filter_dict
        )
        connected_client._client.search.assert_called_once()

    def test_search_not_connected(self) -> None:
        client = QdrantClient(url="http://localhost:6333")
        with pytest.raises(VectorStoreConnectionError, match="Not connected"):
            client.search(query_vector=[0.1, 0.2, 0.3])


# ---------------------------------------------------------------------------
# delete_by_filter()
# ---------------------------------------------------------------------------


class TestDeleteByFilter:
    def test_delete_by_filter_success(self, connected_client: QdrantClient) -> None:
        filter_dict = {"must": [{"key": "text", "match": {"value": "test"}}]}
        connected_client.delete_by_filter(filter_dict)
        connected_client._client.delete.assert_called_once()

    def test_delete_by_filter_not_connected(self) -> None:
        client = QdrantClient(url="http://localhost:6333")
        with pytest.raises(VectorStoreConnectionError, match="Not connected"):
            client.delete_by_filter({"must": []})


# ---------------------------------------------------------------------------
# get_collection_info()
# ---------------------------------------------------------------------------


class TestGetCollectionInfo:
    def test_get_collection_info_success(self, connected_client: QdrantClient) -> None:
        info = connected_client.get_collection_info()
        assert info["vectors_count"] == 100
        assert info["points_count"] == 100
        assert info["config"]["params"]["vectors"]["size"] == 384
        assert info["config"]["params"]["vectors"]["distance"] == "Cosine"

    def test_get_collection_info_not_connected(self) -> None:
        client = QdrantClient(url="http://localhost:6333")
        with pytest.raises(VectorStoreConnectionError, match="Not connected"):
            client.get_collection_info()
