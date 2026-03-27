#!/usr/bin/env python3
"""Clean up the duplicate and broken code in incremental_builder.py"""
from pathlib import Path

file_path = Path("aica/memory/graph_store/incremental_builder.py")
content = file_path.read_text()
lines = content.split('\n')

# Find the start of _load_all_ast_data (broken version)
broken_start = None
for i, line in enumerate(lines):
    if 'def _load_all_ast_data(ast_dir: Path) -> dict[str, list[dict]]:' in line:
        broken_start = i
        break

# Find the start of _loaded_ast_data_fixed (correct version)
fixed_start = None
for i, line in enumerate(lines):
    if 'def _loaded_ast_data_fixed(ast_dir: Path) -> dict[str, list[dict]]:' in line:
        fixed_start = i
        break

print(f"Broken _load_all_ast_data at line {broken_start + 1}")
print(f"Fixed _loaded_ast_data_fixed at line {fixed_start + 1}")

# Extract the correct function (from fixed_start to end of that function)
# Find where _flatten_calls starts (next function) after the fixed version
flatten_start = None
for i in range(fixed_start + 1, len(lines)):
    if lines[i].startswith('def _flatten_calls'):
        flatten_start = i
        break

if flatten_start:
    print(f"_flatten_calls at line {flatten_start + 1}")
    
    # Extract correct version of _load_all_ast_data
    correct_function_lines = lines[fixed_start:flatten_start]
    # Rename it back
    correct_function_lines[0] = correct_function_lines[0].replace('_loaded_ast_data_fixed', '_load_all_ast_data')
    
    # Now build new file:
    # - Everything before broken function
    # - Correct _load_all_ast_data 
    # - Everything from _flatten_calls onward, removing any duplicates
    
    new_lines = lines[:broken_start]  # Everything before broken function
    new_lines.extend(correct_function_lines)  # Add correct function
    
    # Add remaining functions, skip duplicates by finding _flatten_calls and going from there
    # But first remove the duplicate _loaded_ast_data_fixed
    remaining_start = flatten_start
    remaining_lines = lines[remaining_start:]
    
     # Skip any broken duplicate code between old _load_all_ast_data and _flatten_calls
    final_lines = new_lines + remaining_lines
    
    # Write back
    new_content = '\n'.join(final_lines)
    file_path.write_text(new_content)
    print("✓ Fixed and cleaned up!")
else:
    print("✗ Could not find function boundaries")
