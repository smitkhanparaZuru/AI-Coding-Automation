"""
Code Chunkers — Sub-Plan 2.2-2.6

Transform AST JSON outputs into embeddable code chunks with rich metadata.

Public API
----------
chunk_functions(functions: list[dict], repo_path: Path) -> list[CodeChunk]
chunk_components(components: list[dict], repo_path: Path) -> list[CodeChunk]
chunk_types(types: list[dict], repo_path: Path) -> list[CodeChunk]
create_code_chunks(repo_path: Path) -> list[CodeChunk]
"""

from __future__ import annotations

import json
from pathlib import Path

from aica.core.logging.logger import get_logger
from aica.memory.vector_store.schemas import ChunkMetadata, CodeChunk
from aica.memory.vector_store.utils import (
    extract_source_lines,
    infer_feature,
    truncate_text,
)

log = get_logger("vector_store.chunker")

# Maximum characters per chunk before truncation
MAX_CHUNK_SIZE = 2000


def chunk_functions(functions: list[dict], repo_path: Path) -> list[CodeChunk]:
    """Convert function definitions to code chunks.

    Extracts function source code from files using line numbers from AST output.
    Includes function signature, body, and docstring/JSDoc if present.

    Args:
        functions: List of function dicts from extract_functions (functions.json).
        repo_path: Absolute path to repository root.

    Returns:
        List of CodeChunk instances with function code and metadata.

    Example:
        >>> functions = [{"file": "src/utils.ts", "name": "calc", "line": 10, ...}]
        >>> chunks = chunk_functions(functions, Path("/repo"))
        >>> print(chunks[0].id)
        src/utils.ts:function:calc:10
    """
    chunks: list[CodeChunk] = []

    for fn in functions:
        # Validate required fields
        if not all(key in fn for key in ("file", "line")):
            log.warning("chunker.function.missing_fields", entry=fn)
            continue

        file_path = repo_path / fn["file"]
        name = fn.get("name") or "anonymous"
        line = fn["line"]

        # Extract function source (heuristic: 50 lines should cover most functions)
        source_text = extract_source_lines(file_path, line, line + 49)
        if not source_text:
            log.debug(
                "chunker.function.no_source",
                file=fn["file"],
                line=line,
            )
            continue

        # Try to include docstring/JSDoc (3 lines before function)
        if line > 3:
            preceding = extract_source_lines(file_path, line - 3, line - 1)
            if preceding and ("/**" in preceding or "//" in preceding):
                source_text = preceding + "\n" + source_text

        # Truncate if needed
        text, was_truncated = truncate_text(source_text, MAX_CHUNK_SIZE)

        # Build chunk ID: {file}:function:{name}:{line}
        chunk_id = f"{fn['file']}:function:{name}:{line}"

        # Determine language from file extension
        language = _infer_language(fn["file"])

        # Create metadata
        metadata = ChunkMetadata(
            file=fn["file"],
            line=line,
            chunk_type="function",
            name=name,
            exported=fn.get("exported", False),
            feature=infer_feature(fn["file"]),
            dependencies=[],  # Enriched later by orchestrator
            language=language,
            truncated=was_truncated,
            kind=fn.get("kind"),
            async_=fn.get("async"),
            params=fn.get("params"),
        )

        chunk = CodeChunk(id=chunk_id, text=text, metadata=metadata)
        chunks.append(chunk)

    log.info("chunker.functions.completed", count=len(chunks))
    return chunks


