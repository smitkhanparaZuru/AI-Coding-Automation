#!/usr/bin/env pwsh
# Validate AICA coding patterns before file modifications
# This hook checks for common anti-patterns before edits are applied

param()

$ErrorActionPreference = "Continue"

# Read hook input from stdin
$input = $null
if (-not [Console]::IsInputRedirected) {
    $stdinInput = @(Get-Content -Raw)
    if ($stdinInput.Count -gt 0) {
        $input = $stdinInput[0] | ConvertFrom-Json -ErrorAction SilentlyContinue
    }
}

# Extract tool information
$toolName = ""
$newContent = ""
$filePaths = @()

if ($input) {
    $toolName = $input.toolName
    
    if ($input.toolArguments) {
        $args = $input.toolArguments
        
        # Extract file paths and new content
        if ($args.filePath) {
            $filePaths += $args.filePath
            $newContent = $args.newString
        }
        if ($args.replacements) {
            foreach ($replacement in $args.replacements) {
                if ($replacement.filePath) {
                    $filePaths += $replacement.filePath
                }
                if ($replacement.newString) {
                    $newContent += "`n" + $replacement.newString
                }
            }
        }
        if ($args.content) {
            $newContent = $args.content
        }
    }
}

# Filter to only Python files in aica/ directory
$aicaFiles = $filePaths | Where-Object { 
    $_ -match '\.py$' -and $_ -match 'aica[/\\]'
}

if ($aicaFiles.Count -eq 0 -or [string]::IsNullOrWhiteSpace($newContent)) {
    # Not editing AICA Python code, allow without validation
    $output = @{
        hookSpecificOutput = @{
            hookEventName      = "PreToolUse"
            permissionDecision = "allow"
        }
    }
    $output | ConvertTo-Json -Compress | Write-Output
    exit 0
}

# Validation: Check for anti-patterns
$warnings = @()
$errors = @()

# Check 1: No print() statements (use structured logging)
if ($newContent -match '\bprint\s*\(') {
    $warnings += "🚫 Found print() statement - use get_logger() instead"
}

# Check 2: No stdlib logging (use structlog)
if ($newContent -match '\blogging\.(info|debug|warning|error|critical)\(') {
    $warnings += "🚫 Found stdlib logging - use get_logger() from aica.core.logging"
}

# Check 3: Missing 'from __future__ import annotations' at start
if ($newContent -match '^[^#\n]*\n' -and $newContent -notmatch '^\s*from __future__ import annotations') {
    # Only warn if file has other imports
    if ($newContent -match '\bimport\b|\bfrom\b') {
        $warnings += "⚠️  Missing 'from __future__ import annotations' at file start"
    }
}

# Check 4: Using typing.List/Dict instead of builtin (Python 3.11+)
if ($newContent -match '\btyping\.(List|Dict|Tuple|Set)\b') {
    $warnings += "⚠️  Use builtin generics (list, dict, tuple, set) instead of typing.* in Python 3.11+"
}

# Check 5: Detect relative imports crossing packages (should use absolute)
if ($newContent -match 'from \.\.\.[^\s]+ import') {
    $errors += "❌ Relative import crossing packages detected - use absolute imports (from aica.module import ...)"
}

# Check 6: Hardcoded secrets or API keys
if ($newContent -match "(api_key|secret|password|token)\s*=\s*[`"'][^`"']{20,}[`"']") {
    $errors += "❌ Potential hardcoded secret detected - use Settings with SecretStr"
}

# Determine permission decision
$decision = "allow"
$reasons = @()

if ($errors.Count -gt 0) {
    $decision = "ask"
    $reasons += $errors
}

if ($warnings.Count -gt 0) {
    $reasons += $warnings
}

# Build output
$output = @{
    hookSpecificOutput = @{
        hookEventName      = "PreToolUse"
        permissionDecision = $decision
    }
}

if ($reasons.Count -gt 0) {
    $reasonText = "AICA Pattern Validation:`n" + ($reasons -join "`n")
    $output.hookSpecificOutput.permissionDecisionReason = $reasonText
    
    # Add system message for warnings even if allowing
    if ($decision -eq "allow") {
        $output.systemMessage = $reasonText
    }
}

$output | ConvertTo-Json -Depth 3 -Compress | Write-Output
exit 0
