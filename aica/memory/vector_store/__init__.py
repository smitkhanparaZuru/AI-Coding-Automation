from __future__ import annotations

from aica.memory.vector_store.chunkers import (
    chunk_components,
    chunk_functions,
    chunk_types,
    create_code_chunks,
)
from aica.memory.vector_store.embedding_provider import (
    BaseEmbeddingProvider,
    OllamaEmbeddingProvider,
    OpenRouterEmbeddingProvider,
)
from aica.memory.vector_store.exceptions import (
    VectorStoreAuthError,
    VectorStoreConnectionError,
    VectorStoreError,
    VectorStoreQueryError,
    VectorStoreRateLimitError,
    VectorStoreTimeoutError,
)
from aica.memory.vector_store.factory import EmbeddingProvider
from aica.memory.vector_store.incremental_updater import (
    EmbeddingUpdateSummary,
    update_embeddings_for_files,
)
from aica.memory.vector_store.indexing_pipeline import IndexingSummary, index_codebase
from aica.memory.vector_store.qdrant_client import QdrantClient
from aica.memory.vector_store.retriever import (
    build_context_from_results,
    build_qdrant_filter,
    format_search_results,
    search_code,
)
from aica.memory.vector_store.schemas import (
    ChunkMetadata,
    CodeChunk,
    SearchQuery,
    SearchResponse,
    SearchResult,
)
from aica.memory.vector_store.utils import (
    extract_source_lines,
    infer_feature,
    truncate_text,
)

__all__ = [
    "BaseEmbeddingProvider",
    "ChunkMetadata",
    "CodeChunk",
    "EmbeddingProvider",
    "EmbeddingUpdateSummary",
    "IndexingSummary",
    "OllamaEmbeddingProvider",
    "OpenRouterEmbeddingProvider",
    "QdrantClient",
    "SearchQuery",
    "SearchResponse",
    "SearchResult",
    "VectorStoreAuthError",
    "VectorStoreConnectionError",
    "VectorStoreError",
    "VectorStoreQueryError",
    "VectorStoreRateLimitError",
    "VectorStoreTimeoutError",
    "build_context_from_results",
    "build_qdrant_filter",
    "chunk_components",
    "chunk_functions",
    "chunk_types",
    "create_code_chunks",
    "extract_source_lines",
    "format_search_results",
    "infer_feature",
    "index_codebase",
    "search_code",
    "truncate_text",
    "update_embeddings_for_files",
]