def chunk_components(components: list[dict], repo_path: Path) -> list[CodeChunk]:
    """Convert React component definitions to code chunks.

    Extracts component source including JSX return statement and props.

    Args:
        components: List of component dicts from extract_components (components.json).
        repo_path: Absolute path to repository root.

    Returns:
        List of CodeChunk instances with component code and metadata.

    Example:
        >>> components = [{"file": "src/Button.tsx", "name": "Button", "line": 5, ...}]
        >>> chunks = chunk_components(components, Path("/repo"))
        >>> print(chunks[0].metadata.chunk_type)
        component
    """
    chunks: list[CodeChunk] = []

    for comp in components:
        # Validate required fields
        if not all(key in comp for key in ("file", "name", "line")):
            log.warning("chunker.component.missing_fields", entry=comp)
            continue

        file_path = repo_path / comp["file"]
        name = comp["name"]
        line = comp["line"]

        # Extract component source (heuristic: 60 lines for components with JSX)
        source_text = extract_source_lines(file_path, line, line + 59)
        if not source_text:
            log.debug(
                "chunker.component.no_source",
                file=comp["file"],
                line=line,
            )
            continue

        # Try to include JSDoc/comments (3 lines before)
        if line > 3:
            preceding = extract_source_lines(file_path, line - 3, line - 1)
            if preceding and ("/**" in preceding or "//" in preceding):
                source_text = preceding + "\n" + source_text

        # Truncate if needed
        text, was_truncated = truncate_text(source_text, MAX_CHUNK_SIZE)

        # Build chunk ID: {file}:component:{name}:{line}
        chunk_id = f"{comp['file']}:component:{name}:{line}"

        # Determine language (components are typically TSX/JSX)
        language = _infer_language(comp["file"])

        # Create metadata
        metadata = ChunkMetadata(
            file=comp["file"],
            line=line,
            chunk_type="component",
            name=name,
            exported=comp.get("exported", False),
            feature=infer_feature(comp["file"]),
            dependencies=[],  # Enriched later
            language=language,
            truncated=was_truncated,
            kind=comp.get("kind"),
            props=comp.get("props"),
        )

        chunk = CodeChunk(id=chunk_id, text=text, metadata=metadata)
        chunks.append(chunk)

    log.info("chunker.components.completed", count=len(chunks))
    return chunks


def chunk_types(types: list[dict], repo_path: Path) -> list[CodeChunk]:
    """Convert TypeScript type/interface definitions to code chunks.

    Extracts full type definitions including all members.

    Args:
        types: List of type dicts from extract_types (types.json).
        repo_path: Absolute path to repository root.

    Returns:
        List of CodeChunk instances with type definitions and metadata.

    Example:
        >>> types = [{"file": "src/types.ts", "name": "User", "line": 8, ...}]
        >>> chunks = chunk_types(types, Path("/repo"))
        >>> print(chunks[0].metadata.kind)
        interface
    """
    chunks: list[CodeChunk] = []

    for typ in types:
        # Validate required fields
        if not all(key in typ for key in ("file", "name", "line")):
            log.warning("chunker.type.missing_fields", entry=typ)
            continue

        file_path = repo_path / typ["file"]
        name = typ["name"]
        line = typ["line"]

        # Extract type definition (heuristic: 30 lines for type definitions)
        source_text = extract_source_lines(file_path, line, line + 29)
        if not source_text:
            log.debug(
                "chunker.type.no_source",
                file=typ["file"],
                line=line,
            )
            continue

        # Try to include JSDoc/comments (3 lines before)
        if line > 3:
            preceding = extract_source_lines(file_path, line - 3, line - 1)
            if preceding and ("/**" in preceding or "//" in preceding):
                source_text = preceding + "\n" + source_text

        # Truncate if needed (types are usually shorter)
        text, was_truncated = truncate_text(source_text, MAX_CHUNK_SIZE)

        # Build chunk ID: {file}:type:{name}:{line}
        chunk_id = f"{typ['file']}:type:{name}:{line}"

        # Determine language
        language = _infer_language(typ["file"])

        # Create metadata
        metadata = ChunkMetadata(
            file=typ["file"],
            line=line,
            chunk_type="type",
            name=name,
            exported=typ.get("exported", False),
            feature=infer_feature(typ["file"]),
            dependencies=[],  # Enriched later
            language=language,
            truncated=was_truncated,
            kind=typ.get("kind"),
            members=typ.get("members"),
        )

        chunk = CodeChunk(id=chunk_id, text=text, metadata=metadata)
        chunks.append(chunk)

    log.info("chunker.types.completed", count=len(chunks))
    return chunks


