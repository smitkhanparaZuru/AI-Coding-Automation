"""
Semantic Code Retrieval — Sub-Plan 4

Provides semantic search over code chunks stored in Qdrant vector database.
Supports metadata filtering, re-ranking, and result formatting for CLI and LLM consumption.

Public API
----------
search_code() — Main search function with filtering and re-ranking
build_qdrant_filter() — Convert user-friendly filters to Qdrant syntax
format_search_results() — Format results for CLI display with rich
build_context_from_results() — Format results for LLM context
"""

from __future__ import annotations

import time
from fnmatch import fnmatch
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from aica.config.settings import get_settings
from aica.core.logging import get_logger
from aica.memory.vector_store.exceptions import VectorStoreQueryError
from aica.memory.vector_store.factory import EmbeddingProvider
from aica.memory.vector_store.qdrant_client import QdrantClient
from aica.memory.vector_store.schemas import (
    CodeChunk,
    SearchQuery,
    SearchResponse,
    SearchResult,
)

log = get_logger("vector_store.retriever")


def build_qdrant_filter(filters: dict[str, Any]) -> dict[str, Any] | None:
    """Convert user-friendly filters to Qdrant filter syntax.

    Supported filters:
        file_pattern (str): Glob pattern for file paths (e.g., "src/**/*.ts")
        chunk_type (str): Entity type (function, component, type)
        feature (str): Feature/module name from directory structure
        exported_only (bool): Only include exported entities
        min_lines (int): Minimum line count
        max_lines (int): Maximum line count

    Args:
        filters: Dict with user-friendly filter keys.

    Returns:
        Dict in Qdrant filter syntax, or None if no filters.

    Example:
        >>> build_qdrant_filter({"exported_only": True, "chunk_type": "function"})
        {
            "must": [
                {"key": "exported", "match": {"value": True}},
                {"key": "chunk_type", "match": {"value": "function"}}
            ]
        }
    """
    if not filters:
        return None

    must_conditions = []

    # Chunk type filter (exact match)
    if "chunk_type" in filters:
        must_conditions.append({
            "key": "chunk_type",
            "match": {"value": filters["chunk_type"]}
        })

    # Feature filter (exact match)
    if "feature" in filters:
        must_conditions.append({
            "key": "feature",
            "match": {"value": filters["feature"]}
        })

    # Exported only filter
    if filters.get("exported_only"):
        must_conditions.append({
            "key": "exported",
            "match": {"value": True}
        })

    # Line count range filters
    if "min_lines" in filters or "max_lines" in filters:
        range_condition: dict[str, Any] = {"key": "line"}
        if "min_lines" in filters:
            range_condition["gte"] = filters["min_lines"]
        if "max_lines" in filters:
            range_condition["lte"] = filters["max_lines"]
        must_conditions.append({"range": range_condition})

    # File pattern is handled post-search (glob matching)
    # because Qdrant doesn't support glob patterns natively

    if not must_conditions:
        return None

    return {"must": must_conditions}


def _rerank_results(
    results: list[SearchResult],
    context_feature: str | None = None,
) -> list[SearchResult]:
    """Apply re-ranking adjustments to search results.

    Boosts:
        - Exported entities: +0.05
        - Entities with docstrings: +0.03 (detected via leading comments)
        - Entities in same feature as context: +0.04

    Args:
        results: List of search results to re-rank.
        context_feature: Optional feature name for contextual boosting.

    Returns:
        Re-ranked list sorted by adjusted_score (highest first).
    """
    for result in results:
        adjusted = result.score

        # Boost exported entities
        if result.chunk.metadata.exported:
            adjusted += 0.05

        # Boost entities with docstrings (heuristic: text starts with comment)
        text_start = result.chunk.text.lstrip()
        if text_start.startswith(("/**", "//", "/*")):
            adjusted += 0.03

        # Boost entities in same feature
        if context_feature and result.chunk.metadata.feature == context_feature:
            adjusted += 0.04

        # Cap at 1.0
        result.adjusted_score = min(adjusted, 1.0)

    # Sort by adjusted score (descending)
    results.sort(key=lambda r: r.adjusted_score, reverse=True)
    return results


