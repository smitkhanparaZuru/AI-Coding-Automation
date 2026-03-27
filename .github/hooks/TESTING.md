# Hook Testing Guide

Quick guide to test each AICA hook locally.

## Prerequisites

```powershell
# Ensure PowerShell can execute scripts
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Install dependencies
pip install ruff pytest mypy
```

---

## Test 1: Session Start Hook

**What it tests**: Environment check and context injection

**How to test**:

```powershell
# Run the script directly
pwsh .github/hooks/scripts/session-start.ps1

# Expected output: JSON with systemMessage containing environment info
```

**What to verify**:

- ✓ Python version detected
- ✓ Ruff version detected (or warning if not installed)
- ✓ Quick commands list displayed
- ✓ Key AICA rules reminder shown

---

## Test 2: Pattern Validation Hook (PreToolUse)

**What it tests**: Anti-pattern detection before file edits

**How to test**:

Create a test input file `test-input.json`:

```json
{
  "toolName": "replace_string_in_file",
  "toolArguments": {
    "filePath": "aica/core/test.py",
    "newString": "print('Hello')\nimport logging\nfrom ...core.logging import get_logger\napi_key = 'sk-1234567890abcdefghijklmnop'"
  }
}
```

Run the hook:

```powershell
Get-Content test-input.json | pwsh .github/hooks/scripts/validate-patterns.ps1
```

**What to verify**:

- ✓ Detects `print()` usage (warning)
- ✓ Detects stdlib `logging` usage (warning)
- ✓ Detects relative imports crossing packages (error → `permissionDecision: "ask"`)
- ✓ Detects hardcoded secrets (error → `permissionDecision: "ask"`)

**Expected output**:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "ask",
    "permissionDecisionReason": "AICA Pattern Validation:\n❌ Relative import crossing packages..."
  }
}
```

---

## Test 3: Auto-Format Hook (PostToolUse)

**What it tests**: Automatic formatting after file edits

**How to test**:

1. Create a poorly formatted test file:

```powershell
# Create test file with bad formatting
@"
def bad_function(x,y,z):
    result=x+y+z
    return result
"@ | Out-File -FilePath test_format.py -Encoding utf8
```

2. Create test input:

```json
{
  "toolName": "replace_string_in_file",
  "toolArguments": {
    "filePath": "test_format.py"
  }
}
```

3. Run the hook:

```powershell
Get-Content test-input.json | pwsh .github/hooks/scripts/auto-format.ps1
```

4. Check if `test_format.py` was formatted:

```powershell
Get-Content test_format.py
```

**What to verify**:

- ✓ File is formatted with proper spacing
- ✓ Hook returns success message
- ✓ If ruff not installed, shows warning but continues

---

## Test 4: Session Stop Hook

**What it tests**: Pre-commit checklist reminder

**How to test**:

```powershell
pwsh .github/hooks/scripts/session-stop.ps1
```

**What to verify**:

- ✓ Displays pre-commit checklist
- ✓ Lists all validation commands
- ✓ References pre-release-checklist skill

---

## Integration Testing

Test hooks in real VS Code Copilot sessions:

### Test SessionStart

1. Close and reopen VS Code
2. Start a new Copilot chat
3. Check for environment context message

### Test PreToolUse Validation

1. Ask Copilot to edit a file in `aica/` with anti-patterns:
   ```
   Edit aica/core/test.py and add a print statement
   ```
2. Verify hook blocks or warns before edit

### Test PostToolUse Format

1. Ask Copilot to edit any Python file
2. After edit completes, check if file was auto-formatted
3. Look for "✓ Auto-formatted: ..." message

### Test SessionStop

1. End a Copilot session
2. Check for pre-commit checklist reminder

---

## Troubleshooting

### Hook not running in VS Code

**Check JSON syntax**:

```powershell
Get-Content .github/hooks/auto-format.json | ConvertFrom-Json
```

**Check VS Code Output panel**:

- Open: View → Output
- Select: GitHub Copilot
- Look for hook execution logs

### Script exits with error

**Test script manually**:

```powershell
# Set verbose error mode
$ErrorActionPreference = "Stop"
pwsh .github/hooks/scripts/validate-patterns.ps1
```

**Check exit code**:

```powershell
pwsh .github/hooks/scripts/session-start.ps1
Write-Host "Exit code: $LASTEXITCODE"
# 0 = success, 2 = block, other = warning
```

### Permission denied errors

**Windows**: Allow script execution

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Verify script can run**:

```powershell
Get-ExecutionPolicy -List
```

---

## Common Test Patterns

### Test with different tool arguments

```json
{
  "toolName": "multi_replace_string_in_file",
  "toolArguments": {
    "replacements": [
      {"filePath": "aica/core/agent.py", "newString": "..."},
      {"filePath": "aica/core/planner.py", "newString": "..."}
    ]
  }
}
```

### Test with non-Python files (should be ignored)

```json
{
  "toolName": "replace_string_in_file",
  "toolArguments": {
    "filePath": "README.md",
    "newString": "Some markdown content"
  }
}
```

### Test with files outside aica/ (should be ignored by validation)

```json
{
  "toolName": "replace_string_in_file",
  "toolArguments": {
    "filePath": "tests/test_something.py",
    "newString": "print('This is okay in tests')"
  }
}
```

---

## Performance Testing

Measure hook execution time:

```powershell
Measure-Command {
  pwsh .github/hooks/scripts/validate-patterns.ps1
}
```

**Target**: < 5 seconds for PreToolUse hooks, < 1 second for SessionStart/Stop

---

## Cleanup

Remove test files after testing:

```powershell
Remove-Item test-input.json -ErrorAction SilentlyContinue
Remove-Item test_format.py -ErrorAction SilentlyContinue
```