def create_code_chunks(repo_path: Path) -> list[CodeChunk]:
    """Orchestrate chunking of all AST outputs into embeddable code chunks.

    Loads functions.json, components.json, types.json from .repo_intelligence/ast/,
    chunks each entity type, deduplicates, enriches with feature detection and
    dependencies from imports.json.

    Args:
        repo_path: Absolute path to repository root.

    Returns:
        Consolidated list of CodeChunk instances ready for embedding.

    Raises:
        FileNotFoundError: If .repo_intelligence/ast/ directory doesn't exist.

    Example:
        >>> chunks = create_code_chunks(Path("/path/to/repo"))
        >>> print(f"Generated {len(chunks)} chunks")
        Generated 1234 chunks
    """
    ast_dir = repo_path / ".repo_intelligence" / "ast"

    if not ast_dir.exists():
        log.error("chunker.orchestrator.ast_dir_missing", path=str(ast_dir))
        raise FileNotFoundError(f"AST directory not found: {ast_dir}")

    # Load AST JSON files
    functions = _load_json(ast_dir / "functions.json")
    components = _load_json(ast_dir / "components.json")
    types = _load_json(ast_dir / "types.json")

    log.info(
        "chunker.orchestrator.loaded",
        functions=len(functions),
        components=len(components),
        types=len(types),
    )

    # Chunk each entity type
    function_chunks = chunk_functions(functions, repo_path)
    component_chunks = chunk_components(components, repo_path)
    type_chunks = chunk_types(types, repo_path)

    # Combine all chunks
    all_chunks = function_chunks + component_chunks + type_chunks

    # Deduplicate by ID (prefer exported=True over exported=False)
    deduplicated = _deduplicate_chunks(all_chunks)

    # Enrich with dependencies from imports.json
    imports = _load_json(ast_dir / "imports.json")
    enriched = _enrich_dependencies(deduplicated, imports)

    log.info("chunker.orchestrator.completed", total_chunks=len(enriched))
    return enriched


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _load_json(file_path: Path) -> list[dict]:
    """Load JSON file, return empty list if missing or malformed."""
    if not file_path.exists():
        log.warning("chunker.load_json.missing", file=str(file_path))
        return []

    try:
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError) as e:
        log.error("chunker.load_json.failed", file=str(file_path), error=str(e))
        return []


def _infer_language(file_path: str) -> str:
    """Infer language from file extension."""
    if file_path.endswith(".tsx"):
        return "tsx"
    elif file_path.endswith(".jsx"):
        return "jsx"
    elif file_path.endswith(".js"):
        return "javascript"
    else:
        return "typescript"


def _deduplicate_chunks(chunks: list[CodeChunk]) -> list[CodeChunk]:
    """Deduplicate chunks by ID, preferring exported=True over exported=False.

    Args:
        chunks: List of code chunks (may contain duplicates).

    Returns:
        Deduplicated list with exported chunks preferred.
    """
    chunk_map: dict[str, CodeChunk] = {}

    for chunk in chunks:
        chunk_id = chunk.id

        if chunk_id not in chunk_map:
            chunk_map[chunk_id] = chunk
        else:
            # Prefer exported over non-exported
            existing = chunk_map[chunk_id]
            if chunk.metadata.exported and not existing.metadata.exported:
                chunk_map[chunk_id] = chunk
                log.debug(
                    "chunker.dedup.replaced",
                    id=chunk_id,
                    reason="exported_preference",
                )

    deduplicated = list(chunk_map.values())
    duplicates_removed = len(chunks) - len(deduplicated)

    if duplicates_removed > 0:
        log.info("chunker.dedup.completed", removed=duplicates_removed)

    return deduplicated


def _enrich_dependencies(
    chunks: list[CodeChunk], imports: list[dict]
) -> list[CodeChunk]:
    """Enrich chunks with dependency information from imports.json.

    Builds a map of {file: [imported_modules]} and adds dependencies to
    each chunk's metadata.

    Args:
        chunks: List of code chunks.
        imports: List of import dicts from imports.json.

    Returns:
        Chunks with enriched metadata.dependencies.
    """
    # Build file -> imports map
    file_imports: dict[str, list[str]] = {}
    for imp in imports:
        file = imp.get("file")
        source = imp.get("source")
        if file and source:
            if file not in file_imports:
                file_imports[file] = []
            file_imports[file].append(source)

    # Enrich chunks
    enriched_count = 0
    for chunk in chunks:
        file_deps = file_imports.get(chunk.metadata.file, [])
        if file_deps:
            # Deduplicate and sort
            chunk.metadata.dependencies = sorted(set(file_deps))
            enriched_count += 1

    log.info("chunker.enrich.completed", enriched_files=enriched_count)
    return chunks
