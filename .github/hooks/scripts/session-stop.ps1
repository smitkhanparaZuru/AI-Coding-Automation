#!/usr/bin/env pwsh
# Session stop hook - remind about pre-commit validation
# This runs when the agent session ends

param()

$ErrorActionPreference = "Continue"

# Build reminder message
$messages = @()
$messages += "📋 Session Ended - Pre-Commit Checklist:"
$messages += ""
$messages += "Before committing, run:"
$messages += "  ☐ pytest tests/ -v                    # All tests pass"
$messages += "  ☐ pytest tests/ --cov=aica            # Check coverage"
$messages += "  ☐ ruff check aica/                    # No lint errors"
$messages += "  ☐ ruff format aica/                   # Code formatted"
$messages += "  ☐ mypy aica/                          # Type check passes"
$messages += ""
$messages += "📚 See: .github/skills/pre-release-checklist/SKILL.md"

# Return hook output
$output = @{
    continue      = $true
    systemMessage = $messages -join "`n"
}

$output | ConvertTo-Json -Compress | Write-Output
exit 0
