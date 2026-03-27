#!/usr/bin/env python3
"""Test runner to show errors."""
import subprocess
import sys

result = subprocess.run(
    [
        sys.executable, "-m", "pytest",
        "tests/test_incremental_builder.py",
        "-v", "--tb=short"
    ],
    cwd=".",
    capture_output=True,
    text=True,
)

print(result.stdout)
print(result.stderr)
sys.exit(result.returncode)
