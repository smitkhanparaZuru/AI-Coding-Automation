# AICA Hooks - Architecture Diagram

## Hook Lifecycle Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     COPILOT SESSION LIFECYCLE                    │
└─────────────────────────────────────────────────────────────────┘

1. SESSION START
   │
   ├─► session-start.json
   │   └─► scripts/session-start.ps1
   │       ├─ Check Python environment
   │       ├─ Check Ruff availability
   │       ├─ Check Pytest availability
   │       └─ Display AICA context & quick commands
   │
   └─► User sees environment info message
       ────────────────────────────────────────────────────────────

2. USER PROMPT
   │
   └─► "Edit aica/core/agent.py and add logging"
       ────────────────────────────────────────────────────────────

3. PRE-TOOL USE (Before file modification)
   │
   ├─► validate-patterns.json
   │   └─► scripts/validate-patterns.ps1
   │       ├─ Parse tool arguments (file path, new content)
   │       ├─ Check for anti-patterns:
   │       │   • print() statements (warning)
   │       │   • stdlib logging (warning)
   │       │   • Relative imports crossing packages (error)
   │       │   • Hardcoded secrets (error)
   │       │   • Missing __future__ annotations (warning)
   │       │   • typing.List instead of list (warning)
   │       ├─ Return permission decision:
   │       │   • "allow" - no errors (warnings shown)
   │       │   • "ask" - errors found (user approval required)
   │
   ├─► IF errors found:
   │   └─► User prompted: "❌ Relative import crossing packages..."
   │       ├─ User approves → Continue
   │       └─ User denies → Block operation
   │
   └─► IF no errors or user approved:
       └─► Continue to tool execution
       ────────────────────────────────────────────────────────────

4. TOOL EXECUTION
   │
   └─► replace_string_in_file executes
       └─► File modified on disk
       ────────────────────────────────────────────────────────────

5. POST-TOOL USE (After file modification)
   │
   ├─► auto-format.json
   │   └─► scripts/auto-format.ps1
   │       ├─ Parse tool arguments (file paths)
   │       ├─ Filter to Python files only
   │       ├─ Check if Ruff is installed
   │       ├─ Run "ruff format <file>" on each
   │       └─ Report results:
   │           • "✓ Auto-formatted: file.py"
   │           • "⚠️ Format failed: file.py"
   │
   └─► User sees formatting confirmation message
       ────────────────────────────────────────────────────────────

6. SESSION END
   │
   ├─► session-stop.json
   │   └─► scripts/session-stop.ps1
   │       └─ Display pre-commit checklist:
   │           • pytest tests/ -v
   │           • ruff check aica/
   │           • ruff format aica/
   │           • mypy aica/
   │
   └─► User sees checklist reminder
```

## Hook Input/Output Contract

### PreToolUse Example

**Input (stdin)**:

```json
{
  "toolName": "replace_string_in_file",
  "toolArguments": {
    "filePath": "aica/core/agent.py",
    "oldString": "...",
    "newString": "print('Debug')\nfrom ...logging import get_logger"
  }
}
```

**Output (stdout)** - Errors found:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "ask",
    "permissionDecisionReason": "❌ Relative import crossing packages detected\n🚫 Found print() statement"
  }
}
```

