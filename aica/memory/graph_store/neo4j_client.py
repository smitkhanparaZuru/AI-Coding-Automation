from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from aica.config.settings import get_settings
from aica.core.logging.logger import get_logger

if TYPE_CHECKING:
    import neo4j as _neo4j

log = get_logger("graph.neo4j")


# ---------------------------------------------------------------------------
# Error hierarchy
# ---------------------------------------------------------------------------


class GraphError(Exception):
    """Base class for all graph database errors."""


class GraphConnectionError(GraphError):
    """Raised on network failures or service unavailability."""


class GraphAuthError(GraphError):
    """Raised on authentication failures — never retried."""


class GraphQueryError(GraphError):
    """Raised on Cypher syntax or runtime execution errors."""


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class Neo4jClient:
    """Thin wrapper around the neo4j Python driver.

    All four connection parameters fall back to ``get_settings()`` when not
    supplied, so the client can be constructed with zero arguments inside the
    AICA pipeline:

        client = Neo4jClient()   # reads AICA_NEO4J_* env vars

    Or overridden explicitly for tests / alternative targets:

        client = Neo4jClient(uri="bolt://myhost:7687", password="secret")
    """

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str | None = None,
    ) -> None:
        cfg = get_settings()
        self._uri: str = uri or cfg.neo4j_uri
        self._user: str = user or cfg.neo4j_user
        self._password: str = (
            password
            if password is not None
            else cfg.neo4j_password.get_secret_value()
        )
        self._database: str = database or cfg.neo4j_database
        self._driver: _neo4j.Driver | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Create the driver and verify connectivity.

        Raises:
            GraphAuthError: Invalid credentials.
            GraphConnectionError: Neo4j is unreachable.
        """
        try:
            import neo4j  # noqa: PLC0415  (deferred so tests can mock before import)
        except ModuleNotFoundError as exc:
            raise GraphConnectionError(
                "neo4j package is not installed. Run: pip install neo4j>=5.0"
            ) from exc

        auth = (self._user, self._password) if self._password else None

        try:
            driver = neo4j.GraphDatabase.driver(self._uri, auth=auth)
            driver.verify_connectivity()
            self._driver = driver
            log.info("neo4j.connected", uri=self._uri, database=self._database)
        except neo4j.exceptions.AuthError as exc:
            raise GraphAuthError(str(exc)) from exc
        except neo4j.exceptions.ServiceUnavailable as exc:
            raise GraphConnectionError(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise GraphConnectionError(str(exc)) from exc

    def close(self) -> None:
        """Close the driver. Safe to call when not connected."""
        if self._driver is not None:
            self._driver.close()
            self._driver = None
            log.info("neo4j.disconnected", uri=self._uri)

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> Neo4jClient:
        self.connect()
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def run_query(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Execute a read-or-write Cypher statement and return all records as dicts.

        Args:
            cypher: The Cypher query string.
            params: Optional parameter dictionary bound into the query.

        Returns:
            A list of records, each converted to a plain ``dict``.

        Raises:
            GraphConnectionError: Driver is not connected.
            GraphQueryError: Neo4j rejected the query.
        """
        if self._driver is None:
            raise GraphConnectionError("Not connected — call connect() or use as context manager.")

        import neo4j.exceptions as _neo4j_exc  # noqa: PLC0415

        try:
            with self._driver.session(database=self._database) as session:
                result = session.run(cypher, parameters=params or {})
                records = [dict(record) for record in result]
                log.debug("neo4j.query_ok", cypher=cypher[:80], rows=len(records))
                return records
        except _neo4j_exc.Neo4jError as exc:
            log.error("neo4j.query_failed", cypher=cypher[:80], error=str(exc))
            raise GraphQueryError(str(exc)) from exc

    def run_batch(self, queries: list[tuple[str, dict[str, Any]]]) -> None:
        """Execute multiple Cypher statements inside a single write transaction.

        All statements succeed or all are rolled back.

        Args:
            queries: List of ``(cypher, params)`` pairs executed in order.

        Raises:
            GraphConnectionError: Driver is not connected.
            GraphQueryError: Any query in the batch failed.
        """
        if self._driver is None:
            raise GraphConnectionError("Not connected — call connect() or use as context manager.")

        import neo4j.exceptions as _neo4j_exc  # noqa: PLC0415

        def _tx_work(tx: Any) -> None:
            for cypher, params in queries:
                tx.run(cypher, parameters=params)

        try:
            with self._driver.session(database=self._database) as session:
                session.execute_write(_tx_work)
                log.debug("neo4j.batch_ok", count=len(queries))
        except _neo4j_exc.Neo4jError as exc:
            log.error("neo4j.batch_failed", count=len(queries), error=str(exc))
            raise GraphQueryError(str(exc)) from exc

    def with_transaction(self, fn: Callable[[Any], Any]) -> Any:
        """Pass a live ``neo4j.Session`` to *fn* and return its result.

        Useful when callers need fine-grained transaction control.

        Args:
            fn: Callable that receives a ``neo4j.Session`` and returns a value.

        Raises:
            GraphConnectionError: Driver is not connected.
            GraphQueryError: Execution inside *fn* raised a Neo4j error.
        """
        if self._driver is None:
            raise GraphConnectionError("Not connected — call connect() or use as context manager.")

        import neo4j.exceptions as _neo4j_exc  # noqa: PLC0415

        try:
            with self._driver.session(database=self._database) as session:
                return fn(session)
        except _neo4j_exc.Neo4jError as exc:
            raise GraphQueryError(str(exc)) from exc
