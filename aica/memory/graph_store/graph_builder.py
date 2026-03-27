"""
Graph Builder — Sub-Plan 4.7

Orchestrates the full dependency graph construction pipeline:
1. Load AST JSONs (imports, functions, calls, exports, hooks, components, types)
2. Load scanner JSONs (routes, services, stores)
3. Connect to Neo4j
4. Create schema constraints
5. Build nodes (Files, Functions, Components, Types, Hooks)
6. Insert edges (Imports, Calls, Hook usage)
7. Build scanner nodes (Routes, Services, Stores)
8. Return structured summary

Public API
----------
build_dependency_graph(repo_path: Path) -> GraphSummary
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from aica.config import get_settings
from aica.core.logging.logger import get_logger
from aica.memory.graph_store.call_builder import insert_call_edges, insert_hook_usage_edges
from aica.memory.graph_store.import_builder import insert_import_edges
from aica.memory.graph_store.neo4j_client import Neo4jClient
from aica.memory.graph_store.node_builder import (
    build_component_nodes,
    build_file_nodes,
    build_function_nodes,
    build_hook_nodes,
    build_type_nodes,
)
from aica.memory.graph_store.scanner_builder import (
    build_route_nodes,
    build_service_nodes,
    build_store_nodes,
)
from aica.memory.graph_store.schema import setup_schema

log = get_logger("graph_store.builder")


# ---------------------------------------------------------------------------
# GraphSummary dataclass
# ---------------------------------------------------------------------------


@dataclass
class GraphSummary:
    """Summary statistics from a full dependency graph build."""

    files: int
    functions: int
    components: int
    types: int
    hooks: int
    routes: int
    services: int
    stores: int
    import_edges: int
    call_edges: int
    hook_edges: int


# ---------------------------------------------------------------------------
# JSON loading helpers
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> list[dict] | None:
    """
    Load JSON from *path*, returning None if file doesn't exist.
    Logs a warning on missing files but doesn't crash the pipeline.
    
    Note: Returns list[dict] or None. If the JSON contains a dict at the root,
    it will be wrapped in a list for consistent handling.
    """
    if not path.exists():
        log.warning("graph_builder.missing_json", path=str(path))
        return None

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Ensure we always return a list for consistent handling
        if isinstance(data, dict):
            data_len = len(data)
            log.debug("graph_builder.loaded_json_dict", path=str(path), keys=data_len)
            return [data]  # Wrap dict in list
        elif isinstance(data, list):
            data_len = len(data)
            log.debug("graph_builder.loaded_json", path=str(path), items=data_len)
            return data
        else:
            log.warning("graph_builder.unexpected_json_type", path=str(path), type=type(data).__name__)
            return None
    except (OSError, json.JSONDecodeError) as e:
        log.error("graph_builder.load_error", path=str(path), error=str(e))
        return None


def _flatten_call_graph(call_graph_data: list[dict] | None) -> list[dict]:
    """
    Transform nested call_graph.json structure (file → functions → calls)
    into a flat list of call records with {file, caller, callee, kind, line}.
    
    Input structure:
        [{"file": "...", "functions": [{"name": "...", "calls": [...]}]}]
    
    Output structure:
        [{"file": "...", "caller": "...", "callee": "...", "kind": "...", "line": ...}]
    """
    if not call_graph_data:
        return []

    flat_calls = []
    for file_entry in call_graph_data:
        file_path = file_entry.get("file")
        if not file_path:
            continue

        for func_entry in file_entry.get("functions", []):
            caller_name = func_entry.get("name")
            for call in func_entry.get("calls", []):
                flat_calls.append({
                    "file": file_path,
                    "caller": caller_name,
                    "callee": call.get("callee"),
                    "callee_object": call.get("callee_object"),
                    "kind": call.get("kind"),
                    "line": call.get("line"),
                })

    log.debug("graph_builder.flatten_calls", total_calls=len(flat_calls))
    return flat_calls


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


def build_dependency_graph(repo_path: Path) -> GraphSummary:
    """
    Build the full dependency graph from AST and scanner artifacts.
    
    Loads all JSON files from `.repo_intelligence/`, connects to Neo4j,
    creates schema, builds nodes and edges, and returns summary statistics.
    
    Args:
        repo_path: Root directory of the repository (must contain `.repo_intelligence/`)
    
    Returns:
        GraphSummary with counts for all node and edge types
    
    Raises:
        GraphConnectionError: If Neo4j connection fails
        GraphAuthError: If Neo4j authentication fails
        GraphQueryError: If any Cypher query fails
    """
    log.info("graph_builder.start", repo_path=str(repo_path))
    
    # --- Load AST JSONs ---
    ast_dir = repo_path / ".repo_intelligence" / "ast"
    
    imports_data = _load_json(ast_dir / "imports.json") or []
    functions_data = _load_json(ast_dir / "functions.json") or []
    call_graph_data = _load_json(ast_dir / "call_graph.json")
    hooks_data = _load_json(ast_dir / "hooks.json") or []
    components_data = _load_json(ast_dir / "components.json") or []
    types_data = _load_json(ast_dir / "types.json") or []
    
    # Flatten call_graph structure
    calls_data = _flatten_call_graph(call_graph_data)
    
    log.info(
        "graph_builder.loaded_ast",
        imports=len(imports_data),
        functions=len(functions_data),
        calls=len(calls_data),
        hooks=len(hooks_data),
        components=len(components_data),
        types=len(types_data),
    )
    
    # --- Load scanner JSONs ---
    scanner_dir = repo_path / ".repo_intelligence"
    
    routes_data = _load_json(scanner_dir / "routes.json") or []
    services_data = _load_json(scanner_dir / "services.json") or []
    stores_data = _load_json(scanner_dir / "stores.json") or []
    
    log.info(
        "graph_builder.loaded_scanner",
        routes=len(routes_data),
        services=len(services_data),
        stores=len(stores_data),
    )
    
    # --- Connect to Neo4j ---
    settings = get_settings()
    
    client = Neo4jClient(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password.get_secret_value(),
        database=settings.neo4j_database,
    )
    
    try:
        client.connect()
        log.info(
            "graph_builder.connected",
            uri=settings.neo4j_uri,
            database=settings.neo4j_database,
        )
        
        # --- Setup schema (constraints) ---
        setup_schema(client)
        log.info("graph_builder.schema_ready")
        
        # --- Build nodes ---
        file_count = build_file_nodes(
            client, functions_data, components_data, types_data, hooks_data
        )
        log.info("graph_builder.nodes.files", count=file_count)
        
        function_count = build_function_nodes(client, functions_data)
        log.info("graph_builder.nodes.functions", count=function_count)
        
        component_count = build_component_nodes(client, components_data)
        log.info("graph_builder.nodes.components", count=component_count)
        
        type_count = build_type_nodes(client, types_data)
        log.info("graph_builder.nodes.types", count=type_count)
        
        hook_count = build_hook_nodes(client, hooks_data, functions=functions_data)
        log.info("graph_builder.nodes.hooks", count=hook_count)
        
        # --- Build edges ---
        import_edge_count = insert_import_edges(client, imports_data, repo_path)
        log.info("graph_builder.edges.imports", count=import_edge_count)
        
        call_edge_count = insert_call_edges(client, calls_data, functions_data)
        log.info("graph_builder.edges.calls", count=call_edge_count)
        
        hook_edge_count = insert_hook_usage_edges(
            client, hooks_data, functions_data, components_data
        )
        log.info("graph_builder.edges.hooks", count=hook_edge_count)
        
        # --- Build scanner nodes ---
        route_count = build_route_nodes(client, routes_data)
        log.info("graph_builder.nodes.routes", count=route_count)
        
        service_count = build_service_nodes(client, services_data)
        log.info("graph_builder.nodes.services", count=service_count)
        
        store_count = build_store_nodes(client, stores_data)
        log.info("graph_builder.nodes.stores", count=store_count)
        
        # --- Return summary ---
        summary = GraphSummary(
            files=file_count,
            functions=function_count,
            components=component_count,
            types=type_count,
            hooks=hook_count,
            routes=route_count,
            services=service_count,
            stores=store_count,
            import_edges=import_edge_count,
            call_edges=call_edge_count,
            hook_edges=hook_edge_count,
        )
        
        log.info(
            "graph_builder.done",
            total_nodes=(
                file_count + function_count + component_count + type_count +
                hook_count + route_count + service_count + store_count
            ),
            total_edges=import_edge_count + call_edge_count + hook_edge_count,
        )
        
        return summary
    
    finally:
        client.close()
        log.debug("graph_builder.disconnected")
