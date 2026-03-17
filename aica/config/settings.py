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

    # Repository
    repo_path: Path = Field(
        default=Path("."), description="Root path of the repository to analyse"
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
