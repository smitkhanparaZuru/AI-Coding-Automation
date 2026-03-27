# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] - 2026-03-27

### Initial Release

**AICA (AI Coding Automation Engine)** — Local, CLI-first AI coding automation platform for analyzing and understanding codebases with LLM integration and graph database support.

### Added

#### Core Features

- **Dual LLM Backend Support**
  - Ollama provider for local inference with streaming support
  - OpenRouter provider for cloud-based models (200+ models)
  - Pluggable `LLMProvider` facade with sync, async, streaming, and async-streaming APIs
  - Exponential backoff retry logic for transient errors (connection, timeout, rate limit)
  - Error hierarchy: `LLMConnectionError`, `LLMAuthError`, `LLMRateLimitError`, `LLMTimeoutError`

- **Repository Intelligence System**
  - **17 Detectors** for comprehensive Next.js codebase analysis:
    - Framework Detection (Next.js version, App Router, package manager)
    - Structure Detection (source directories, config files)
    - Route Detection (pages, API routes, dynamic routes, parallel routes)
    - Component Detection (React components with props inference)
    - Service Detection (exported utilities and services)
    - Database Detection (Prisma, Drizzle, TypeORM schemas)
    - Package Detection (categorized npm dependencies)
    - Zustand Store Detection (stores, slices, middleware)
    - tRPC Router Detection (lambda/async/edge routers with procedures)
    - i18n Detection (locales, namespaces)
    - Auth Detection (Clerk, NextAuth, Auth0, session strategies)
    - Server Modules Detection (server-side module inventory)
    - Agent Runtime Detection (LLM providers, SSO providers)
    - Environment Variables Detection (categorized by type)
    - Hooks Detection (custom React hooks)
    - Scripts Detection (automation scripts)
    - Libraries Detection (integration SDKs)
  - JSON output to `.repo_intelligence/` directory with 16 artifact files

- **TypeScript/TSX AST Extraction**
  - **7 AST Extractors** powered by tree-sitter:
    - Import statements (external, alias, relative, type-only)
    - Function definitions (functions, arrows, methods, generators, async)
    - Export statements (named, default, re-export, namespace-reexport)
    - Call expressions (function calls, new expressions, method calls)
    - React hooks (custom and built-in, with caller context)
    - React components (function, arrow, class, with props)
    - TypeScript types (interfaces, type aliases, with members)
  - Call graph builder (per-file grouped structure)
  - JSON output to `.repo_intelligence/ast/` directory with 7 artifact files

- **Neo4j Dependency Graph**
  - Build queryable knowledge graph from AST and scanner artifacts
  - **9 Node Types:** File, Function, Component, Hook, Type, Module, Route, Service, Store
  - **8 Relationship Types:** IMPORTS, DEFINES, CALLS, USES_HOOK, HAS_ROUTE, HAS_STORE, BELONGS_TO, EXPORTS
  - 7 uniqueness constraints for data integrity
  - Batch operations (500 nodes/edges per transaction)
  - Idempotent MERGE semantics for re-runs
  - GraphSummary result with node/edge counts
  - Support for local Docker, Neo4j Desktop, and Neo4j Aura

- **CLI Commands (8 total)**
  - `aica status` — Display configuration and module status
  - `aica version` — Print installed version
  - `aica scan-repo [--path PATH] [--verbose]` — Deep-scan repository with all 17 detectors
  - `aica index-code [--path PATH]` — Extract AST data with tree-sitter
  - `aica summarize-repo [--path PATH]` — Regenerate summary from existing artifacts
  - `aica build-graph [--path PATH]` — Build Neo4j dependency graph
  - `aica plan-task TASK` — Generate 5-step execution plan (deterministic in v0.1.0)
  - `aica run-task COMMAND [--cwd CWD]` — Execute shell command with captured output

- **Configuration System**
  - Pydantic Settings v2 with layered configuration (env vars → `.env` → defaults)
  - All settings use `AICA_` prefix
  - Nested delimiter support (`__`)
  - `SecretStr` masking for API keys and passwords
  - 25+ environment variables for fine-grained control

- **Execution & Memory**
  - `ExecutionRunner` — Safe subprocess wrapper with `RunResult` dataclass
  - `TerminalRunner` — Command execution with timeout support
  - `MemoryStore` ABC — Pluggable memory backends
  - `InMemoryStore` — Dict-backed in-memory implementation

- **Extensibility**
  - `BaseAgent` ABC — Custom agent framework
  - `Orchestrator` — Agent registry and dispatcher
  - `BaseTool` ABC — Extensible tool system
  - `BaseLLMProvider` ABC — Custom LLM provider interface

- **Logging & Error Handling**
  - Structured logging via `structlog`
  - JSON output in production, console in debug mode
  - Error hierarchy with retry-aware exception types
  - Never logs sensitive data (`SecretStr` fields masked)

#### Documentation

- **Installation Guide** (`docs/installation.md`)
- **Configuration Reference** (`docs/configuration.md`)
- **CLI Reference** (`docs/cli.md`) — All 8 commands with examples
- **Neo4j Graph Guide** (`docs/neo4j-graph.md`) — Comprehensive graph schema, setup, and 10+ query examples
- **Tutorials** (`docs/tutorials.md`) — 3 step-by-step guides:
  - Quick Start (5 minutes)
  - Deep Dive (20 minutes, Ollama-based)
  - Cloud Setup (15 minutes, OpenRouter + Neo4j Aura)
- **API Reference** (`docs/api-reference.md`) — Public class signatures with usage examples
- **Developer Guide** (`docs/extending.md`) — Add agents, providers, tools, detectors
- **Troubleshooting Guide** (`docs/troubleshooting.md`) — Common issues and solutions
- **Contributing Guide** (`CONTRIBUTING.md`) — Development setup, testing, PR process
- **Code of Conduct** (`CODE_OF_CONDUCT.md`) — Contributor Covenant 2.1

#### Testing

- 40+ test files with pytest
- Coverage: Scanner detectors, AST extractors, LLM providers, CLI commands
- Mock-based testing (no live LLM/Neo4j required)
- Type checking with mypy
- Linting and formatting with ruff

---

## [Unreleased]

### Planned for v0.2.0

- LLM-driven task planning (replace deterministic 5-step plans)
- Vector memory integration (ChromaDB)
- Incremental graph updates (only changed files)
- Agent execution framework (run plans automatically)
- GitHub Actions integration templates
- CI/CD analysis reports
- Web UI for graph visualization
- Python AST extraction (in addition to TypeScript)
- Support for Vue.js, Nuxt, SvelteKit frameworks

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## License

[MIT](LICENSE)

---

[0.1.0]: https://github.com/your-org/AI-Coding-Automation/releases/tag/v0.1.0
