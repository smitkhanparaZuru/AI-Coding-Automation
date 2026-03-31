from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aica.config.settings import get_settings
from aica.core.logging.logger import get_logger
from aica.memory.vector_store.exceptions import (
    VectorStoreAuthError,
    VectorStoreConnectionError,
    VectorStoreQueryError,
)

if TYPE_CHECKING:
    from qdrant_client import QdrantClient as _QdrantClient
    from qdrant_client.models import Distance, PointStruct, ScoredPoint, VectorParams

log = get_logger("vector_store.qdrant")


class QdrantClient:
    """Thin wrapper around the qdrant-client Python library.

    All four connection parameters fall back to ``get_settings()`` when not
    supplied, so the client can be constructed with zero arguments inside the
    AICA pipeline:

        client = QdrantClient()   # reads AICA_QDRANT_* env vars

    Or overridden explicitly for tests / alternative targets:

        client = QdrantClient(url="http://myhost:6333", api_key="secret")
    """

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        collection_name: str | None = None,
        vector_dimension: int | None = None,
        batch_size: int | None = None,
    ) -> None:
        cfg = get_settings()
        self._url: str = url or cfg.qdrant_url
        self._api_key: str | None = (
            api_key
            if api_key is not None
            else (cfg.qdrant_api_key.get_secret_value() if cfg.qdrant_api_key else None)
        )
        self._collection_name: str = collection_name or cfg.qdrant_collection_name
        self._vector_dimension: int | None = vector_dimension or cfg.qdrant_vector_dimension
        self._batch_size: int = batch_size or cfg.qdrant_batch_size
        self._client: _QdrantClient | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Create the client and verify connectivity.

        Raises:
            VectorStoreAuthError: Invalid API key.
            VectorStoreConnectionError: Qdrant is unreachable.
        """
        try:
            from qdrant_client import QdrantClient as _QdrantClient  # noqa: PLC0415
        except ModuleNotFoundError as exc:
            raise VectorStoreConnectionError(
                "qdrant-client package is not installed. Run: pip install qdrant-client>=1.7"
            ) from exc

        try:
            client = _QdrantClient(url=self._url, api_key=self._api_key, timeout=60)
            # Verify connectivity by listing collections
            client.get_collections()
            self._client = client
            log.info(
                "qdrant.connected",
                url=self._url,
                collection=self._collection_name,
            )
        except Exception as exc:  # noqa: BLE001
            # Qdrant client raises various exceptions; map to our hierarchy
            error_msg = str(exc).lower()
            if "auth" in error_msg or "unauthorized" in error_msg or "forbidden" in error_msg:
                raise VectorStoreAuthError(str(exc)) from exc
            raise VectorStoreConnectionError(str(exc)) from exc

    def close(self) -> None:
        """Close the client. Safe to call when not connected."""
        if self._client is not None:
            self._client.close()
            self._client = None
            log.info("qdrant.disconnected", url=self._url)

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> QdrantClient:
        self.connect()
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Collection operations
    # ------------------------------------------------------------------

    def collection_exists(self, collection_name: str | None = None) -> bool:
        """Check if a collection exists.

        Args:
            collection_name: Collection name (defaults to configured collection).

        Returns:
            True if the collection exists, False otherwise.

        Raises:
            VectorStoreConnectionError: Client is not connected.
        """
        if self._client is None:
            raise VectorStoreConnectionError(
                "Not connected — call connect() or use as context manager."
            )

        name = collection_name or self._collection_name
        try:
            return self._client.collection_exists(collection_name=name)
        except Exception as exc:  # noqa: BLE001
            log.error("qdrant.check_failed", collection=name, error=str(exc))
            raise VectorStoreConnectionError(str(exc)) from exc

    def create_collection(
        self,
        collection_name: str | None = None,
        vector_dimension: int | None = None,
        distance: str = "Cosine",
    ) -> None:
        """Create a new collection with specified vector dimension.

        Args:
            collection_name: Collection name (defaults to configured collection).
            vector_dimension: Vector dimension (defaults to configured dimension).
            distance: Distance metric (Cosine, Euclid, Dot). Default: Cosine.

        Raises:
            VectorStoreConnectionError: Client is not connected.
            VectorStoreQueryError: Collection creation failed.
        """
        if self._client is None:
            raise VectorStoreConnectionError(
                "Not connected — call connect() or use as context manager."
            )

        from qdrant_client.models import Distance as _Distance, VectorParams  # noqa: PLC0415

        name = collection_name or self._collection_name
        dimension = vector_dimension or self._vector_dimension

        if dimension is None:
            raise ValueError(
                "vector_dimension must be specified (via argument or config AICA_QDRANT_VECTOR_DIMENSION)"
            )

        # Map string distance to enum
        distance_map = {
            "Cosine": _Distance.COSINE,
            "Euclid": _Distance.EUCLID,
            "Dot": _Distance.DOT,
        }
        distance_metric = distance_map.get(distance, _Distance.COSINE)

        try:
            self._client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=dimension, distance=distance_metric),
            )
            log.info(
                "qdrant.collection_created",
                collection=name,
                dimension=dimension,
                distance=distance,
            )
        except Exception as exc:  # noqa: BLE001
            log.error("qdrant.create_failed", collection=name, error=str(exc))
            raise VectorStoreQueryError(str(exc)) from exc

    def delete_collection(self, collection_name: str | None = None) -> None:
        """Delete a collection.

        Args:
            collection_name: Collection name (defaults to configured collection).

        Raises:
            VectorStoreConnectionError: Client is not connected.
            VectorStoreQueryError: Collection deletion failed.
        """
        if self._client is None:
            raise VectorStoreConnectionError(
                "Not connected — call connect() or use as context manager."
            )

        name = collection_name or self._collection_name

        try:
            self._client.delete_collection(collection_name=name)
            log.info("qdrant.collection_deleted", collection=name)
        except Exception as exc:  # noqa: BLE001
            log.error("qdrant.delete_failed", collection=name, error=str(exc))
            raise VectorStoreQueryError(str(exc)) from exc

    # ------------------------------------------------------------------
    # Vector operations
    # ------------------------------------------------------------------

    def upsert_vectors(
        self,
        vectors: list[dict[str, Any]],
        collection_name: str | None = None,
    ) -> int:
        """Upsert vectors into the collection in batches.

        Args:
            vectors: List of dicts with keys: 'id' (str), 'vector' (list[float]), 'payload' (dict).
            collection_name: Collection name (defaults to configured collection).

        Returns:
            Number of vectors upserted.

        Raises:
            VectorStoreConnectionError: Client is not connected.
            VectorStoreQueryError: Upsert operation failed.
        """
        if self._client is None:
            raise VectorStoreConnectionError(
                "Not connected — call connect() or use as context manager."
            )

        from qdrant_client.models import PointStruct  # noqa: PLC0415

        name = collection_name or self._collection_name
        total = len(vectors)

        if total == 0:
            log.debug("qdrant.upsert_empty", collection=name)
            return 0

        try:
            # Process in batches
            for i in range(0, total, self._batch_size):
                batch = vectors[i : i + self._batch_size]
                points = [
                    PointStruct(
                        id=v["id"],
                        vector=v["vector"],
                        payload=v.get("payload", {}),
                    )
                    for v in batch
                ]
                self._client.upsert(collection_name=name, points=points)
                log.debug(
                    "qdrant.batch_upserted",
                    collection=name,
                    batch=f"{i + 1}-{i + len(batch)}",
                    total=total,
                )

            log.info("qdrant.upsert_complete", collection=name, count=total)
            return total
        except Exception as exc:  # noqa: BLE001
            log.error("qdrant.upsert_failed", collection=name, error=str(exc))
            raise VectorStoreQueryError(str(exc)) from exc

    def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        filter_dict: dict[str, Any] | None = None,
        collection_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar vectors.

        Args:
            query_vector: Query embedding vector.
            top_k: Number of results to return.
            filter_dict: Optional metadata filter (Qdrant filter syntax).
            collection_name: Collection name (defaults to configured collection).

        Returns:
            List of dicts with keys: 'id', 'score', 'payload'.

        Raises:
            VectorStoreConnectionError: Client is not connected.
            VectorStoreQueryError: Search operation failed.
        """
        if self._client is None:
            raise VectorStoreConnectionError(
                "Not connected — call connect() or use as context manager."
            )

        name = collection_name or self._collection_name

        try:
            results = self._client.search(
                collection_name=name,
                query_vector=query_vector,
                limit=top_k,
                query_filter=filter_dict,
            )
            log.debug("qdrant.search_ok", collection=name, top_k=top_k, results=len(results))
            return [
                {"id": result.id, "score": result.score, "payload": result.payload}
                for result in results
            ]
        except Exception as exc:  # noqa: BLE001
            log.error("qdrant.search_failed", collection=name, error=str(exc))
            raise VectorStoreQueryError(str(exc)) from exc

    def delete_by_filter(
        self,
        filter_dict: dict[str, Any],
        collection_name: str | None = None,
    ) -> None:
        """Delete vectors matching a filter.

        Args:
            filter_dict: Metadata filter (Qdrant filter syntax).
            collection_name: Collection name (defaults to configured collection).

        Raises:
            VectorStoreConnectionError: Client is not connected.
            VectorStoreQueryError: Delete operation failed.
        """
        if self._client is None:
            raise VectorStoreConnectionError(
                "Not connected — call connect() or use as context manager."
            )

        name = collection_name or self._collection_name

        try:
            self._client.delete(collection_name=name, points_selector=filter_dict)
            log.info("qdrant.delete_by_filter", collection=name, filter=str(filter_dict))
        except Exception as exc:  # noqa: BLE001
            log.error("qdrant.delete_failed", collection=name, error=str(exc))
            raise VectorStoreQueryError(str(exc)) from exc

    def get_collection_info(self, collection_name: str | None = None) -> dict[str, Any]:
        """Get information about a collection.

        Args:
            collection_name: Collection name (defaults to configured collection).

        Returns:
            Dict with keys: 'vectors_count', 'config', etc.

        Raises:
            VectorStoreConnectionError: Client is not connected.
            VectorStoreQueryError: Query failed.
        """
        if self._client is None:
            raise VectorStoreConnectionError(
                "Not connected — call connect() or use as context manager."
            )

        name = collection_name or self._collection_name

        try:
            info = self._client.get_collection(collection_name=name)
            return {
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "config": {
                    "params": {
                        "vectors": {
                            "size": info.config.params.vectors.size,
                            "distance": info.config.params.vectors.distance.name,
                        }
                    }
                },
            }
        except Exception as exc:  # noqa: BLE001
            log.error("qdrant.get_info_failed", collection=name, error=str(exc))
            raise VectorStoreQueryError(str(exc)) from exc
