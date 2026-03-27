from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aica.memory.graph_store.neo4j_client import Neo4jClient


# ---------------------------------------------------------------------------
# Node labels
# ---------------------------------------------------------------------------


class NodeLabel(StrEnum):
    FILE = "File"
    FUNCTION = "Function"
    COMPONENT = "Component"
    HOOK = "Hook"
    TYPE = "Type"
    MODULE = "Module"  # external packages (npm, pip, etc.)
    ROUTE = "Route"
    SERVICE = "Service"
    STORE = "Store"


# ---------------------------------------------------------------------------
# Relationship types
# ---------------------------------------------------------------------------


class RelType(StrEnum):
    IMPORTS = "IMPORTS"
    DEFINES = "DEFINES"
    CALLS = "CALLS"
    EXPORTS = "EXPORTS"
    USES_HOOK = "USES_HOOK"
    HAS_ROUTE = "HAS_ROUTE"
    HAS_STORE = "HAS_STORE"
    BELONGS_TO = "BELONGS_TO"


# ---------------------------------------------------------------------------
# Uniqueness constraints (Neo4j 4.4+ named-constraint syntax)
#
# DDL is auto-commit only — never mix into explicit write transactions.
# Named constraints make IF NOT EXISTS idempotent across re-runs.
#
# Type and Service are intentionally excluded: no natural unique key is
# defined in the design spec; deduplication is handled by MERGE in builders.
# ---------------------------------------------------------------------------

CONSTRAINT_QUERIES: list[str] = [
    "CREATE CONSTRAINT aica_file_path IF NOT EXISTS FOR (n:File) REQUIRE n.path IS UNIQUE",
    "CREATE CONSTRAINT aica_function_id IF NOT EXISTS FOR (n:Function) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT aica_component_id IF NOT EXISTS FOR (n:Component) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT aica_hook_name IF NOT EXISTS FOR (n:Hook) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT aica_module_name IF NOT EXISTS FOR (n:Module) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT aica_route_route IF NOT EXISTS FOR (n:Route) REQUIRE n.route IS UNIQUE",
    "CREATE CONSTRAINT aica_store_store IF NOT EXISTS FOR (n:Store) REQUIRE n.store IS UNIQUE",
]


# ---------------------------------------------------------------------------
# Schema setup
# ---------------------------------------------------------------------------


def setup_schema(client: Neo4jClient) -> None:
    """Apply all uniqueness constraints idempotently.

    Each constraint is executed as a separate auto-commit query because Neo4j
    schema DDL cannot run inside an explicit write transaction.  Safe to call
    multiple times — every statement uses ``IF NOT EXISTS``.
    """
    for query in CONSTRAINT_QUERIES:
        client.run_query(query, {})
