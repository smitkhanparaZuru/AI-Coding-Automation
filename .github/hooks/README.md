# AICA Hooks

This directory contains lifecycle hooks that enforce AICA coding patterns and automate developer workflows.

## Overview

Hooks are deterministic shell scripts that run at specific points in the agent lifecycle. They can:

- **Block** operations that violate patterns
- **Warn** about potential issues
- **Inject** context into the agent session
- **Automate** validation and formatting

## Active Hooks

### 1. Session Start (`session-start.json`)

**Trigger**: Beginning of each agent session

**Purpose**: Provide AICA context and environment check

**What it does**:

- Displays Python, Ruff, and Pytest versions
- Shows quick command reference
- Lists active hooks
- Reminds about key AICA rules

**Script**: `scripts/session-start.ps1`

---

### 2. Pattern Validation (`validate-patterns.json`)

**Trigger**: Before any file modification tool use (PreToolUse)

**Purpose**: Prevent anti-patterns from being committed to AICA codebase

**What it validates**:

- ❌ **Errors** (requires approval):
  - Relative imports crossing packages (use absolute imports)
  - Hardcoded secrets/API keys (use Settings with SecretStr)

- ⚠️ **Warnings** (allows but notifies):
  - Using `print()` instead of `get_logger()`
  - Using stdlib logging instead of structlog
  - Missing `from __future__ import annotations`
  - Using `typing.List/Dict` instead of builtin generics

**Script**: `scripts/validate-patterns.ps1`

**Permission decisions**:

- `allow` - No errors detected (warnings shown as system message)
- `ask` - Errors detected (requires user approval to proceed)

---

### 3. Auto-Format (`auto-format.json`)

**Trigger**: After file modification tool use (PostToolUse)

**Purpose**: Automatically format Python files with Ruff after edits

**What it does**:

- Detects when Python files were modified
- Runs `ruff format` on those files
- Reports success/failure status
- Skips silently if Ruff is not installed

**Script**: `scripts/auto-format.ps1`

---

### 4. Session Stop (`session-stop.json`)

**Trigger**: End of agent session (Stop)

**Purpose**: Remind about pre-commit validation checklist

**What it displays**:

- Pre-commit checklist (pytest, ruff, mypy)
- Link to pre-release-checklist skill
- Quality gates before committing code

**Script**: `scripts/session-stop.ps1`

---

## Testing Hooks

### Test Pattern Validation

Try editing a Python file in `aica/` with anti-patterns:

```python
# This should trigger warnings/errors:
print("Hello")  # Warning: use get_logger()
import logging  # Warning: use structlog
from ...core.logging import get_logger  # Error: relative import crossing packages
api_key = "sk-1234567890abcdefghijklmnop"  # Error: hardcoded secret
```

### Test Auto-Format

Edit any Python file and check if Ruff auto-formats it after the edit completes.

### Test Session Start

Start a new agent session (reload window) and check for the environment context message.

---

## Hook Structure

Each hook consists of:

1. **JSON configuration** (`*.json`) - Defines which event(s) trigger the hook
2. **PowerShell script** (`scripts/*.ps1`) - The actual hook logic

### Configuration Format

```json
{
  "hooks": {
    "EventName": [
      {
        "type": "command",
        "command": "pwsh -NoProfile -ExecutionPolicy Bypass -File .github/hooks/scripts/script.ps1",
        "timeout": 30,
        "cwd": "${workspaceFolder}"
      }
    ]
  }
}
```

### Script Input/Output

**Input** (via stdin): JSON with hook event data

```json
{
  "toolName": "replace_string_in_file",
  "toolArguments": {
    "filePath": "aica/core/agent.py",
    "newString": "..."
  }
}
```

**Output** (via stdout): JSON response

```json
{
  "continue": true,
  "systemMessage": "✓ Validation passed",
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow"
  }
}
```

---

## Disabling Hooks

To temporarily disable a hook:

1. **Rename** the JSON file: `validate-patterns.json` → `validate-patterns.json.disabled`
2. Or **delete** the hook JSON file (keep the script for reference)

---

## Creating New Hooks

See the official hooks reference for complete details:
https://code.visualstudio.com/docs/copilot/customization/hooks

### Common patterns:

1. **PreToolUse** - Gate operations before they happen
2. **PostToolUse** - Automate validation/cleanup after operations
3. **SessionStart** - Inject context at session start
4. **Stop** - Session cleanup and reporting

---

## Troubleshooting

### Hook not running

- Check JSON syntax (use a JSON validator)
- Verify script path is correct
- Check script has execution permissions
- Look for errors in VS Code Output panel → GitHub Copilot

### Hook timing out

- Increase `timeout` value in JSON config
- Optimize script to run faster
- Consider if hook should be async

### Hook blocking incorrectly

- Review validation logic in the script
- Test with `pwsh .github/hooks/scripts/script.ps1` manually
- Check exit codes (0 = success, 2 = block, other = warning)

---

## Best Practices

1. **Keep hooks fast** - They run synchronously and block the agent
2. **Fail gracefully** - Missing tools (ruff, pytest) should warn, not block
3. **Clear messages** - Permission reasons should explain what's wrong
4. **Test thoroughly** - Run hooks manually before committing
5. **Document patterns** - Update this README when adding new hooks

---

## Related Documentation

- [Hooks Reference](https://code.visualstudio.com/docs/copilot/customization/hooks)
- [AICA Coding Guidelines](../copilot-instructions.md)
- [Agent Customization Docs](https://code.visualstudio.com/docs/copilot/customization/customization-overview)
