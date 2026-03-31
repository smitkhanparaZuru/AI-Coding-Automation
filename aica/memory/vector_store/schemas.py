"""
Code Chunk Schemas — Sub-Plan 2.1 & 4.1

Pydantic models for code chunks with rich metadata for vector embedding and RAG.
Also includes models for semantic search queries and results.

Public API
----------
CodeChunk — Main chunk model with text, metadata, and optional embedding
ChunkMetadata — Structured metadata for code entities
SearchQuery — Query parameters for semantic search
SearchResult — Individual search result with score and chunk
SearchResponse — Complete search response with metadata
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field


class ChunkMetadata(BaseModel):
    """Structured metadata for a code chunk.

    Attributes:
        file: POSIX-relative path from repository root.
        line: 1-based line number where the entity starts.
        chunk_type: Entity type (function, component, type).
        name: Identifier name (e.g., function/component/type name).
        exported: Whether the entity is directly exported.
        feature: Feature/module name extracted from directory structure.
        dependencies: List of imported module names from imports.json.
        language: Source language (typescript, tsx, javascript, jsx).
        truncated: Whether the text was truncated due to size limits.
        kind: Specific declaration form (function/arrow/method, interface/type, etc.).
        async_: For functions — whether declared with async keyword.
        params: For functions — parameter names list.
        props: For components — prop names list.
        members: For types — member names list.
    """

    file: str = Field(..., description="POSIX-relative file path")
    line: int = Field(..., description="1-based line number", ge=1)
    chunk_type: str = Field(..., description="Entity type: function, component, type")
    name: str = Field(..., description="Identifier name")
    exported: bool = Field(default=False, description="Directly exported from module")
    feature: str | None = Field(default=None, description="Feature/module name from path")
    dependencies: list[str] = Field(
        default_factory=list, description="Imported module names"
    )
    language: str = Field(default="typescript", description="Source language")
    truncated: bool = Field(default=False, description="Text was truncated")

    # Entity-specific fields (optional)
    kind: str | None = Field(default=None, description="Declaration form")
    async_: bool | None = Field(
        default=None, alias="async", description="Function is async"
    )
    params: list[str] | None = Field(default=None, description="Function parameters")
    props: list[str] | None = Field(default=None, description="Component props")
    members: list[str] | None = Field(default=None, description="Type members")

    model_config = {"populate_by_name": True}


class CodeChunk(BaseModel):
    """A code chunk ready for embedding and vector storage.

    Represents a single logical unit of code (function, component, or type)
    with its source text and rich metadata for semantic search.

    Attributes:
        id: Unique identifier in format "{file}:{type}:{name}:{line}".
        text: Source code text (may be truncated to max_chars).
        metadata: Structured metadata dict.
        embedding: Optional embedding vector (populated by embedding provider).
    """

    id: str = Field(..., description="Unique chunk identifier")
    text: str = Field(..., description="Source code text")
    metadata: ChunkMetadata = Field(..., description="Structured metadata")
    embedding: list[float] | None = Field(
        default=None, description="Embedding vector (optional)"
    )

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization.

        Returns:
            Dict with all fields, metadata as nested dict.
        """
        return {
            "id": self.id,
            "text": self.text,
            "metadata": self.metadata.model_dump(by_alias=True),
            "embedding": self.embedding,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CodeChunk:
        """Create CodeChunk from dict.

        Args:
            data: Dict with id, text, metadata, and optional embedding.

        Returns:
            CodeChunk instance.
        """
        return cls(
            id=data["id"],
            text=data["text"],
            metadata=ChunkMetadata(**data["metadata"]),
            embedding=data.get("embedding"),
        )


class SearchQuery(BaseModel):
    """Query parameters for semantic search.

    Attributes:
        text: Query text to search for.
        top_k: Maximum number of results to return.
        filters: Optional metadata filters (file_pattern, chunk_type, etc.).
        min_score: Minimum similarity score threshold (0.0 to 1.0).
        context_feature: Optional feature name for same-feature boosting.
    """

    text: str = Field(..., description="Query text", min_length=1)
    top_k: int = Field(default=10, description="Max results", ge=1, le=100)
    filters: dict[str, Any] = Field(
        default_factory=dict, description="Metadata filters"
    )
    min_score: float = Field(default=0.0, description="Min score threshold", ge=0.0, le=1.0)
    context_feature: str | None = Field(
        default=None, description="Feature name for boosting"
    )


class SearchResult(BaseModel):
    """Individual search result with score and chunk.

    Attributes:
        score: Similarity score (0.0 to 1.0, higher is better).
        chunk: The matched code chunk with metadata.
        explanation: Human-readable explanation of why it matched.
        adjusted_score: Score after re-ranking adjustments.
    """

    score: float = Field(..., description="Similarity score", ge=0.0, le=1.0)
    chunk: CodeChunk = Field(..., description="Matched code chunk")
    explanation: str = Field(default="High semantic similarity", description="Match reason")
    adjusted_score: float = Field(..., description="Re-ranked score", ge=0.0)

    def get_preview(self, max_lines: int = 3, max_chars_per_line: int = 120) -> str:
        """Extract preview from chunk text.

        Args:
            max_lines: Maximum number of lines to include.
            max_chars_per_line: Maximum characters per line.

        Returns:
            Preview string with first N non-empty lines.
        """
        lines = [line for line in self.chunk.text.split("\n") if line.strip()]
        preview_lines = lines[:max_lines]
        truncated = [
            line[:max_chars_per_line] + ("..." if len(line) > max_chars_per_line else "")
            for line in preview_lines
        ]
        return "\n".join(truncated)


@dataclass(frozen=True)
class SearchResponse:
    """Complete search response with metadata.

    Attributes:
        query: Original query text.
        total_found: Total number of results found.
        results: List of search results (ranked by score).
        execution_time_ms: Query execution time in milliseconds.
        filters_applied: Summary of filters that were applied.
        warnings: Any warnings generated during search.
    """

    query: str
    total_found: int
    results: list[SearchResult]
    execution_time_ms: float
    filters_applied: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
