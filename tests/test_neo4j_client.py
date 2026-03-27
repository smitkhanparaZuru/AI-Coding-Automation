from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from aica.memory.graph_store.neo4j_client import (
    GraphAuthError,
    GraphConnectionError,
    GraphQueryError,
    Neo4jClient,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_driver_mock(session_records: list[dict[str, Any]] | None = None) -> MagicMock:
    """Build a mock neo4j.GraphDatabase.driver return value."""
    record_mocks = [MagicMock(**{"__iter__": lambda s: iter(rec.items())}) for rec in (session_records or [])]
    # Each mock record behaves like dict() when iterated: dict(record) → picks up items()
    # Use a simpler approach: make session.run() return objects that convert via dict()
    run_result = MagicMock()
    run_result.__iter__ = MagicMock(return_value=iter(
        [MagicMock(**{"keys.return_value": list(r.keys()), "data.return_value": r}) for r in (session_records or [])]
    ))

    session_mock = MagicMock()
    session_mock.__enter__ = MagicMock(return_value=session_mock)
    session_mock.__exit__ = MagicMock(return_value=False)
    session_mock.run.return_value = run_result

    driver_mock = MagicMock()
    driver_mock.session.return_value = session_mock
    driver_mock.verify_connectivity = MagicMock()
    driver_mock.close = MagicMock()

    return driver_mock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def driver_mock() -> MagicMock:
    return _make_driver_mock()


@pytest.fixture()
def connected_client(driver_mock: MagicMock) -> Neo4jClient:
    """A Neo4jClient with a pre-connected mock driver (skips real neo4j import)."""
    client = Neo4jClient(uri="bolt://localhost:7687", user="neo4j", password="test", database="neo4j")
    client._driver = driver_mock  # inject mock directly — avoids neo4j import in connect()
    return client


# ---------------------------------------------------------------------------
# connect()
# ---------------------------------------------------------------------------


class TestConnect:
    def test_connect_success(self) -> None:
        driver_mock = _make_driver_mock()

        neo4j_mod = MagicMock()
        neo4j_mod.GraphDatabase.driver.return_value = driver_mock
        neo4j_mod.exceptions.AuthError = type("AuthError", (Exception,), {})
        neo4j_mod.exceptions.ServiceUnavailable = type("ServiceUnavailable", (Exception,), {})

        with patch.dict("sys.modules", {"neo4j": neo4j_mod, "neo4j.exceptions": neo4j_mod.exceptions}):
            client = Neo4jClient(uri="bolt://localhost:7687", user="neo4j", password="pass")
            client.connect()

        neo4j_mod.GraphDatabase.driver.assert_called_once_with("bolt://localhost:7687", auth=("neo4j", "pass"))
        driver_mock.verify_connectivity.assert_called_once()
        assert client._driver is driver_mock

    def test_connect_auth_error_raises_graph_auth_error(self) -> None:
        class _AuthError(Exception):
            pass

        neo4j_mod = MagicMock()
        neo4j_mod.GraphDatabase.driver.side_effect = _AuthError("bad credentials")
        neo4j_mod.exceptions.AuthError = _AuthError
        neo4j_mod.exceptions.ServiceUnavailable = type("ServiceUnavailable", (Exception,), {})

        with patch.dict("sys.modules", {"neo4j": neo4j_mod, "neo4j.exceptions": neo4j_mod.exceptions}):
            client = Neo4jClient(uri="bolt://localhost:7687", password="wrong")
            with pytest.raises(GraphAuthError, match="bad credentials"):
                client.connect()

    def test_connect_service_unavailable_raises_graph_connection_error(self) -> None:
        class _ServiceUnavailable(Exception):
            pass

        neo4j_mod = MagicMock()
        neo4j_mod.exceptions.AuthError = type("AuthError", (Exception,), {})
        neo4j_mod.exceptions.ServiceUnavailable = _ServiceUnavailable
        neo4j_mod.GraphDatabase.driver.side_effect = _ServiceUnavailable("connection refused")

        with patch.dict("sys.modules", {"neo4j": neo4j_mod, "neo4j.exceptions": neo4j_mod.exceptions}):
            client = Neo4jClient(uri="bolt://localhost:7687")
            with pytest.raises(GraphConnectionError, match="connection refused"):
                client.connect()

    def test_connect_unknown_error_raises_graph_connection_error(self) -> None:
        neo4j_mod = MagicMock()
        neo4j_mod.exceptions.AuthError = type("AuthError", (Exception,), {})
        neo4j_mod.exceptions.ServiceUnavailable = type("ServiceUnavailable", (Exception,), {})
        neo4j_mod.GraphDatabase.driver.side_effect = OSError("network down")

        with patch.dict("sys.modules", {"neo4j": neo4j_mod, "neo4j.exceptions": neo4j_mod.exceptions}):
            client = Neo4jClient(uri="bolt://localhost:7687")
            with pytest.raises(GraphConnectionError, match="network down"):
                client.connect()

    def test_connect_no_password_omits_auth_tuple(self) -> None:
        driver_mock = _make_driver_mock()

        neo4j_mod = MagicMock()
        neo4j_mod.GraphDatabase.driver.return_value = driver_mock
        neo4j_mod.exceptions.AuthError = type("AuthError", (Exception,), {})
        neo4j_mod.exceptions.ServiceUnavailable = type("ServiceUnavailable", (Exception,), {})

        with patch.dict("sys.modules", {"neo4j": neo4j_mod, "neo4j.exceptions": neo4j_mod.exceptions}):
            client = Neo4jClient(uri="bolt://localhost:7687", password="")
            client.connect()

        # auth=None when password is empty string
        neo4j_mod.GraphDatabase.driver.assert_called_once_with("bolt://localhost:7687", auth=None)


# ---------------------------------------------------------------------------
# close()
# ---------------------------------------------------------------------------


class TestClose:
    def test_close_calls_driver_close(self, connected_client: Neo4jClient, driver_mock: MagicMock) -> None:
        connected_client.close()
        driver_mock.close.assert_called_once()
        assert connected_client._driver is None

    def test_close_safe_when_not_connected(self) -> None:
        client = Neo4jClient(uri="bolt://localhost:7687")
        client.close()  # must not raise


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


class TestContextManager:
    def test_context_manager_calls_connect_and_close(self) -> None:
        client = Neo4jClient(uri="bolt://localhost:7687", password="p")
        client.connect = MagicMock()  # type: ignore[method-assign]
        client.close = MagicMock()  # type: ignore[method-assign]

        with client as c:
            assert c is client

        client.connect.assert_called_once()
        client.close.assert_called_once()

    def test_context_manager_closes_on_exception(self) -> None:
        client = Neo4jClient(uri="bolt://localhost:7687", password="p")
        client.connect = MagicMock()  # type: ignore[method-assign]
        client.close = MagicMock()  # type: ignore[method-assign]

        with pytest.raises(ValueError):
            with client:
                raise ValueError("boom")

        client.close.assert_called_once()


# ---------------------------------------------------------------------------
# run_query()
# ---------------------------------------------------------------------------


class TestRunQuery:
    def test_run_query_returns_list_of_dicts(self, connected_client: Neo4jClient, driver_mock: MagicMock) -> None:
        record1, record2 = MagicMock(), MagicMock()
        # dict(record) is called — make records iterable as (key, value) pairs
        record1.keys.return_value = ["id", "name"]
        record1.__getitem__ = lambda self, k: {"id": "fn1", "name": "getData"}[k]
        record2.keys.return_value = ["id", "name"]
        record2.__getitem__ = lambda self, k: {"id": "fn2", "name": "setData"}[k]

        # Patch run to return an iterable of record-like objects that dict() can convert
        rows = [{"id": "fn1", "name": "getData"}, {"id": "fn2", "name": "setData"}]

        run_result = MagicMock()
        run_result.__iter__ = MagicMock(return_value=iter(
            [_DictRecord(r) for r in rows]
        ))
        driver_mock.session.return_value.__enter__.return_value.run.return_value = run_result

        neo4j_exc = MagicMock()
        neo4j_exc.Neo4jError = Exception

        with patch.dict("sys.modules", {"neo4j.exceptions": neo4j_exc}):
            result = connected_client.run_query("MATCH (n) RETURN n")

        assert result == rows

    def test_run_query_raises_when_not_connected(self) -> None:
        client = Neo4jClient(uri="bolt://localhost:7687")
        with pytest.raises(GraphConnectionError):
            client.run_query("MATCH (n) RETURN n")

    def test_run_query_maps_neo4j_error_to_query_error(self, connected_client: Neo4jClient, driver_mock: MagicMock) -> None:
        class _Neo4jError(Exception):
            pass

        neo4j_exc = MagicMock()
        neo4j_exc.Neo4jError = _Neo4jError
        driver_mock.session.return_value.__enter__.return_value.run.side_effect = _Neo4jError("syntax error")

        with patch.dict("sys.modules", {"neo4j.exceptions": neo4j_exc}):
            with pytest.raises(GraphQueryError, match="syntax error"):
                connected_client.run_query("INVALID CYPHER")


# ---------------------------------------------------------------------------
# run_batch()
# ---------------------------------------------------------------------------


class TestRunBatch:
    def test_run_batch_executes_in_single_transaction(self, connected_client: Neo4jClient, driver_mock: MagicMock) -> None:
        queries = [
            ("MERGE (n:File {path: $p})", {"p": "a.ts"}),
            ("MERGE (n:File {path: $p})", {"p": "b.ts"}),
        ]

        neo4j_exc = MagicMock()
        neo4j_exc.Neo4jError = Exception

        session = driver_mock.session.return_value.__enter__.return_value

        with patch.dict("sys.modules", {"neo4j.exceptions": neo4j_exc}):
            connected_client.run_batch(queries)

        # execute_write was called once (single transaction)
        session.execute_write.assert_called_once()

    def test_run_batch_raises_when_not_connected(self) -> None:
        client = Neo4jClient(uri="bolt://localhost:7687")
        with pytest.raises(GraphConnectionError):
            client.run_batch([("MERGE (n) RETURN n", {})])

    def test_run_batch_maps_neo4j_error_to_query_error(self, connected_client: Neo4jClient, driver_mock: MagicMock) -> None:
        class _Neo4jError(Exception):
            pass

        neo4j_exc = MagicMock()
        neo4j_exc.Neo4jError = _Neo4jError
        session = driver_mock.session.return_value.__enter__.return_value
        session.execute_write.side_effect = _Neo4jError("tx failed")

        with patch.dict("sys.modules", {"neo4j.exceptions": neo4j_exc}):
            with pytest.raises(GraphQueryError, match="tx failed"):
                connected_client.run_batch([("MERGE (n) RETURN n", {})])


# ---------------------------------------------------------------------------
# with_transaction()
# ---------------------------------------------------------------------------


class TestWithTransaction:
    def test_with_transaction_passes_session_to_fn(self, connected_client: Neo4jClient, driver_mock: MagicMock) -> None:
        received: list[Any] = []

        neo4j_exc = MagicMock()
        neo4j_exc.Neo4jError = Exception

        session = driver_mock.session.return_value.__enter__.return_value

        with patch.dict("sys.modules", {"neo4j.exceptions": neo4j_exc}):
            connected_client.with_transaction(lambda s: received.append(s))

        assert received == [session]

    def test_with_transaction_returns_fn_result(self, connected_client: Neo4jClient, driver_mock: MagicMock) -> None:
        neo4j_exc = MagicMock()
        neo4j_exc.Neo4jError = Exception

        with patch.dict("sys.modules", {"neo4j.exceptions": neo4j_exc}):
            result = connected_client.with_transaction(lambda _: 42)

        assert result == 42

    def test_with_transaction_raises_when_not_connected(self) -> None:
        client = Neo4jClient(uri="bolt://localhost:7687")
        with pytest.raises(GraphConnectionError):
            client.with_transaction(lambda s: None)


# ---------------------------------------------------------------------------
# Settings defaults
# ---------------------------------------------------------------------------


class TestSettingsDefaults:
    def test_defaults_from_settings_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AICA_NEO4J_URI", "bolt://remotehost:7688")
        monkeypatch.setenv("AICA_NEO4J_USER", "admin")
        monkeypatch.setenv("AICA_NEO4J_PASSWORD", "supersecret")
        monkeypatch.setenv("AICA_NEO4J_DATABASE", "mydb")

        # Clear the lru_cache so monkeypatched env vars are picked up
        from aica.config.settings import get_settings
        get_settings.cache_clear()

        try:
            client = Neo4jClient()
            assert client._uri == "bolt://remotehost:7688"
            assert client._user == "admin"
            assert client._password == "supersecret"
            assert client._database == "mydb"
        finally:
            get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class _DictRecord:
    """Minimal record stand-in: dict(record) works by iterating (key, value) pairs."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def __iter__(self):  # type: ignore[override]
        return iter(self._data.items())

    def keys(self) -> list[str]:
        return list(self._data.keys())

    def __getitem__(self, key: str) -> Any:
        return self._data[key]
