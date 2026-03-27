#!/usr/bin/env pwsh
# Session start hook - provide AICA context and environment check
# This runs at the start of each agent session

param()

$ErrorActionPreference = "Continue"

# Build context message
$messages = @()
$messages += "🤖 AICA Development Session Started"
$messages += ""

# Check Python environment
$pythonVersion = $null
try {
    $pythonOutput = python --version 2>&1
    if ($pythonOutput -match 'Python (\d+\.\d+\.\d+)') {
        $pythonVersion = $matches[1]
        $messages += "✓ Python: $pythonVersion"
    }
}
catch {
    $messages += "⚠️  Python not found in PATH"
}

# Check ruff (linter/formatter)
$ruffVersion = $null
try {
    $ruffOutput = ruff --version 2>&1
    if ($ruffOutput -match 'ruff (\d+\.\d+\.\d+)') {
        $ruffVersion = $matches[1]
        $messages += "✓ Ruff: $ruffVersion"
    }
}
catch {
    $messages += "⚠️  Ruff not installed (run: pip install ruff)"
}

# Check pytest
$pytestAvailable = $null -ne (Get-Command pytest -ErrorAction SilentlyContinue)
if ($pytestAvailable) {
    $messages += "✓ Pytest: Available"
}
else {
    $messages += "⚠️  Pytest not installed"
}

$messages += ""
$messages += "📋 Quick Commands:"
$messages += "  • pytest tests/ -v              Run all tests"
$messages += "  • ruff check aica/              Lint code"
$messages += "  • ruff format aica/             Format code"
$messages += "  • pytest --cov=aica tests/      Coverage report"
$messages += ""
$messages += "🎯 Active Hooks:"
$messages += "  • SessionStart: Environment check (this message)"
$messages += "  • PreToolUse: Pattern validation (blocks anti-patterns)"
$messages += "  • PostToolUse: Auto-format Python files with ruff"
$messages += "  • Stop: Pre-commit checklist reminder"
$messages += ""
$messages += "📚 Key AICA Rules:"
$messages += "  • Always start files with: from __future__ import annotations"
$messages += "  • Use get_logger() for logging, never print() or stdlib logging"
$messages += "  • Absolute imports (from aica.module import ...) across packages"
$messages += "  • Type hints on all function signatures"
$messages += "  • Use Path not str for file paths"

# Return hook output with context message
$output = @{
    continue      = $true
    systemMessage = $messages -join "`n"
}

$output | ConvertTo-Json -Compress | Write-Output
exit 0
