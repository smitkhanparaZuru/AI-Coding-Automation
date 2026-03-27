#!/usr/bin/env python3
"""Fix indentation in incremental_builder.py"""

# Read the file
with open('aica/memory/graph_store/incremental_builder.py', 'r') as f:
    content = f.read()

# Find and replace the problematic section
old = """        try:
            with open(path) as f:
                content = json.load(f)
                # Ensure always returns list[dict]
                if isinstance(content, dict):
                    return [content]
                return content if isinstance(content, list) else []
            except (json.JSONDecodeError, OSError) as e:
                log.warning("ast.file_load_failed", filename=filename, error=str(e))
                return []"""

new = """        try:
            with open(path) as f:
                content = json.load(f)
                # Ensure always returns list[dict]
                if isinstance(content, dict):
                    return [content]
                return content if isinstance(content, list) else []
        except (json.JSONDecodeError, OSError) as e:
            log.warning("ast.file_load_failed", filename=filename, error=str(e))
            return []"""

if old in content:
    content = content.replace(old, new)
    with open('aica/memory/graph_store/incremental_builder.py', 'w') as f:
        f.write(content)
    print("✓ Fixed indentation!")
else:
    print("✗ Pattern not found - file may have been modified")
    # Try showing what we have
    lines = content.split('\n')
    for i, line in enumerate(lines[100:115], start=101):
        print(f"{i:3d}: {repr(line)}")