**Output (stdout)** - Warnings only:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow"
  },
  "systemMessage": "⚠️ Found print() statement - use get_logger()"
}
```

### PostToolUse Example

**Input (stdin)**:

```json
{
  "toolName": "multi_replace_string_in_file",
  "toolArguments": {
    "replacements": [
      {"filePath": "aica/core/agent.py"},
      {"filePath": "aica/core/planner.py"}
    ]
  }
}
```

**Output (stdout)**:

```json
{
  "continue": true,
  "systemMessage": "✓ Auto-formatted: agent.py, planner.py"
}
```

## Validation Rules Matrix

| Pattern                   | Detection                                               | Severity  | Action         |
| ------------------------- | ------------------------------------------------------- | --------- | -------------- |
| `print(...)`              | Regex: `\bprint\s*\(`                                   | Warning   | Allow + notify |
| `logging.info(...)`       | Regex: `\blogging\.(info\|debug\|...)`                  | Warning   | Allow + notify |
| Missing `from __future__` | First line check                                        | Warning   | Allow + notify |
| `typing.List`             | Regex: `\btyping\.(List\|Dict\|...)`                    | Warning   | Allow + notify |
| `from ...module`          | Regex: `from \.\.\.[^\s]+ import`                       | **Error** | Ask user       |
| `api_key = "sk-..."`      | Regex: `(api_key\|secret\|password).*=.*["'][^"']{20,}` | **Error** | Ask user       |

## File Targeting

### Pattern Validation Hook

**Applies to**: Only Python files in `aica/` directory

```
✓ aica/core/agent.py
✓ aica/repo_intelligence/scanner/scanner.py
✗ tests/test_agent.py (tests excluded)
✗ docs/example.py (docs excluded)
✗ README.md (non-Python)
```

### Auto-Format Hook

**Applies to**: All modified Python files

```
✓ aica/core/agent.py
✓ tests/test_agent.py
✓ docs/example.py
✗ README.md (non-Python)
✗ pyproject.toml (non-Python)
```

## Exit Codes

| Code  | Meaning              | Hook Behavior                 |
| ----- | -------------------- | ----------------------------- |
| 0     | Success              | Continue normally             |
| 2     | Blocking error       | Stop operation, show error    |
| Other | Non-blocking warning | Continue with warning message |

## Performance Budgets

| Hook              | Event        | Target Time | Timeout |
| ----------------- | ------------ | ----------- | ------- |
| session-start     | SessionStart | < 1s        | 10s     |
| validate-patterns | PreToolUse   | < 3s        | 15s     |
| auto-format       | PostToolUse  | < 5s        | 30s     |
| session-stop      | Stop         | < 1s        | 5s      |

## Customization Points

### Adding New Validation Rules

Edit `scripts/validate-patterns.ps1`:

```powershell
# Add new check after line 60
if ($newContent -match '\bYOUR_PATTERN\b') {
    $warnings += "⚠️ Your custom warning message"
}

# Or add as error
if ($newContent -match '\bDANGEROUS_PATTERN\b') {
    $errors += "❌ Your custom error message"
}
```

### Adjusting Formatting Behavior

Edit `scripts/auto-format.ps1`:

```powershell
# Add additional formatting tools
ruff format "$file"
black "$file"  # Add Black formatter
isort "$file"  # Add import sorter
```

### Changing Session Context

Edit `scripts/session-start.ps1` to include project-specific context:

```powershell
# Add custom checks
$messages += "📊 Current branch: $(git branch --show-current)"
$messages += "🔄 Uncommitted changes: $(git status --short | Measure-Object).Count"
```

## Troubleshooting Decision Tree

```
Hook not running?
├─► Check JSON syntax
│   └─► Fix: Get-Content hook.json | ConvertFrom-Json
│
├─► Check VS Code Output panel
│   └─► View → Output → GitHub Copilot
│
└─► Check execution policy
    └─► Fix: Set-ExecutionPolicy RemoteSigned -Scope CurrentUser

Hook blocking incorrectly?
├─► Review validation logic
│   └─► Edit: scripts/validate-patterns.ps1
│
├─► Test manually
│   └─► pwsh scripts/validate-patterns.ps1
│
└─► Temporarily disable
    └─► Rename: hook.json → hook.json.disabled

Script execution errors?
├─► Run with error details
│   └─► $ErrorActionPreference = "Stop"; pwsh script.ps1
│
├─► Check dependencies
│   └─► Get-Command ruff, pytest, python
│
└─► Verify file paths
    └─► Test-Path .github/hooks/scripts/script.ps1
```
