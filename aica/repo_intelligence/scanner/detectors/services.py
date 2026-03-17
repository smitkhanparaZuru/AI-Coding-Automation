from __future__ import annotations

import re
from pathlib import Path

from aica.core.logging import get_logger

log = get_logger("repo.scanner.detectors.services")

# Directories to scan for service/utility files
_SCAN_DIRS = ("services", "lib", "utils")

# export class AuthService  — PascalCase class name
_RE_CLASS_EXPORT = re.compile(
    r"export\s+(?:default\s+)?(?:abstract\s+)?class\s+([A-Z][A-Za-z0-9_]*)"
)

# export [default] [async] function fnName(  — any valid identifier (camelCase or PascalCase)
_RE_NAMED_EXPORT_FN = re.compile(
    r"export\s+(?:default\s+)?(?:async\s+)?function\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*[(<]"
)

# export const fnName [: Type] =  (arrow function, value, or object)
_RE_CONST_EXPORT = re.compile(
    r"export\s+const\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*(?::[^=\n]+)?\s*="
)


class ServiceDetector:
    """Detect exported services and utilities in ``services/``, ``lib/``, and ``utils/``.

    Scans ``.ts`` and ``.tsx`` files using regex — no Node.js runtime required.
    Prefers the ``src/`` prefix layout used by Next.js.

    Output per file::

        {
            "service": "AuthService",
            "file": "services/auth.service.ts",
            "exported_functions": ["login", "logout"]
        }

    The ``service`` name is the first exported PascalCase class found in the file;
    if no class is found, the file stem is titlecased as a fallback.
    """

    def detect(self, repo_path: Path) -> list[dict]:
        """Return all service/utility entries found under *repo_path*.

        Args:
            repo_path: Absolute path to the repository root.

        Returns:
            List of dicts with keys ``service``, ``file``, and ``exported_functions``.
        """
        log.info("services.start", path=str(repo_path))
        services: list[dict] = []

        for file_path in self._locate_source_files(repo_path):
            entry = self._extract_service(file_path, repo_path)
            if entry is not None:
                services.append(entry)
                log.debug(
                    "services.file_found",
                    file=entry["file"],
                    service=entry["service"],
                    exports=len(entry["exported_functions"]),
                )

        log.info("services.done", count=len(services))
        return services

    # ── private ───────────────────────────────────────────────────────────────

    def _locate_source_files(self, repo_path: Path) -> list[Path]:
        """Return all ``.ts`` and ``.tsx`` files from each scan directory.

        The ``src/`` prefix is preferred; if ``src/<dir>`` exists it takes
        precedence over a root-level ``<dir>`` to avoid double-counting.
        """
        result: list[Path] = []
        for base_name in _SCAN_DIRS:
            for prefix in ("src", ""):
                candidate = repo_path / prefix / base_name if prefix else repo_path / base_name
                if candidate.is_dir():
                    result.extend(sorted(candidate.glob("**/*.ts")))
                    result.extend(sorted(candidate.glob("**/*.tsx")))
                    break  # src/ prefix wins; skip root-level variant
        return result

    def _extract_service(self, file_path: Path, repo_path: Path) -> dict | None:
        """Return a service descriptor dict for *file_path*, or ``None`` if unreadable."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            log.warning("services.read_error", file=str(file_path))
            return None

        rel_file = file_path.relative_to(repo_path).as_posix()

        # Determine service name: first exported class wins, else titlecase file stem
        class_match = _RE_CLASS_EXPORT.search(content)
        if class_match:
            service_name = class_match.group(1)
        else:
            # e.g. "auth.service" → ["auth", "service"] → "AuthService"
            # e.g. "formatDate" → ["formatDate"] → "FormatDate" (preserve inner casing)
            stem = file_path.stem
            service_name = "".join(
                part[0].upper() + part[1:] for part in re.split(r"[.\-_]", stem) if part
            )

        # Collect exported function / const names (any valid identifier)
        exported: list[str] = []
        seen: set[str] = set()

        for m in _RE_NAMED_EXPORT_FN.finditer(content):
            name = m.group(1)
            if name not in seen:
                seen.add(name)
                exported.append(name)

        for m in _RE_CONST_EXPORT.finditer(content):
            name = m.group(1)
            if name not in seen:
                seen.add(name)
                exported.append(name)

        return {
            "service": service_name,
            "file": rel_file,
            "exported_functions": exported,
        }
