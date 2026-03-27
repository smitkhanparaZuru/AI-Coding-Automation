"""Tests for aica/memory/graph_store/scanner_builder.py — Sub-Plan 4.6"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from aica.memory.graph_store.scanner_builder import (
    BATCH_SIZE,
    build_route_nodes,
    build_service_nodes,
    build_store_nodes,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client() -> MagicMock:
    """A mock Neo4jClient with run_query stubbed out."""
    mock = MagicMock()
    mock.run_query = MagicMock(return_value=[])
    return mock


# ---------------------------------------------------------------------------
# Sample entity factories
# ---------------------------------------------------------------------------


def _route(
    route: str = "/api/users",
    file: str = "app/api/users/route.ts",
    type: str = "api",
    methods: list[str] | None = None,
    tier: str | None = None,
    slot: str | None = None,
    **kwargs: object,
) -> dict:
    return {
        "route": route,
        "file": file,
        "type": type,
        "methods": methods if methods is not None else ["GET"],
        "tier": tier,
        "slot": slot,
        **kwargs,
    }


def _service(
    service: str = "AuthService",
    file: str = "src/services/auth.service.ts",
    exported_functions: list[str] | None = None,
    **kwargs: object,
) -> dict:
    return {
        "service": service,
        "file": file,
        "exported_functions": exported_functions if exported_functions is not None else ["login", "logout"],
        **kwargs,
    }


def _store(
    store: str = "user",
    path: str = "src/store/user",
    slices: list[str] | None = None,
    middleware: list[str] | None = None,
    **kwargs: object,
) -> dict:
    return {
        "store": store,
        "path": path,
        "slices": slices if slices is not None else ["auth"],
        "middleware": middleware if middleware is not None else ["devtools"],
        **kwargs,
    }


# ---------------------------------------------------------------------------
# TestBuildRouteNodes
# ---------------------------------------------------------------------------


class TestBuildRouteNodes:
    def test_empty_returns_zero(self, client: MagicMock) -> None:
        result = build_route_nodes(client, [])
        assert result == 0
        client.run_query.assert_not_called()

    def test_count_returned(self, client: MagicMock) -> None:
        routes = [
            _route(route="/api/users"),
            _route(route="/api/posts"),
            _route(route="/about"),
        ]
        result = build_route_nodes(client, routes)
        assert result == 3

    def test_skips_missing_route_key(self, client: MagicMock) -> None:
        routes = [
            _route(route="/api/users"),
            {"route": None, "file": "app/page.tsx", "type": "page"},
            {"route": "", "file": "app/layout.tsx", "type": "page"},
            _route(route="/home"),
        ]
        result = build_route_nodes(client, routes)
        assert result == 2  # Only the two valid routes

    def test_cypher_contains_merge_route(self, client: MagicMock) -> None:
        routes = [_route()]
        build_route_nodes(client, routes)
        # First call is node creation
        cypher = client.run_query.call_args_list[0][0][0]
        assert "MERGE" in cypher
        assert "Route" in cypher
        assert "route: row.route" in cypher

    def test_params_contain_route_key(self, client: MagicMock) -> None:
        routes = [_route(route="/api/users")]
        build_route_nodes(client, routes)
        # First call is node creation
        params = client.run_query.call_args_list[0][0][1]
        assert "batch" in params
        assert params["batch"][0]["route"] == "/api/users"

    def test_edge_query_called(self, client: MagicMock) -> None:
        routes = [_route()]
        build_route_nodes(client, routes)
        # Two queries per batch: node + edge
        assert client.run_query.call_count == 2
        # Second call is edge creation
        edge_cypher = client.run_query.call_args_list[1][0][0]
        assert "HAS_ROUTE" in edge_cypher
        assert "MATCH (f:File" in edge_cypher

    def test_batching(self, client: MagicMock) -> None:
        # BATCH_SIZE + 1 routes → 2 batches → 4 queries (2 per batch)
        routes = [_route(route=f"/api/route{i}") for i in range(BATCH_SIZE + 1)]
        build_route_nodes(client, routes)
        assert client.run_query.call_count == 4

    def test_optional_fields_stored(self, client: MagicMock) -> None:
        routes = [
            _route(
                route="/api/edge",
                tier="edge",
                slot="@modal",
                methods=["GET", "POST"],
            )
        ]
        build_route_nodes(client, routes)
        params = client.run_query.call_args_list[0][0][1]
        batch_row = params["batch"][0]
        assert batch_row["tier"] == "edge"
        assert batch_row["slot"] == "@modal"
        assert batch_row["methods"] == ["GET", "POST"]


# ---------------------------------------------------------------------------
# TestBuildServiceNodes
# ---------------------------------------------------------------------------


class TestBuildServiceNodes:
    def test_empty_returns_zero(self, client: MagicMock) -> None:
        result = build_service_nodes(client, [])
        assert result == 0
        client.run_query.assert_not_called()

    def test_count_returned(self, client: MagicMock) -> None:
        services = [
            _service(service="AuthService"),
            _service(service="UserService"),
            _service(service="DataService"),
        ]
        result = build_service_nodes(client, services)
        assert result == 3

    def test_skips_missing_service_key(self, client: MagicMock) -> None:
        services = [
            _service(service="AuthService"),
            {"service": None, "file": "src/utils/helpers.ts"},
            {"service": "", "file": "src/utils/constants.ts"},
            _service(service="UserService"),
        ]
        result = build_service_nodes(client, services)
        assert result == 2  # Only the two valid services

    def test_name_mapped_from_service_field(self, client: MagicMock) -> None:
        services = [_service(service="AuthService")]
        build_service_nodes(client, services)
        # First call is node creation
        params = client.run_query.call_args_list[0][0][1]
        assert params["batch"][0]["name"] == "AuthService"

    def test_cypher_contains_merge_service(self, client: MagicMock) -> None:
        services = [_service()]
        build_service_nodes(client, services)
        # First call is node creation
        cypher = client.run_query.call_args_list[0][0][0]
        assert "MERGE" in cypher
        assert "Service" in cypher
        assert "name: row.name" in cypher

    def test_edge_query_called(self, client: MagicMock) -> None:
        services = [_service()]
        build_service_nodes(client, services)
        # Two queries per batch: node + edge
        assert client.run_query.call_count == 2
        # Second call is edge creation
        edge_cypher = client.run_query.call_args_list[1][0][0]
        assert "BELONGS_TO" in edge_cypher
        assert "MATCH (f:File" in edge_cypher

    def test_batching(self, client: MagicMock) -> None:
        # BATCH_SIZE + 1 services → 2 batches → 4 queries (2 per batch)
        services = [_service(service=f"Service{i}") for i in range(BATCH_SIZE + 1)]
        build_service_nodes(client, services)
        assert client.run_query.call_count == 4

    def test_exported_functions_stored(self, client: MagicMock) -> None:
        services = [
            _service(
                service="AuthService",
                exported_functions=["login", "logout", "verify"],
            )
        ]
        build_service_nodes(client, services)
        params = client.run_query.call_args_list[0][0][1]
        batch_row = params["batch"][0]
        assert batch_row["exported_functions"] == ["login", "logout", "verify"]


# ---------------------------------------------------------------------------
# TestBuildStoreNodes
# ---------------------------------------------------------------------------


class TestBuildStoreNodes:
    def test_empty_returns_zero(self, client: MagicMock) -> None:
        result = build_store_nodes(client, [])
        assert result == 0
        client.run_query.assert_not_called()

    def test_count_returned(self, client: MagicMock) -> None:
        stores = [
            _store(store="user"),
            _store(store="chat"),
            _store(store="settings"),
        ]
        result = build_store_nodes(client, stores)
        assert result == 3

    def test_skips_missing_store_key(self, client: MagicMock) -> None:
        stores = [
            _store(store="user"),
            {"store": None, "path": "src/store/unknown"},
            {"store": "", "path": "src/store/empty"},
            _store(store="chat"),
        ]
        result = build_store_nodes(client, stores)
        assert result == 2  # Only the two valid stores

    def test_cypher_uses_merge_for_file(self, client: MagicMock) -> None:
        stores = [_store()]
        build_store_nodes(client, stores)
        # Second call is edge creation — should use MERGE for File node
        edge_cypher = client.run_query.call_args_list[1][0][0]
        assert "MERGE (f:File" in edge_cypher
        assert "HAS_STORE" in edge_cypher

    def test_params_contain_store_key(self, client: MagicMock) -> None:
        stores = [_store(store="user")]
        build_store_nodes(client, stores)
        # First call is node creation
        params = client.run_query.call_args_list[0][0][1]
        assert params["batch"][0]["store"] == "user"

    def test_params_contain_path(self, client: MagicMock) -> None:
        stores = [_store(path="src/store/user")]
        build_store_nodes(client, stores)
        # First call is node creation
        params = client.run_query.call_args_list[0][0][1]
        assert params["batch"][0]["path"] == "src/store/user"

    def test_edge_query_called(self, client: MagicMock) -> None:
        stores = [_store()]
        build_store_nodes(client, stores)
        # Two queries per batch: node + edge
        assert client.run_query.call_count == 2

    def test_batching(self, client: MagicMock) -> None:
        # BATCH_SIZE + 1 stores → 2 batches → 4 queries (2 per batch)
        stores = [_store(store=f"store{i}") for i in range(BATCH_SIZE + 1)]
        build_store_nodes(client, stores)
        assert client.run_query.call_count == 4

    def test_slices_and_middleware_stored(self, client: MagicMock) -> None:
        stores = [
            _store(
                store="user",
                slices=["auth", "credits", "modelList"],
                middleware=["devtools", "subscribeWithSelector", "persist"],
            )
        ]
        build_store_nodes(client, stores)
        params = client.run_query.call_args_list[0][0][1]
        batch_row = params["batch"][0]
        assert batch_row["slices"] == ["auth", "credits", "modelList"]
        assert batch_row["middleware"] == ["devtools", "subscribeWithSelector", "persist"]
