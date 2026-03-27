"""
Scanner Builder — Sub-Plan 4.6

Ingests scanner JSON data (routes, services, stores) into Neo4j, building
nodes and edges from the flat dicts produced by the scanner detectors.

All write operations use batched UNWIND queries (500 rows per round-trip)
to match the pattern established by node_builder and call_builder.

Public API
----------
build_route_nodes(client, routes) -> int
build_service_nodes(client, services) -> int
build_store_nodes(client, stores) -> int
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aica.core.logging.logger import get_logger
from aica.memory.graph_store.node_builder import BATCH_SIZE, _chunks
from aica.memory.graph_store.schema import NodeLabel, RelType

if TYPE_CHECKING:
    from aica.memory.graph_store.neo4j_client import Neo4jClient

log = get_logger("graph.scanner_builder")


# ---------------------------------------------------------------------------
# Route nodes
# ---------------------------------------------------------------------------


def build_route_nodes(client: Neo4jClient, routes: list[dict]) -> int:
    """MERGE Route nodes and HAS_ROUTE edges from File.

    The route string matches the ``aica_route_route`` uniqueness constraint.
    Optional fields (tier, slot) are stored as null-able Neo4j properties.

    Args:
        client: Connected Neo4jClient.
        routes: Output of RouteDetector.detect() — list of route descriptor dicts.

    Returns:
        Number of route nodes written.
    """
    rows = []
    for route_entry in routes:
        route_str = route_entry.get("route")
        if not route_str:
            continue
        rows.append({
            "route": route_str,
            "file": route_entry.get("file", ""),
            "type": route_entry.get("type"),
            "methods": route_entry.get("methods", []),
            "tier": route_entry.get("tier"),
            "slot": route_entry.get("slot"),
        })

    if not rows:
        return 0

    # Query 1: Create/update Route nodes
    node_cypher = (
        f"UNWIND $batch AS row "
        f"MERGE (r:{NodeLabel.ROUTE} {{route: row.route}}) "
        f"SET r.type = row.type, r.methods = row.methods, r.tier = row.tier, r.slot = row.slot"
    )

    # Query 2: Create HAS_ROUTE edges from File to Route
    edge_cypher = (
        f"UNWIND $batch AS row "
        f"MATCH (f:{NodeLabel.FILE} {{path: row.file}}) "
        f"MATCH (r:{NodeLabel.ROUTE} {{route: row.route}}) "
        f"MERGE (f)-[:{RelType.HAS_ROUTE}]->(r)"
    )

    count = 0
    for chunk in _chunks(rows, BATCH_SIZE):
        client.run_query(node_cypher, {"batch": chunk})
        client.run_query(edge_cypher, {"batch": chunk})
        count += len(chunk)

    log.info("scanner_builder.route_nodes", count=count)
    return count


# ---------------------------------------------------------------------------
# Service nodes
# ---------------------------------------------------------------------------


def build_service_nodes(client: Neo4jClient, services: list[dict]) -> int:
    """MERGE Service nodes and BELONGS_TO edges from File.

    Service nodes are keyed on the ``name`` property, derived from the
    ``service`` field in each dict.  There is no uniqueness constraint for
    Service nodes in the schema (intentionally excluded); MERGE handles
    deduplication.

    Args:
        client: Connected Neo4jClient.
        services: Output of ServiceDetector.detect() — list of service descriptor dicts.

    Returns:
        Number of service nodes written.
    """
    rows = []
    for service_entry in services:
        service_name = service_entry.get("service")
        if not service_name:
            continue
        rows.append({
            "name": service_name,
            "file": service_entry.get("file", ""),
            "exported_functions": service_entry.get("exported_functions", []),
        })

    if not rows:
        return 0

    # Query 1: Create/update Service nodes
    node_cypher = (
        f"UNWIND $batch AS row "
        f"MERGE (s:{NodeLabel.SERVICE} {{name: row.name}}) "
        f"SET s.file = row.file, s.exported_functions = row.exported_functions"
    )

    # Query 2: Create BELONGS_TO edges from File to Service
    edge_cypher = (
        f"UNWIND $batch AS row "
        f"MATCH (f:{NodeLabel.FILE} {{path: row.file}}) "
        f"MATCH (s:{NodeLabel.SERVICE} {{name: row.name}}) "
        f"MERGE (f)-[:{RelType.BELONGS_TO}]->(s)"
    )

    count = 0
    for chunk in _chunks(rows, BATCH_SIZE):
        client.run_query(node_cypher, {"batch": chunk})
        client.run_query(edge_cypher, {"batch": chunk})
        count += len(chunk)

    log.info("scanner_builder.service_nodes", count=count)
    return count


# ---------------------------------------------------------------------------
# Store nodes
# ---------------------------------------------------------------------------


def build_store_nodes(client: Neo4jClient, stores: list[dict]) -> int:
    """MERGE Store nodes and HAS_STORE edges from File.

    The store string matches the ``aica_store_store`` uniqueness constraint.

    Store paths are directories (e.g. ``src/store/user``), not specific files,
    so the edge query uses ``MERGE (f:File)`` to create the File node if it
    doesn't exist, rather than ``MATCH`` which would silently skip.

    Args:
        client: Connected Neo4jClient.
        stores: Output of ZustandStoreDetector.detect() — list of store descriptor dicts.

    Returns:
        Number of store nodes written.
    """
    rows = []
    for store_entry in stores:
        store_name = store_entry.get("store")
        if not store_name:
            continue
        rows.append({
            "store": store_name,
            "path": store_entry.get("path", ""),
            "slices": store_entry.get("slices", []),
            "middleware": store_entry.get("middleware", []),
        })

    if not rows:
        return 0

    # Query 1: Create/update Store nodes
    node_cypher = (
        f"UNWIND $batch AS row "
        f"MERGE (st:{NodeLabel.STORE} {{store: row.store}}) "
        f"SET st.slices = row.slices, st.middleware = row.middleware"
    )

    # Query 2: Create HAS_STORE edges from File to Store
    # Note: MERGE (f:File) because store paths are directories — no prior File node
    edge_cypher = (
        f"UNWIND $batch AS row "
        f"MERGE (f:{NodeLabel.FILE} {{path: row.path}}) "
        f"MATCH (st:{NodeLabel.STORE} {{store: row.store}}) "
        f"MERGE (f)-[:{RelType.HAS_STORE}]->(st)"
    )

    count = 0
    for chunk in _chunks(rows, BATCH_SIZE):
        client.run_query(node_cypher, {"batch": chunk})
        client.run_query(edge_cypher, {"batch": chunk})
        count += len(chunk)

    log.info("scanner_builder.store_nodes", count=count)
    return count
