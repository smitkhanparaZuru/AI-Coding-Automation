"""
Vector Store Utilities — Sub-Plan 2.2

Helper functions for code chunking: source extraction, feature detection, text truncation.

Public API
----------
extract_source_lines(file_path: Path, start_line: int, end_line: int) -> str
infer_feature(file_path: str) -> str | None
truncate_text(text: str, max_chars: int) -> tuple[str, bool]
"""

from __future__ import annotations

import re
from pathlib import Path

from aica.core.logging.logger import get_logger

log = get_logger("vector_store.utils")

# Feature directory patterns (searched in order)
_FEATURE_PATTERNS = [
    re.compile(r"/features/([^/]+)/"),  # src/features/Auth/login.ts → Auth
    re.compile(r"/routes/([^/]+)/"),  # src/routes/api/user.ts → api
    re.compile(r"/components/([^/]+)/"),  # src/components/Button/index.tsx → Button
    re.compile(r"/app/([^/]+)/"),  # src/app/dashboard/page.tsx → dashboard
    re.compile(r"/pages/([^/]+)/"),  # src/pages/admin/users.tsx → admin
]


def extract_source_lines(
    file_path: Path, start_line: int, end_line: int | None = None
) -> str:
    """Extract source code lines from a file.

    Args:
        file_path: Absolute path to source file.
        start_line: 1-based line number to start (inclusive).
        end_line: 1-based line number to end (inclusive). If None, read to EOF.

    Returns:
        Extracted source text. Empty string if file unavailable or error occurs.

    Example:
        >>> from pathlib import Path
        >>> text = extract_source_lines(Path("src/utils.ts"), 10, 20)
        >>> print(text[:50])
        export function calculateTotal(items: Item[]) {
    """
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError) as e:
        log.warning(
            "utils.extract_source.read_failed",
            file=str(file_path),
            error=str(e),
        )
        return ""

    lines = content.splitlines()

    # Handle out-of-bounds line numbers gracefully
    if start_line < 1 or start_line > len(lines):
        log.warning(
            "utils.extract_source.invalid_start",
            file=str(file_path),
            start_line=start_line,
            total_lines=len(lines),
        )
        return ""

    # Convert to 0-based indexing
    start_idx = start_line - 1
    end_idx = (end_line if end_line is not None else len(lines)) - 1 + 1

    # Extract slice
    extracted = lines[start_idx:end_idx]
    return "\n".join(extracted)


def infer_feature(file_path: str) -> str | None:
    """Infer feature/module name from file path directory structure.

    Searches for common feature directory patterns (features/, routes/, components/)
    and extracts the immediate subdirectory name.

    Args:
        file_path: POSIX-relative file path (e.g., "src/features/Auth/login.ts").

    Returns:
        Feature name (e.g., "Auth") or None if no pattern matches.

    Example:
        >>> infer_feature("src/features/Auth/hooks/useAuth.ts")
        'Auth'
        >>> infer_feature("src/routes/api/users/route.ts")
        'api'
        >>> infer_feature("src/utils/helpers.ts")
        None
    """
    # Ensure leading slash for regex matching
    normalized = f"/{file_path}" if not file_path.startswith("/") else file_path

    for pattern in _FEATURE_PATTERNS:
        match = pattern.search(normalized)
        if match:
            return match.group(1)

    return None


def truncate_text(text: str, max_chars: int = 2000) -> tuple[str, bool]:
    """Truncate text to maximum character count with indicator.

    Args:
        text: Source text to potentially truncate.
        max_chars: Maximum character count (default: 2000).

    Returns:
        Tuple of (truncated_text, was_truncated).
        If text <= max_chars, returns (text, False).
        If text > max_chars, returns (text[:max_chars] + "...", True).

    Example:
        >>> text = "a" * 3000
        >>> truncated, was_truncated = truncate_text(text, max_chars=2000)
        >>> len(truncated)
        2003
        >>> was_truncated
        True
        >>> truncated[-3:]
        '...'
    """
    if len(text) <= max_chars:
        return text, False

    log.debug(
        "utils.truncate_text.truncated",
        original_length=len(text),
        max_chars=max_chars,
    )

    return text[:max_chars] + "...", True
