"""
Node Builder — Sub-Plan 4.3

Creates File, Function, Component, Type, and Hook nodes in Neo4j from the
flat entity dicts produced by the AST extractor pipeline.  All write
operations use batched UNWIND queries (500 rows per round-trip) so that
large repositories don't flood the driver with individual statements.

Public API
----------
build_file_nodes(client, functions, components, types, hooks) -> int
build_function_nodes(client, functions) -> int
build_component_nodes(client, components) -> int
build_type_nodes(client, types) -> int
build_hook_nodes(client, hooks, functions=None) -> int
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

from aica.core.logging.logger import get_logger
from aica.memory.graph_store.schema import NodeLabel, RelType

if TYPE_CHECKING:
    from aica.memory.graph_store.neo4j_client import Neo4jClient

log = get_logger("graph.node_builder")

BATCH_SIZE = 500


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _chunks(items: list, size: int) -> Iterator[list]:
    """Yield successive non-overlapping chunks of *size* from *items*."""
    for i in range(0, len(items), size):
        yield items[i : i + size]


# ---------------------------------------------------------------------------
# File nodes
# ---------------------------------------------------------------------------


def build_file_nodes(
    client: Neo4jClient,
    functions: list[dict],
    components: list[dict],
    types: list[dict],
    hooks: list[dict],
) -> int:
    """MERGE one File node per unique path found across all entity lists.

    Args:
        client: Connected Neo4jClient.
        functions: Output of extract_functions.
        components: Output of extract_components.
        types: Output of extract_types.
        hooks: Output of extract_hooks.

    Returns:
        Number of unique file paths written.
    """
    paths: set[str] = set()
    for entity_list in (functions, components, types, hooks):
        for entity in entity_list:
            if file := entity.get("file"):
                paths.add(file)

    if not paths:
        return 0

    path_list = [{"path": p} for p in sorted(paths)]
    cypher = f"UNWIND $batch AS row MERGE (f:{NodeLabel.FILE} {{path: row.path}})"

    count = 0
    for chunk in _chunks(path_list, BATCH_SIZE):
        client.run_query(cypher, {"batch": chunk})
        count += len(chunk)

    log.info("node_builder.file_nodes", count=count)
    return count


# ---------------------------------------------------------------------------
# Function nodes
# ---------------------------------------------------------------------------


def build_function_nodes(client: Neo4jClient, functions: list[dict]) -> int:
    """MERGE Function nodes and DEFINES edges from File, skipping anonymous arrows.

    The function id matches the ``aica_function_id`` uniqueness constraint:
    ``"{file}::{name}::{line}"``

    The ``async`` field from the extractor is stored as ``is_async`` to avoid
    collision with the Python reserved keyword when building props dicts.

    Args:
        client: Connected Neo4jClient.
        functions: Output of extract_functions.

    Returns:
        Number of named functions written (anonymous entries skipped).
    """
    rows = []
    for fn in functions:
        name = fn.get("name")
        if name is None:
            continue
        fn_id = f"{fn['file']}::{name}::{fn['line']}"
        rows.append({
            "id": fn_id,
            "file": fn["file"],
            "props": {
                "name": name,
                "kind": fn.get("kind"),
                "is_async": fn.get("async", False),
                "params": fn.get("params", []),
                "line": fn.get("line"),
                "exported": fn.get("exported", False),
            },
        })

    if not rows:
        return 0

    cypher = (
        f"UNWIND $batch AS row "
        f"MERGE (f:{NodeLabel.FUNCTION} {{id: row.id}}) "
        f"SET f += row.props "
        f"WITH f, row "
        f"MATCH (file:{NodeLabel.FILE} {{path: row.file}}) "
        f"MERGE (file)-[:{RelType.DEFINES}]->(f)"
    )

    count = 0
    for chunk in _chunks(rows, BATCH_SIZE):
        client.run_query(cypher, {"batch": chunk})
        count += len(chunk)

    log.info("node_builder.function_nodes", count=count)
    return count


# ---------------------------------------------------------------------------
# Component nodes
# ---------------------------------------------------------------------------


def build_component_nodes(client: Neo4jClient, components: list[dict]) -> int:
    """MERGE Component nodes and DEFINES edges from File.

    The component id matches the ``aica_component_id`` uniqueness constraint:
    ``"{file}::{name}"``

    Args:
        client: Connected Neo4jClient.
        components: Output of extract_components.

    Returns:
        Number of components written.
    """
    rows = []
    for comp in components:
        comp_id = f"{comp['file']}::{comp['name']}"
        rows.append({
            "id": comp_id,
            "file": comp["file"],
            "props": {
                "name": comp.get("name"),
                "kind": comp.get("kind"),
                "props": comp.get("props", []),
                "exported": comp.get("exported", False),
                "line": comp.get("line"),
            },
        })

    if not rows:
        return 0

    cypher = (
        f"UNWIND $batch AS row "
        f"MERGE (c:{NodeLabel.COMPONENT} {{id: row.id}}) "
        f"SET c += row.props "
        f"WITH c, row "
        f"MATCH (file:{NodeLabel.FILE} {{path: row.file}}) "
        f"MERGE (file)-[:{RelType.DEFINES}]->(c)"
    )

    count = 0
    for chunk in _chunks(rows, BATCH_SIZE):
        client.run_query(cypher, {"batch": chunk})
        count += len(chunk)

    log.info("node_builder.component_nodes", count=count)
    return count


# ---------------------------------------------------------------------------
# Type nodes
# ---------------------------------------------------------------------------


def build_type_nodes(client: Neo4jClient, types: list[dict]) -> int:
    """MERGE Type nodes and DEFINES edges from File.

    Type has no uniqueness constraint, so nodes are merged on the composite
    key ``{file, name, line}`` to avoid duplicates while not requiring an
    artificial id property.

    Args:
        client: Connected Neo4jClient.
        types: Output of extract_types.

    Returns:
        Number of type entries written.
    """
    rows = []
    for typ in types:
        rows.append({
            "file": typ["file"],
            "name": typ.get("name"),
            "line": typ.get("line"),
            "props": {
                "kind": typ.get("kind"),
                "exported": typ.get("exported", False),
                "members": typ.get("members", []),
            },
        })

    if not rows:
        return 0

    cypher = (
        f"UNWIND $batch AS row "
        f"MERGE (t:{NodeLabel.TYPE} {{file: row.file, name: row.name, line: row.line}}) "
        f"SET t += row.props "
        f"WITH t, row "
        f"MATCH (file:{NodeLabel.FILE} {{path: row.file}}) "
        f"MERGE (file)-[:{RelType.DEFINES}]->(t)"
    )

    count = 0
    for chunk in _chunks(rows, BATCH_SIZE):
        client.run_query(cypher, {"batch": chunk})
        count += len(chunk)

    log.info("node_builder.type_nodes", count=count)
    return count


# ---------------------------------------------------------------------------
# Hook nodes
# ---------------------------------------------------------------------------


def build_hook_nodes(
    client: Neo4jClient,
    hooks: list[dict],
    functions: list[dict] | None = None,
) -> int:
    """MERGE Hook nodes from call-site records and optionally add DEFINES edges.

    Step 1: Deduplicate hook names across all call sites, then batch-MERGE
    ``Hook {name}`` nodes using the ``aica_hook_name`` uniqueness constraint.

    Step 2: If *functions* is supplied, build a lookup of user-defined hook
    names (functions whose name starts with ``use`` that are in the codebase).
    For each such hook, send a DEFINES edge from the file that defines it.
    External hooks (``useState``, ``useEffect``, etc.) are silently skipped —
    they are not in the functions list and belong to external Module nodes.

    Args:
        client: Connected Neo4jClient.
        hooks: Output of extract_hooks (call-site records).
        functions: Output of extract_functions, used to resolve user-defined
            hook definitions. Pass ``None`` to skip DEFINES edges entirely.

    Returns:
        Number of unique Hook nodes written.
    """
    # Deduplicate hook names
    unique_names: set[str] = {h["name"] for h in hooks if h.get("name")}

    if not unique_names:
        return 0

    # Step 1 — MERGE Hook nodes
    name_rows = [{"name": n} for n in sorted(unique_names)]
    merge_cypher = f"UNWIND $batch AS row MERGE (h:{NodeLabel.HOOK} {{name: row.name}})"

    for chunk in _chunks(name_rows, BATCH_SIZE):
        client.run_query(merge_cypher, {"batch": chunk})

    # Step 2 — DEFINES edges for user-defined hooks
    if functions:
        # Build lookup: hook_name → file (last-wins for deduplication)
        fn_lookup: dict[str, str] = {
            fn["name"]: fn["file"]
            for fn in functions
            if fn.get("name") and fn["name"] in unique_names
        }

        if fn_lookup:
            defines_rows = [{"name": name, "file": file} for name, file in fn_lookup.items()]
            defines_cypher = (
                f"UNWIND $batch AS row "
                f"MATCH (file:{NodeLabel.FILE} {{path: row.file}}) "
                f"MATCH (h:{NodeLabel.HOOK} {{name: row.name}}) "
                f"MERGE (file)-[:{RelType.DEFINES}]->(h)"
            )
            for chunk in _chunks(defines_rows, BATCH_SIZE):
                client.run_query(defines_cypher, {"batch": chunk})

            log.info("node_builder.hook_defines_edges", count=len(fn_lookup))

    count = len(unique_names)
    log.info("node_builder.hook_nodes", count=count)
    return count
