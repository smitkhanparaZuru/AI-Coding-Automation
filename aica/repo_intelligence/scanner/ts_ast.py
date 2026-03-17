from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from aica.core.logging import get_logger

log = get_logger("repo.scanner.ts_ast")


class TsAstRunner:
    """Lightweight bridge to Node.js-based TypeScript AST extraction.

    This class is **not used in Task 2.1**.  It exists as a well-defined
    injection point for Phase 2.2 detectors (routes, components, services)
    that require real AST analysis of TypeScript/TSX files.

    Usage pattern (Phase 2.2+)::

        runner = TsAstRunner()
        if runner.is_available(repo_path):
            result = runner.run_extractor(repo_path, extractor_script)
        else:
            # fall back to regex heuristics
            ...
    """

    def is_available(self, repo_path: Path) -> bool:  # noqa: ARG002
        """Return True if Node.js is available on PATH.

        The *repo_path* argument is accepted for future use (e.g. checking a
        repo-local ``node`` binary inside ``node_modules/.bin``).
        """
        available = shutil.which("node") is not None
        log.debug("ts_ast.node_available", available=available)
        return available

    def run_extractor(self, repo_path: Path, script: str) -> dict | None:
        """Execute a Node.js *script* string inside *repo_path* and return its JSON output.

        The script must write a single JSON object to stdout.  Any stderr
        output is logged as a warning but does not raise.

        Args:
            repo_path: Working directory for the Node process.
            script: Inline JavaScript to execute via ``node -e``.

        Returns:
            Parsed dict on success, or ``None`` if Node is unavailable or the
            script fails / produces non-JSON output.
        """
        if not self.is_available(repo_path):
            log.warning("ts_ast.node_not_available")
            return None

        try:
            proc = subprocess.run(  # noqa: S603
                ["node", "-e", script],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            log.error("ts_ast.run_failed", error=str(exc))
            return None

        if proc.stderr:
            log.warning("ts_ast.extractor_stderr", stderr=proc.stderr[:500])

        if proc.returncode != 0:
            log.error("ts_ast.extractor_nonzero", returncode=proc.returncode)
            return None

        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            log.error("ts_ast.json_parse_error", error=str(exc), stdout=proc.stdout[:200])
            return None
