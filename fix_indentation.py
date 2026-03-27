#!/usr/bin/env python3
"""Fix the indentation issue in incremental_builder.py"""
from pathlib import Path

file_path = Path("aica/memory/graph_store/incremental_builder.py")
content = file_path.read_text()

# Simple find-replace with exact spacing
old = "        try:\n            with open(path) as f:\n                content = json.load(f)\n                # Ensure always returns list[dict]\n                if isinstance(content, dict):\n                    return [content]\n                return content if isinstance(content, list) else []\n            except (json.JSONDecodeError, OSError) as e:\n                log.warning(\"ast.file_load_failed\", filename=filename, error=str(e))\n                return []"

new = "        try:\n            with open(path) as f:\n                content = json.load(f)\n                # Ensure always returns list[dict]\n                if isinstance(content, dict):\n                    return [content]\n                return content if isinstance(content, list) else []\n        except (json.JSONDecodeError, OSError) as e:\n            log.warning(\"ast.file_load_failed\", filename=filename, error=str(e))\n            return []"

if old in content:
    content = content.replace(old, new)
    file_path.write_text(content)
    print("✓ Fixed indentation!")
    # Verify
    lines = content.split('\n')
    for i in range(100, 115):
        if i < len(lines):
            print(f"{i+1}: {lines[i][:60]}")
else:
    print("✗ Pattern not found")
    # Show what we have
    lines = content.split('\n')
    for i in range(100, 115):
        if i < len(lines):
            print(f"{i+1}: {repr(lines[i][:60])}")
