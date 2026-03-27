#!/usr/bin/env pwsh
# Auto-format Python files after edit operations
# This hook runs after any file modification tool use

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

# Extract tool name and file paths from hook input
$toolName = ""
$filePaths = @()

if ($input) {
    $toolName = $input.toolName
    
    # Extract file paths from different tool types
    if ($input.toolArguments) {
        $args = $input.toolArguments
        
        # Handle different file path parameter names
        if ($args.filePath) {
            $filePaths += $args.filePath
        }
        if ($args.path) {
            $filePaths += $args.path
        }
        if ($args.replacements) {
            # multi_replace_string_in_file
            foreach ($replacement in $args.replacements) {
                if ($replacement.filePath) {
                    $filePaths += $replacement.filePath
                }
            }
        }
    }
}

# Filter to only Python files
$pythonFiles = $filePaths | Where-Object { $_ -match '\.py$' }

if ($pythonFiles.Count -eq 0) {
    # No Python files modified, exit successfully
    $output = @{
        continue = $true
    }
    $output | ConvertTo-Json -Compress | Write-Output
    exit 0
}

# Check if ruff is available
$ruffAvailable = $null -ne (Get-Command ruff -ErrorAction SilentlyContinue)

if (-not $ruffAvailable) {
    # Ruff not installed, skip formatting but don't block
    $output = @{
        continue      = $true
        systemMessage = "⚠️  Ruff not installed. Run 'pip install ruff' to enable auto-formatting."
    }
    $output | ConvertTo-Json -Compress | Write-Output
    exit 0
}

# Run ruff format on modified files
$formattedFiles = @()
$failedFiles = @()

foreach ($file in $pythonFiles) {
    try {
        # Run ruff format
        ruff format "$file" 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $formattedFiles += $file
        }
        else {
            $failedFiles += $file
        }
    }
    catch {
        $failedFiles += $file
    }
}

# Build status message
$messages = @()
if ($formattedFiles.Count -gt 0) {
    $fileList = ($formattedFiles | ForEach-Object { Split-Path $_ -Leaf }) -join ", "
    $messages += "✓ Auto-formatted: $fileList"
}
if ($failedFiles.Count -gt 0) {
    $fileList = ($failedFiles | ForEach-Object { Split-Path $_ -Leaf }) -join ", "
    $messages += "⚠️  Format failed: $fileList"
}

# Return hook output
$output = @{
    continue = $true
}

if ($messages.Count -gt 0) {
    $output.systemMessage = $messages -join " | "
}

$output | ConvertTo-Json -Compress | Write-Output
exit 0
