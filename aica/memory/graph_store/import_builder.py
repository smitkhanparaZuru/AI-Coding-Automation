"""
Import Builder — Sub-Plan 4.4

Resolves import specifiers produced by the AST extractor pipeline to real
file paths (for internal/alias imports) or Module node names (for external
packages), then writes batched IMPORTS edges into Neo4j.

Public API
----------
resolve_import_path(source, from_file, repo_root) -> str | None
insert_import_edges(client, imports, repo_root) -> int
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from aica.core.logging.logger import get_logger
from aica.memory.graph_store.node_builder import BATCH_SIZE, _chunks
from aica.memory.graph_store.schema import NodeLabel, RelType

if TYPE_CHECKING:
    from aica.memory.graph_store.neo4j_client import Neo4jClient

log = get_logger("graph.import_builder")

# Extension probe order: prefer TypeScript over JavaScript
_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx")

# Alias prefixes resolved to {repo_root}/src/
_ALIAS_SRC_PREFIXES = ("@/", "~/")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _classify_source(source: str) -> str:
    """Classify an import specifier as 'relative', 'alias', or 'external'.

    Mirrors the logic in ``aica.repo_intelligence.ast.extractors.imports`` to
    avoid a cross-layer import dependency.

    Rules:
        - ``./`` or ``../`` prefix  → ``"relative"``
        - ``@`` or ``~`` prefix     → ``"alias"``
        - anything else             → ``"external"``
    """
    if source.startswith("./") or source.startswith("../"):
        return "relative"
    if source.startswith("@") or source.startswith("~"):
        return "alias"
    return "external"


def _find_file(candidate: Path, repo_root: Path) -> str | None:
    """Return the repo-relative POSIX path for *candidate* if it resolves to a
    real file, or ``None`` if nothing matches.

    Probes bare path first (already has an extension), then each extension in
    ``_EXTENSIONS``, then index-file variants inside the candidate directory.

    Path-traversal above *repo_root* is blocked: ``ValueError`` raised by
    ``Path.relative_to`` causes an early ``None`` return.
    """
    def _to_posix(p: Path) -> str | None:
        try:
            return p.relative_to(repo_root).as_posix()
        except ValueError:
            return None

    # 1. Bare path (source already has an extension like "./foo.ts")
    if candidate.is_file():
        return _to_posix(candidate)

    # 2. Try each extension
    for ext in _EXTENSIONS:
        probe = candidate.with_suffix(ext)
        if probe.is_file():
            return _to_posix(probe)

    # 3. Try index files inside a directory
    for ext in _EXTENSIONS:
        probe = candidate / f"index{ext}"
        if probe.is_file():
            return _to_posix(probe)

    return None


# ---------------------------------------------------------------------------
# Public API — path resolver
# ---------------------------------------------------------------------------


def resolve_import_path(source: str, from_file: str, repo_root: Path) -> str | None:
    """Resolve an import specifier to a repo-relative POSIX path.

    External packages always return ``None`` (they become Module nodes, not
    File edges).  Unresolvable relative/alias paths also return ``None`` and
    are logged as warnings by the caller.

    Args:
        source:    Module specifier string, e.g. ``"./utils"``, ``"@/hooks/useAuth"``,
                   or ``"react"``.
        from_file: Repo-relative POSIX path of the file containing the import
                   statement, e.g. ``"src/app/page.tsx"``.
        repo_root: Absolute ``Path`` to the repository root.

    Returns:
        Repo-relative POSIX string (e.g. ``"src/utils/helpers.ts"``) on
        success, ``None`` otherwise.
    """
    kind = _classify_source(source)

    if kind == "external":
        return None

    if kind == "relative":
        base = (repo_root / Path(from_file).parent / source).resolve()
        return _find_file(base, repo_root)

    # --- alias ---
    # Only bare `@/` and `~/` prefixes map to {repo_root}/src/.
    # Scoped packages like `@lobehub/ui` start with `@` but have no `/`
    # immediately after the org name — treat them as unresolvable.
    for prefix in _ALIAS_SRC_PREFIXES:
        if source.startswith(prefix):
            stripped = source[len(prefix):]
            base = (repo_root / "src" / stripped).resolve()
            return _find_file(base, repo_root)

    # `@org/pkg` style or other unrecognised alias — external npm package
    return None


# ---------------------------------------------------------------------------
# Public API — edge inserter
# ---------------------------------------------------------------------------


def insert_import_edges(
    client: Neo4jClient,
    imports: list[dict],
    repo_root: Path,
) -> int:
    """Write IMPORTS edges into Neo4j for all entries in *imports*.

    For external packages a ``Module`` node is merged; for internal (relative /
    alias) imports a ``File``-to-``File`` edge is merged.  Both node types are
    created with ``MERGE`` so files outside the current AST scan (e.g. ``.d.ts``
    declaration files or bare re-exports) are handled gracefully.

    Unresolvable import paths are logged as warnings and silently skipped —
    the pipeline never stops on a missing file.

    Args:
        client:    Connected :class:`~aica.memory.graph_store.neo4j_client.Neo4jClient`.
        imports:   Output of ``extract_imports`` — list of import dicts from the
                   AST extractor pipeline.
        repo_root: Absolute ``Path`` to the repository root used to resolve
                   relative and alias specifiers.

    Returns:
        Total number of edges written (internal + external).
    """
    internal: list[dict] = []  # {from, to}
    seen_external: set[tuple[str, str]] = set()
    external: list[dict] = []  # {file, module}

    for imp in imports:
        source = imp.get("source", "")
        from_file = imp.get("file", "")
        kind = imp.get("import_kind") or _classify_source(source)

        if kind == "external":
            key = (from_file, source)
            if key not in seen_external:
                seen_external.add(key)
                external.append({"file": from_file, "module": source})
        else:
            resolved = resolve_import_path(source, from_file, repo_root)
            if resolved is None:
                log.warning(
                    "import_builder.unresolved_import",
                    source=source,
                    from_file=from_file,
                )
                continue
            internal.append({"from": from_file, "to": resolved})

    # --- Write external edges (File -> Module) ---
    external_cypher = (
        f"UNWIND $batch AS row "
        f"MERGE (m:{NodeLabel.MODULE} {{name: row.module}}) "
        f"MERGE (a:{NodeLabel.FILE} {{path: row.file}}) "
        f"MERGE (a)-[:{RelType.IMPORTS}]->(m)"
    )
    external_count = 0
    for chunk in _chunks(external, BATCH_SIZE):
        client.run_query(external_cypher, {"batch": chunk})
        external_count += len(chunk)

    # --- Write internal edges (File -> File) ---
    internal_cypher = (
        f"UNWIND $batch AS row "
        f"MERGE (a:{NodeLabel.FILE} {{path: row.from}}) "
        f"MERGE (b:{NodeLabel.FILE} {{path: row.to}}) "
        f"MERGE (a)-[:{RelType.IMPORTS}]->(b)"
    )
    internal_count = 0
    for chunk in _chunks(internal, BATCH_SIZE):
        client.run_query(internal_cypher, {"batch": chunk})
        internal_count += len(chunk)

    log.info(
        "import_builder.edges_created",
        internal=internal_count,
        external=external_count,
    )
    return internal_count + external_count
