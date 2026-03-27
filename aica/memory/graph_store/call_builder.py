"""
Call Builder — Sub-Plan 4.5

Resolves call-site records (from the AST extractor pipeline) to existing
Function, Component, and Hook nodes in Neo4j, then writes batched CALLS and
USES_HOOK edges.

All write operations use batched UNWIND queries (500 rows per round-trip)
to match the pattern established by node_builder and import_builder.

Public API
----------
insert_call_edges(client, calls, functions) -> int
insert_hook_usage_edges(client, hooks, functions, components) -> int
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aica.core.logging.logger import get_logger
from aica.memory.graph_store.node_builder import BATCH_SIZE, _chunks
from aica.memory.graph_store.schema import NodeLabel, RelType

if TYPE_CHECKING:
    from aica.memory.graph_store.neo4j_client import Neo4jClient

log = get_logger("graph.call_builder")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _build_function_id_map(functions: list[dict]) -> dict[str, list[dict]]:
    """Build a per-file lookup of named function entries, sorted by line.

    Each entry is ``{"name": str, "line": int, "id": str}`` where ``id``
    matches the uniqueness constraint format ``"{file}::{name}::{line}"``
    used by :func:`~aica.memory.graph_store.node_builder.build_function_nodes`.

    Anonymous functions (``name is None``) are excluded because they have no
    corresponding Function node in the graph.

    Args:
        functions: Output of ``extract_functions``.

    Returns:
        ``{file_path: [sorted entries]}`` mapping.
    """
    result: dict[str, list[dict]] = {}
    for fn in functions:
        name = fn.get("name")
        if name is None:
            continue
        file = fn["file"]
        line = fn.get("line", 0)
        fn_id = f"{file}::{name}::{line}"
        result.setdefault(file, []).append({"name": name, "line": line, "id": fn_id})

    for entries in result.values():
        entries.sort(key=lambda e: e["line"])

    return result


def _resolve_caller_id(
    file: str,
    caller_name: str,
    call_line: int,
    fn_id_map: dict[str, list[dict]],
) -> str | None:
    """Resolve the enclosing Function node ID for a call site.

    When multiple functions share the same name in the same file (e.g. a
    name that appears at different scopes), picks the entry with the highest
    ``line`` that is still ≤ *call_line* (i.e. the closest definition above
    the call).

    Args:
        file: Repo-relative path of the file containing the call site.
        caller_name: Name of the enclosing function as reported by the extractor.
        call_line: Line number of the call site (1-based).
        fn_id_map: Mapping built by :func:`_build_function_id_map`.

    Returns:
        Function node ID string, or ``None`` if no match is found.
    """
    best: str | None = None
    for entry in fn_id_map.get(file, []):
        if entry["name"] == caller_name and entry["line"] <= call_line:
            best = entry["id"]  # list is sorted asc, so last match is closest
    return best


def _resolve_callee_id(
    callee_name: str,
    caller_file: str,
    fn_id_map: dict[str, list[dict]],
) -> str | None:
    """Resolve a callee name to an existing Function node ID.

    Prefers a definition in the same file as the call site.  Falls back to a
    cross-file search; when multiple files define a function with the same
    name, the first alphabetically is returned and a debug log is emitted.

    Args:
        callee_name: Name of the called function.
        caller_file: Repo-relative path of the file containing the call site.
        fn_id_map: Mapping built by :func:`_build_function_id_map`.

    Returns:
        Function node ID string, or ``None`` when no definition is found.
    """
    # Same-file match preferred
    for entry in fn_id_map.get(caller_file, []):
        if entry["name"] == callee_name:
            return entry["id"]

    # Cross-file fallback — iterate files in alphabetical order for stability
    candidates: list[str] = []
    for file, entries in sorted(fn_id_map.items()):
        if file == caller_file:
            continue
        for entry in entries:
            if entry["name"] == callee_name:
                candidates.append(entry["id"])
                break  # one candidate per file is enough

    if not candidates:
        return None

    if len(candidates) > 1:
        log.debug(
            "call_builder.ambiguous_callee",
            callee=callee_name,
            candidates=candidates,
        )

    return candidates[0]


def _build_component_id_map(components: list[dict]) -> dict[tuple[str, str], str]:
    """Map ``(file, name)`` pairs to Component node IDs.

    The ID format ``"{file}::{name}"`` matches the uniqueness constraint used
    by :func:`~aica.memory.graph_store.node_builder.build_component_nodes`.

    Args:
        components: Output of ``extract_components``.

    Returns:
        ``{(file, name): component_id}`` mapping.
    """
    return {
        (comp["file"], comp["name"]): f"{comp['file']}::{comp['name']}"
        for comp in components
        if comp.get("name")
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def insert_call_edges(
    client: Neo4jClient,
    calls: list[dict],
    functions: list[dict],
) -> int:
    """Write CALLS edges between Function nodes for all resolved call sites.

    For each entry in *calls*:
    - ``caller is None`` → silently skipped (module-level / anonymous scope)
    - caller cannot be resolved to a Function node → skipped + warning logged
    - callee cannot be resolved to a Function node → skipped + warning logged
    - both resolved → ``(caller:Function)-[:CALLS]->(callee:Function)`` merged

    Args:
        client: Connected :class:`~aica.memory.graph_store.neo4j_client.Neo4jClient`.
        calls: Flat list of call site dicts from ``extract_calls``.
        functions: Flat list of function dicts from ``extract_functions``.

    Returns:
        Number of CALLS edges written.
    """
    fn_id_map = _build_function_id_map(functions)
    edges: list[dict] = []

    for call in calls:
        caller_name = call.get("caller")
        if caller_name is None:
            continue

        file = call.get("file", "")
        call_line = call.get("line", 0)
        callee_name = call.get("callee", "")

        caller_id = _resolve_caller_id(file, caller_name, call_line, fn_id_map)
        if caller_id is None:
            log.warning(
                "call_builder.unresolved_caller",
                file=file,
                caller=caller_name,
                line=call_line,
            )
            continue

        callee_id = _resolve_callee_id(callee_name, file, fn_id_map)
        if callee_id is None:
            log.warning(
                "call_builder.unresolved_callee",
                file=file,
                callee=callee_name,
                caller=caller_name,
            )
            continue

        edges.append({"caller_id": caller_id, "callee_id": callee_id})

    if not edges:
        return 0

    cypher = (
        f"UNWIND $batch AS row "
        f"MATCH (a:{NodeLabel.FUNCTION} {{id: row.caller_id}}) "
        f"MATCH (b:{NodeLabel.FUNCTION} {{id: row.callee_id}}) "
        f"MERGE (a)-[:{RelType.CALLS}]->(b)"
    )

    count = 0
    for chunk in _chunks(edges, BATCH_SIZE):
        client.run_query(cypher, {"batch": chunk})
        count += len(chunk)

    log.info("call_builder.call_edges", count=count)
    return count


def insert_hook_usage_edges(
    client: Neo4jClient,
    hooks: list[dict],
    functions: list[dict],
    components: list[dict],
) -> int:
    """Write USES_HOOK edges from Function/Component nodes to Hook nodes.

    For each entry in *hooks*:
    - ``caller is None`` → silently skipped (module-level scope)
    - caller resolves to a Function node → ``(fn:Function)-[:USES_HOOK]->(hook:Hook)``
    - caller resolves to a Component node → ``(comp:Component)-[:USES_HOOK]->(hook:Hook)``
    - caller resolves to neither → skipped + warning logged

    Function nodes are tried first; Component lookup is the fallback.  The two
    caller types are written in separate batched queries because Neo4j requires
    a concrete label in ``MATCH`` clauses.

    Args:
        client: Connected :class:`~aica.memory.graph_store.neo4j_client.Neo4jClient`.
        hooks: Flat list of hook call site dicts from ``extract_hooks``.
        functions: Flat list of function dicts from ``extract_functions``.
        components: Flat list of component dicts from ``extract_components``.

    Returns:
        Total number of USES_HOOK edges written (function + component callers).
    """
    fn_id_map = _build_function_id_map(functions)
    comp_id_map = _build_component_id_map(components)

    fn_edges: list[dict] = []
    comp_edges: list[dict] = []

    for hook in hooks:
        caller_name = hook.get("caller")
        if caller_name is None:
            continue

        file = hook.get("file", "")
        hook_line = hook.get("line", 0)
        hook_name = hook.get("name", "")

        # Function caller takes priority over Component
        caller_id = _resolve_caller_id(file, caller_name, hook_line, fn_id_map)
        if caller_id is not None:
            fn_edges.append({"caller_id": caller_id, "hook_name": hook_name})
            continue

        comp_id = comp_id_map.get((file, caller_name))
        if comp_id is not None:
            comp_edges.append({"caller_id": comp_id, "hook_name": hook_name})
            continue

        log.warning(
            "call_builder.unresolved_hook_caller",
            file=file,
            caller=caller_name,
            hook=hook_name,
        )

    fn_cypher = (
        f"UNWIND $batch AS row "
        f"MATCH (caller:{NodeLabel.FUNCTION} {{id: row.caller_id}}) "
        f"MATCH (h:{NodeLabel.HOOK} {{name: row.hook_name}}) "
        f"MERGE (caller)-[:{RelType.USES_HOOK}]->(h)"
    )
    comp_cypher = (
        f"UNWIND $batch AS row "
        f"MATCH (caller:{NodeLabel.COMPONENT} {{id: row.caller_id}}) "
        f"MATCH (h:{NodeLabel.HOOK} {{name: row.hook_name}}) "
        f"MERGE (caller)-[:{RelType.USES_HOOK}]->(h)"
    )

    fn_count = 0
    for chunk in _chunks(fn_edges, BATCH_SIZE):
        client.run_query(fn_cypher, {"batch": chunk})
        fn_count += len(chunk)

    comp_count = 0
    for chunk in _chunks(comp_edges, BATCH_SIZE):
        client.run_query(comp_cypher, {"batch": chunk})
        comp_count += len(chunk)

    log.info(
        "call_builder.hook_edges",
        function_edges=fn_count,
        component_edges=comp_count,
    )
    return fn_count + comp_count
