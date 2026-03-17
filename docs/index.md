# AICA — AI Coding Automation Engine

**Version:** 0.1.0 · **Python:** 3.11+

AICA is a local, CLI-first AI coding automation engine. It orchestrates AI agents to plan, analyse, and execute coding tasks against a local workspace, backed by your choice of LLM provider (Ollama for local inference or OpenRouter for cloud models).

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Documentation Pages](#documentation-pages)

---

## Overview

| Capability            | Description                                                                                                                                                                                                                      |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Repo Intelligence** | Deep-scan Next.js / Python repos — 17 detectors covering routes, components, services, database, packages, Zustand stores, tRPC routers, i18n, auth providers, server modules, LLM providers, env vars, hooks, scripts, and libs |
| **LLM Integration**   | Pluggable provider facade (Ollama & OpenRouter) with retry, streaming, and async APIs                                                                                                                                            |
| **Task Planning**     | Structured multi-step execution plans for coding tasks                                                                                                                                                                           |
| **Code Execution**    | Safe subprocess wrapper with captured output and timeout support                                                                                                                                                                 |
| **Extensible Agents** | `BaseAgent` ABC dispatched by an `Orchestrator` registry                                                                                                                                                                         |
| **Pluggable Memory**  | Swappable `MemoryStore` backends (in-memory by default)                                                                                                                                                                          |
| **Rich CLI**          | 8 commands with beautiful `rich` tables and panels                                                                                                                                                                               |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          CLI (Typer)                            │
│  status · version · scan-repo · scan-next · summarize-repo      │
│  index-code · plan-task · run-task                              │
└────────────────────────────┬────────────────────────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
    ┌─────▼──────┐   ┌───────▼──────┐  ┌───────▼──────┐
    │  LLM Layer │   │  Repo Intel  │  │  Execution   │
    │            │   │              │  │              │
    │  Ollama    │   │  Scanner     │  │  Runner      │
    │  OpenRouter│   │  Detectors ×17│ │  Terminal    │
    │  (factory) │   │  Summarizer  │  │  Runner      │
    └─────┬──────┘   └───────┬──────┘  └──────────────┘
          │                  │
    ┌─────▼──────┐   ┌───────▼──────┐
    │   Agents   │   │  .repo_intel │
    │            │   │  *.json      │
    │  BaseAgent │   └──────────────┘
    │  Orchestrat│
    └────────────┘
          │
    ┌─────▼──────┐   ┌──────────────┐
    │   Memory   │   │    Tools     │
    │ MemoryStore│   │  BaseTool    │
    └────────────┘   └──────────────┘
```

**Data flow for `aica scan-next`:**

```
CLI → RepositoryScanner.scan(path)
        ├── FrameworkDetector      → framework, language, next_version
        ├── StructureDetector      → src dirs, config files
        ├── RouteDetector          → routes list
        ├── ComponentDetector      → components list
        ├── ServiceDetector        → services list
        ├── DatabaseDetector       → ORM, schema, models
        ├── PackageDetector        → categorised packages
        ├── ZustandStoreDetector   → stores, slices, middleware
        ├── TRPCRouterDetector     → tRPC routers, procedures
        ├── I18nDetector           → locales, namespaces
        ├── AuthDetector           → providers, session strategy
        ├── ServerModulesDetector  → server module inventory
        ├── AgentRuntimeDetector   → LLM providers, SSO providers
        ├── EnvVarsDetector        → env var categories
        ├── HooksDetector          → custom React hooks
        ├── ScriptsDetector        → automation scripts
        └── LibsDetector           → integration libraries
            │
            ▼
      OutputWriter → .repo_intelligence/*.json  (15 files + repo_summary.json)
            │
            ▼
    RepoSummaryGenerator → repo_summary.json
```

---

## Quick Start

### 1. Install

```bash
pip install -e ".[dev]"   # development (editable)
# OR
pip install .              # production
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env` — choose your LLM backend:

**Ollama (local):**

```env
AICA_LLM_PROVIDER=ollama
AICA_OLLAMA_MODEL=codellama
```

**OpenRouter (cloud):**

```env
AICA_LLM_PROVIDER=openrouter
AICA_OPENROUTER_API_KEY=sk-or-...
AICA_OPENROUTER_MODEL=openai/gpt-4o-mini
```

### 3. Verify

```bash
aica status
```

### 4. Scan a repo

```bash
# Deep-scan any repository
aica scan-repo --path /path/to/your/repo

# Verbose Next.js App Router scan with rich tables
aica scan-next --path /path/to/nextjs-repo
```

Outputs are written to `.repo_intelligence/` inside the target repo:

```
.repo_intelligence/
  structure.json        ← full merged scan result
  routes.json
  components.json
  services.json
  database.json
  packages.json
  stores.json
  trpc_routers.json
  i18n.json
  auth.json
  server_modules.json
  agent_runtime.json
  env_vars.json
  hooks.json
  scripts.json
  libs.json
  repo_summary.json     ← high-level counts summary
```

### 5. Plan and execute tasks

```bash
# Generate a structured execution plan
aica plan-task "Refactor auth module to use JWT"

# Run a shell command with captured output
aica run-task "pytest tests/ -v" --cwd /path/to/project
```

---

## Documentation Pages

| Page                              | Description                                               |
| --------------------------------- | --------------------------------------------------------- |
| [Installation](installation.md)   | Requirements, install options, `.env` setup               |
| [Configuration](configuration.md) | Full `AICA_*` env var reference, provider setup           |
| [CLI Reference](cli.md)           | All 8 commands with options, arguments, examples          |
| [Developer Guide](extending.md)   | Extend with new agents, providers, tools, memory backends |
| [API Reference](api-reference.md) | Public class and method signatures                        |
