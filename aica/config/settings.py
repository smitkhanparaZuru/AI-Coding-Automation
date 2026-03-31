from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AICA_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="AICA", description="Application display name")
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Log level"
    )
    workspace_dir: Path = Field(
        default=Path("."), description="AICA working directory"
    )

    # LLM
    llm_provider: Literal["ollama", "openrouter"] = Field(
        default="ollama", description="LLM backend provider"
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434", description="Ollama API base URL"
    )
    ollama_model: str = Field(
        default="", description="Ollama model name (e.g. llama3.2) — set via AICA_OLLAMA_MODEL"
    )
    openrouter_api_key: SecretStr | None = Field(
        default=None, description="OpenRouter API key (masked in logs)"
    )
    openrouter_model: str = Field(
        default="",
        description="OpenRouter model name (e.g. openai/gpt-4o-mini) — set via AICA_OPENROUTER_MODEL",
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1", description="OpenRouter API base URL"
    )
    llm_timeout: int = Field(default=60, description="LLM request timeout in seconds")
    llm_max_retries: int = Field(default=3, description="Max retry attempts on transient errors")
    llm_retry_min_wait: float = Field(
        default=1.0, description="Minimum wait between retries (seconds)"
    )
    llm_retry_max_wait: float = Field(
        default=10.0, description="Maximum wait between retries (seconds)"
    )

    # Databases
    vector_db_url: str = Field(
        default="http://localhost:8000", description="Vector database URL (e.g. ChromaDB)"
    )
    graph_db_url: str = Field(
        default="bolt://localhost:7687", description="Graph database URL (e.g. Neo4j)"
    )

    # Neo4j
    neo4j_uri: str = Field(
        default="bolt://localhost:7687",
        description="Neo4j connection URI (bolt:// for local Docker, neo4j+s:// for AuraDB)",
    )
    neo4j_user: str = Field(default="neo4j", description="Neo4j username")
    neo4j_password: SecretStr = Field(
        default=SecretStr(""),
        description="Neo4j password (masked in logs) — set via AICA_NEO4J_PASSWORD",
    )
    neo4j_database: str = Field(default="neo4j", description="Neo4j target database")

    # Vector Store (Qdrant)
    qdrant_url: str = Field(
        default="http://localhost:6333",
        description="Qdrant server URL",
    )
    qdrant_api_key: SecretStr | None = Field(
        default=None,
        description="Qdrant API key (optional, masked in logs) — set via AICA_QDRANT_API_KEY",
    )
    qdrant_collection_name: str = Field(
        default="aica-code",
        description="Qdrant collection name for code embeddings",
    )
    qdrant_vector_dimension: int | None = Field(
        default=None,
        description="Vector dimension (auto-detect from embedding model if None)",
    )
    qdrant_batch_size: int = Field(
        default=500,
        description="Batch size for vector upsert operations",
    )

    # Embedding Provider
    embedding_provider: Literal["ollama", "openrouter"] = Field(
        default="ollama",
        description="Embedding provider backend",
    )
    embedding_model: str = Field(
        default="nomic-embed-text",
        description="Embedding model name (e.g. nomic-embed-text for Ollama, openai/text-embedding-3-small for OpenRouter)",
    )
    embedding_batch_size: int = Field(
        default=32,
        description="Batch size for embedding generation",
    )
    embedding_timeout: int = Field(
        default=60,
        description="Embedding request timeout in seconds",
    )
    embedding_max_retries: int = Field(
        default=3,
        description="Max retry attempts on transient errors",
    )
    embedding_retry_min_wait: float = Field(
        default=1.0,
        description="Minimum wait between retries (seconds)",
    )
    embedding_retry_max_wait: float = Field(
        default=10.0,
        description="Maximum wait between retries (seconds)",
    )
    embedding_ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama API base URL for embeddings",
    )
    embedding_openrouter_api_key: SecretStr | None = Field(
        default=None,
        description="OpenRouter API key for embeddings (masked in logs) — set via AICA_EMBEDDING_OPENROUTER_API_KEY",
    )
    embedding_openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="OpenRouter API base URL for embeddings",
    )

    # Repository
    repo_path: Path = Field(
        default=Path("."), description="Root path of the repository to analyse"
    )

    # Sync
    sync_fallback_threshold: float = Field(
        default=0.20,
        ge=0.0,
        le=1.0,
        description="Fallback to full sync when changed TS/TSX files exceed this percentage",
    )
    sync_max_ast_age_seconds: int = Field(
        default=259200,
        ge=0,
        description="Maximum allowed age for AST artifacts before incremental graph update (0 disables)",
    )
    sync_update_embeddings: bool = Field(
        default=True,
        description="Auto-update embeddings during repository sync (set to False to skip)",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
