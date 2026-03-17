# Plan: Task 1.3 — Configuration System

## TL;DR

Extend `aica/config/settings.py` with 6 new Pydantic `BaseSettings` fields (LLM, OPENROUTER_API_KEY as SecretStr, two DB URLs, and REPO_PATH). Update `.env.example` to document all new vars. No other files need changes — `aica/config/__init__.py` already exports the right symbols and `pydantic-settings` is already a declared dependency.

---

## Decisions

- `LLM_PROVIDER`: `Literal["ollama", "openrouter"]`, default `"ollama"`
- `OPENROUTER_API_KEY`: `pydantic.SecretStr | None`, default `None` (masks in logs/repr)
- `VECTOR_DB_URL`: default `"http://localhost:8000"` (ChromaDB)
- `GRAPH_DB_URL`: default `"bolt://localhost:7687"` (Neo4j)
- `REPO_PATH`: separate `Path` field from existing `workspace_dir`, default `Path(".")`
- All env vars automatically prefixed with `AICA_` (existing `env_prefix="AICA_"`)

---

## Steps

### Phase 1: Update Settings Model

1. `aica/config/settings.py`
   - Add `SecretStr` to the `pydantic` import line (Field is already imported)
   - Add 6 new fields to `Settings` class, grouped under a `# LLM`, `# Databases`, `# Repository` comment block:
     - `llm_provider: Literal["ollama", "openrouter"] = Field(default="ollama", ...)`
     - `ollama_base_url: str = Field(default="http://localhost:11434", ...)`
     - `openrouter_api_key: SecretStr | None = Field(default=None, ...)`
     - `vector_db_url: str = Field(default="http://localhost:8000", ...)`
     - `graph_db_url: str = Field(default="bolt://localhost:7687", ...)`
     - `repo_path: Path = Field(default=Path("."), ...)`

### Phase 2: Update .env.example

2. `.env.example` — append new env var sections for LLM, databases, and repo path with inline comments

---

## Relevant Files

- `aica/config/settings.py` — main change target; uses pydantic v2 `BaseSettings` + `SettingsConfigDict`
- `.env.example` — documentation for env var usage
- `aica/config/__init__.py` — NO change needed (already re-exports `Settings`, `get_settings`)
- `pyproject.toml` — NO change needed (`pydantic>=2.5`, `pydantic-settings>=2.1` already declared)

---

## Verification

1. `python -c "from aica.config import get_settings; s = get_settings(); print(s.llm_provider, s.repo_path)"` — should print `ollama .`
2. Set `AICA_LLM_PROVIDER=openrouter` and re-run — should print `openrouter .`
3. Set `AICA_LLM_PROVIDER=invalid` — should raise a Pydantic `ValidationError`
4. Set `AICA_OPENROUTER_API_KEY=secret123` and call `s.openrouter_api_key.get_secret_value()` — should return the raw string while `str(s.openrouter_api_key)` masks it
5. `python -m pytest tests/ -q` — all existing tests pass

---

## Scope Exclusions

- No validator logic (e.g., "if provider=openrouter then api_key must be set") — out of scope for 1.3
- No CLI flags wiring for new settings — separate task
- No changes to `aica/config/__init__.py`