def search_code(
    query: str | SearchQuery,
    qdrant_client: QdrantClient | None = None,
    embedding_provider: EmbeddingProvider | None = None,
) -> SearchResponse:
    """Perform semantic search over code chunks.

    Args:
        query: Query string or SearchQuery object with filters.
        qdrant_client: Optional QdrantClient (creates default if None).
        embedding_provider: Optional EmbeddingProvider (creates default if None).

    Returns:
        SearchResponse with ranked results and metadata.

    Raises:
        VectorStoreQueryError: Search operation failed.

    Example:
        >>> response = search_code("authentication logic")
        >>> for result in response.results[:3]:
        ...     print(f"{result.chunk.metadata.name} (score: {result.adjusted_score:.2f})")
    """
    start_time = time.perf_counter()

    # Parse query
    if isinstance(query, str):
        search_query = SearchQuery(text=query)
    else:
        search_query = query

    log.info(
        "search.started",
        query=search_query.text[:100],
        top_k=search_query.top_k,
        filters=list(search_query.filters.keys()),
    )

    # Initialize clients if not provided
    if qdrant_client is None:
        settings = get_settings()
        qdrant_client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None,
            collection_name=settings.qdrant_collection_name,
        )
        qdrant_client.connect()

    if embedding_provider is None:
        embedding_provider = EmbeddingProvider()

    try:
        # Generate query embedding
        log.debug("search.embedding_query", query=search_query.text[:50])
        query_vector = embedding_provider.generate_embedding(search_query.text)

        # Build Qdrant filter
        qdrant_filter = build_qdrant_filter(search_query.filters)
        log.debug("search.filter_built", filter=qdrant_filter is not None)

        # Execute search
        raw_results = qdrant_client.search(
            query_vector=query_vector,
            top_k=search_query.top_k,
            filter_dict=qdrant_filter,
        )

        log.debug("search.raw_results", count=len(raw_results))

        # Parse results into SearchResult objects
        search_results = []
        for raw_result in raw_results:
            try:
                chunk = CodeChunk.from_dict({
                    "id": raw_result["id"],
                    "text": raw_result["payload"]["text"],
                    "metadata": raw_result["payload"]["metadata"],
                    "embedding": None,  # Don't load embedding in results
                })

                # Apply min_score filter
                if raw_result["score"] < search_query.min_score:
                    continue

                # Apply file_pattern filter (post-search, glob-based)
                if "file_pattern" in search_query.filters:
                    pattern = search_query.filters["file_pattern"]
                    if not fnmatch(chunk.metadata.file, pattern):
                        continue

                search_results.append(
                    SearchResult(
                        score=raw_result["score"],
                        chunk=chunk,
                        explanation="High semantic similarity",
                        adjusted_score=raw_result["score"],  # Will be updated by rerank
                    )
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("search.result_parse_failed", result_id=raw_result.get("id"), error=str(exc))
                continue

        log.debug("search.parsed_results", count=len(search_results))

        # Apply re-ranking
        search_results = _rerank_results(
            search_results,
            context_feature=search_query.context_feature,
        )

        # Build response
        execution_time = (time.perf_counter() - start_time) * 1000  # Convert to ms
        response = SearchResponse(
            query=search_query.text,
            total_found=len(search_results),
            results=search_results,
            execution_time_ms=execution_time,
            filters_applied=search_query.filters,
        )

        log.info(
            "search.completed",
            query=search_query.text[:50],
            results=len(search_results),
            time_ms=f"{execution_time:.1f}",
        )

        return response

    except Exception as exc:
        log.error("search.failed", query=search_query.text[:50], error=str(exc))
        raise VectorStoreQueryError(f"Search failed: {exc}") from exc


def format_search_results(
    response: SearchResponse,
    console: Console | None = None,
    syntax_highlight: bool = True,
) -> None:
    """Format search results for CLI display using rich.

    Args:
        response: Search response to format.
        console: Optional rich Console (creates default if None).
        syntax_highlight: Whether to apply syntax highlighting to code previews.

    Example:
        >>> response = search_code("login function")
        >>> format_search_results(response)
    """
    if console is None:
        console = Console()

    # Header
    console.print()
    console.print(
        Panel(
            f"[bold cyan]Search Results[/bold cyan]\n"
            f"Query: [italic]{response.query}[/italic]\n"
            f"Found: {response.total_found} results in {response.execution_time_ms:.1f}ms",
            border_style="cyan",
        )
    )

    if not response.results:
        console.print("[yellow]No results found.[/yellow]")
        return

    # Results table
    for idx, result in enumerate(response.results, 1):
        metadata = result.chunk.metadata
        
        # Header line
        console.print(
            f"\n[bold]{idx}. {metadata.name}[/bold] "
            f"[dim]({metadata.chunk_type})[/dim] "
            f"[green]score: {result.adjusted_score:.3f}[/green]"
        )
        
        # File location
        console.print(f"   [dim]{metadata.file}:{metadata.line}[/dim]")
        
        # Code preview
        preview = result.get_preview(max_lines=3, max_chars_per_line=100)
        
        if syntax_highlight:
            try:
                syntax = Syntax(
                    preview,
                    metadata.language or "typescript",
                    theme="monokai",
                    line_numbers=False,
                    word_wrap=True,
                )
                console.print(syntax)
            except Exception:  # noqa: BLE001
                # Fall back to plain text if syntax highlighting fails
                console.print(f"   [dim]{preview}[/dim]")
        else:
            console.print(f"   [dim]{preview}[/dim]")

    console.print()


def build_context_from_results(
    response: SearchResponse,
    max_context_chars: int = 8000,
    include_score: bool = True,
) -> str:
    """Format search results for LLM context consumption.

    Args:
        response: Search response to format.
        max_context_chars: Maximum total character count.
        include_score: Whether to include similarity scores in output.

    Returns:
        Formatted context string ready for LLM consumption.

    Example:
        >>> response = search_code("database query functions")
        >>> context = build_context_from_results(response)
        >>> llm_prompt = f"Based on this code:\n\n{context}\n\nImplement a new query..."
    """
    if not response.results:
        return "No relevant code chunks found."

    lines = [
        f"Relevant code for query: '{response.query}'",
        f"Found {response.total_found} matches\n",
    ]

    total_chars = sum(len(line) for line in lines)

    for idx, result in enumerate(response.results, 1):
        metadata = result.chunk.metadata
        
        # Build header
        header_parts = [
            f"\n{idx}. {metadata.name}",
            f"({metadata.chunk_type})",
        ]
        
        if include_score:
            header_parts.append(f"[score: {result.adjusted_score:.2f}]")
        
        header = " ".join(header_parts)
        
        # Build metadata line
        meta_line = f"File: {metadata.file}:{metadata.line}"
        if metadata.exported:
            meta_line += " | exported"
        if metadata.feature:
            meta_line += f" | feature: {metadata.feature}"
        
        # Build code block
        code_block = f"\n```{metadata.language}\n{result.chunk.text}\n```\n"
        
        # Check if adding this result exceeds limit
        chunk_text = f"{header}\n{meta_line}{code_block}"
        if total_chars + len(chunk_text) > max_context_chars:
            lines.append(f"\n... ({response.total_found - idx + 1} more results truncated)")
            break
        
        lines.append(chunk_text)
        total_chars += len(chunk_text)

    return "".join(lines)
