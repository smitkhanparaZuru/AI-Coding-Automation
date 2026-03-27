# AICA Hooks - Quick Start

⚡ **Hooks are now active!** They will automatically run during your Copilot sessions.

## What Just Happened?

Four lifecycle hooks have been installed to enforce AICA patterns and automate workflows:

| Hook                  | Event            | What It Does                                                 |
| --------------------- | ---------------- | ------------------------------------------------------------ |
| **session-start**     | Session begins   | Shows environment check & AICA context                       |
| **validate-patterns** | Before file edit | Blocks anti-patterns (print, hardcoded secrets, bad imports) |
| **auto-format**       | After file edit  | Runs `ruff format` on modified Python files                  |
| **session-stop**      | Session ends     | Displays pre-commit checklist                                |

## Next Steps

### 1. Test the Hooks (Optional)

See [TESTING.md](./TESTING.md) for detailed testing instructions.

**Quick test**:

```powershell
# Test pattern validation
pwsh .github/hooks/scripts/validate-patterns.ps1

# Test auto-format
pwsh .github/hooks/scripts/auto-format.ps1
```

### 2. Use Copilot Normally

Hooks run automatically! You'll see:

- ✅ **At session start**: Environment info and quick commands
- ⚠️ **Before edits**: Warnings/blocks for anti-patterns
- ✅ **After edits**: Auto-formatting confirmation
- 📋 **At session end**: Pre-commit checklist

### 3. Customize (Optional)

**Disable a hook temporarily**:

```powershell
# Rename to disable
Rename-Item .github/hooks/validate-patterns.json validate-patterns.json.disabled
```

**Adjust hook behavior**: Edit the PowerShell scripts in `scripts/`

**Add new validation rules**: Edit `scripts/validate-patterns.ps1`

## Examples

### Pattern Validation in Action

❌ **This will be blocked**:

```python
# Hardcoded secret
api_key = "sk-1234567890abcdefghijk"

# Relative import crossing packages
from ...core.logging import get_logger
```

⚠️ **This will warn but allow**:

```python
# Using print() instead of logger
print("Debug message")

# Using stdlib logging
import logging
logging.info("Started")
```

✅ **This will pass validation**:

```python
from __future__ import annotations

from pathlib import Path

from aica.core.logging import get_logger

log = get_logger("mymodule")
log.info("message", key="value")
```

### Auto-Format in Action

**Before edit** (bad formatting):

```python
def bad_function(x,y,z):
    result=x+y+z
    return result
```

**After Copilot edit + hook** (auto-formatted):

```python
def bad_function(x, y, z):
    result = x + y + z
    return result
```

## Troubleshooting

### Hooks not running?

1. Check JSON syntax: `Get-Content .github/hooks/*.json | ConvertFrom-Json`
2. Check VS Code Output panel: View → Output → GitHub Copilot
3. Verify PowerShell execution policy: `Get-ExecutionPolicy`

### Hook blocking legitimate code?

1. Review the validation rules in `scripts/validate-patterns.ps1`
2. Adjust patterns or thresholds as needed
3. Or disable the hook temporarily (rename `.json` file)

### Script errors?

Run scripts manually to debug:

```powershell
pwsh .github/hooks/scripts/validate-patterns.ps1
Write-Host "Exit code: $LASTEXITCODE"
```

## Learn More

- [README.md](./README.md) - Complete hook documentation
- [TESTING.md](./TESTING.md) - Detailed testing guide
- [Hooks Reference](https://code.visualstudio.com/docs/copilot/customization/hooks) - Official VS Code docs

## Need Help?

- Review hook output in VS Code Output panel (GitHub Copilot channel)
- Check script logs by running manually
- See [TESTING.md](./TESTING.md) for troubleshooting tips

---

🎉 **You're all set!** Hooks will now enforce AICA patterns automatically.
