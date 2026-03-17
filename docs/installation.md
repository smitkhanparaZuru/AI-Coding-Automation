# Installation & Setup

---

## Requirements

| Requirement         | Version                       |
| ------------------- | ----------------------------- |
| Python              | 3.11 or 3.12                  |
| pip                 | Latest recommended            |
| Ollama _(optional)_ | Any — for local LLM inference |

---

## Install AICA

### Development install (editable)

Use this when working on AICA itself or running tests:

```bash
git clone <repo-url>
cd AI-Coding-Automation
pip install -e ".[dev]"
```

This installs AICA in editable mode plus all development dependencies:
`pytest`, `pytest-cov`, `ruff`, `mypy`.

### Production install

```bash
pip install .
```

### Verify the install

```bash
aica version
# aica 0.1.0

aica status
# Displays current config and loaded modules
```

---

## Configure the environment

AICA is configured entirely through environment variables with the `AICA_` prefix. The easiest way is via a `.env` file at the project root.

Copy the example file (if provided) or create `.env` from scratch:

```bash
cp .env.example .env   # if .env.example exists
# OR create manually:
touch .env
```

### Minimal `.env` for Ollama (local inference)

```env
AICA_LLM_PROVIDER=ollama
AICA_OLLAMA_MODEL=codellama
```

Pull the model first:

```bash
ollama pull codellama
```

### Minimal `.env` for OpenRouter (cloud)

```env
AICA_LLM_PROVIDER=openrouter
AICA_OPENROUTER_API_KEY=sk-or-v1-...
AICA_OPENROUTER_MODEL=openai/gpt-4o-mini
```

> **Security:** `AICA_OPENROUTER_API_KEY` is stored as a `SecretStr` and is never logged, even in debug mode.

---

## Setting up Ollama

1. Install Ollama from [https://ollama.com](https://ollama.com)
2. Start the Ollama daemon (it runs on `http://localhost:11434` by default)
3. Pull a model:
   ```bash
   ollama pull codellama         # code-focused model
   ollama pull llama3.2          # general-purpose
   ollama pull qwen2.5-coder     # alternative code model
   ```
4. Set in `.env`:
   ```env
   AICA_LLM_PROVIDER=ollama
   AICA_OLLAMA_MODEL=codellama
   ```

If Ollama runs on a non-default URL:

```env
AICA_OLLAMA_BASE_URL=http://192.168.1.100:11434
```

---

## Setting up OpenRouter

1. Create an account at [https://openrouter.ai](https://openrouter.ai)
2. Generate an API key in the dashboard
3. Set in `.env`:
   ```env
   AICA_LLM_PROVIDER=openrouter
   AICA_OPENROUTER_API_KEY=sk-or-v1-...
   AICA_OPENROUTER_MODEL=openai/gpt-4o-mini
   ```

Popular model identifiers:

| Model             | Identifier                    |
| ----------------- | ----------------------------- |
| GPT-4o Mini       | `openai/gpt-4o-mini`          |
| GPT-4o            | `openai/gpt-4o`               |
| Claude 3.5 Sonnet | `anthropic/claude-3-5-sonnet` |
| Gemini 2.0 Flash  | `google/gemini-2.0-flash-001` |
| DeepSeek Coder    | `deepseek/deepseek-coder`     |

---

## Verifying the setup

```bash
aica status
```

Expected output (example):

```
╭─ AICA Status ───────────────────────────╮
│ Version     0.1.0                        │
│ App Name    AICA                         │
│ Debug       False                        │
│ Log Level   INFO                         │
│ Workspace   .                            │
╰──────────────────────────────────────────╯

╭─ Modules ───────────────────────────────╮
│ core              ✓ loaded              │
│ repo_intelligence ✓ loaded              │
│ memory            ✓ loaded              │
│ tools             ✓ loaded              │
│ execution         ✓ loaded              │
│ interfaces        ✓ loaded              │
│ config            ✓ loaded              │
╰──────────────────────────────────────────╯
```

---

## Development workflow

```bash
# Lint
ruff check aica/

# Type check
mypy aica/

# Run tests
pytest tests/ -v

# Tests with coverage report
pytest tests/ --cov=aica --cov-report=term-missing
```

---

## Uninstall

```bash
pip uninstall aica-coding-automation
```
