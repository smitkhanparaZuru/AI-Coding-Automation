from __future__ import annotations

import re
from pathlib import Path

from aica.core.logging import get_logger

log = get_logger("repo.scanner.detectors.hooks")

# Matches: export [default] [async] function useXxx(
_RE_HOOK_FN = re.compile(
    r"export\s+(?:default\s+)?(?:async\s+)?function\s+(use[A-Z][A-Za-z0-9_]*)\s*\(([^)]*)\)"
)

# Matches: export const useXxx = (  or  export const useXxx: Type = (
_RE_HOOK_CONST = re.compile(
    r"export\s+const\s+(use[A-Z][A-Za-z0-9_]*)\s*(?::[^=\n]+)?\s*=\s*\(([^)]*)\)"
)

# Hook directory candidates (src/-prefixed preferred)
_HOOK_DIRS = (
    "src/hooks",
    "hooks",
)


class HooksDetector:
    """Detect exported React hooks (``useXxx``) in ``.ts`` / ``.tsx`` files.

    Scans the ``src/hooks/`` directory (or ``hooks/`` at the root) and returns
    all exported functions matching the ``useXxx`` naming convention, together
    with their declared parameters.

    Output per hook::

        {"name": "useIsMobile", "file": "src/hooks/useIsMobile.ts", "parameters": ["breakpoint"]}
    """

    def detect(self, repo_path: Path) -> list[dict]:
        """Return all custom hooks found under *repo_path*.

        Args:
            repo_path: Absolute path to the repository root.

        Returns:
            List of hook descriptor dicts.  Empty list when no hooks dir found.
        """
        log.info("hooks.start", path=str(repo_path))
        hooks_dir = self._locate_hooks_dir(repo_path)
        if hooks_dir is None:
            log.info("hooks.no_dir", path=str(repo_path))
            return []

        results: list[dict] = []
        seen_names: set[str] = set()

        for ts_file in sorted(hooks_dir.glob("**/*.ts")) + sorted(hooks_dir.glob("**/*.tsx")):
            if ts_file.name.startswith("_"):
                continue
            hooks = self._extract_hooks(ts_file, repo_path, seen_names)
            results.extend(hooks)

        log.info("hooks.done", count=len(results))
        return results

    # ── private ───────────────────────────────────────────────────────────────

    def _locate_hooks_dir(self, repo_path: Path) -> Path | None:
        for candidate in _HOOK_DIRS:
            d = repo_path / candidate
            if d.is_dir():
                return d
        return None

    def _extract_hooks(
        self, file_path: Path, repo_path: Path, seen: set[str]
    ) -> list[dict]:
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            log.warning("hooks.read_error", file=str(file_path))
            return []

        rel_file = file_path.relative_to(repo_path).as_posix()
        found: list[dict] = []

        for pattern in (_RE_HOOK_FN, _RE_HOOK_CONST):
            for m in pattern.finditer(content):
                name = m.group(1)
                if name in seen:
                    continue
                seen.add(name)
                params = self._parse_params(m.group(2))
                found.append({"name": name, "file": rel_file, "parameters": params})

        return found

    @staticmethod
    def _parse_params(raw_params: str) -> list[str]:
        """Extract parameter names from a raw parameter string."""
        if not raw_params.strip():
            return []
        params: list[str] = []
        for param in raw_params.split(","):
            param = param.strip()
            if not param:
                continue
            # Handle destructuring, type annotations, default values
            # Take only the identifier: `name: Type = default` → `name`
            name = re.split(r"[=:{\[]", param)[0].strip()
            name = name.lstrip(".")  # rest param ...name
            if name and re.match(r"^[a-zA-Z_$][\w$]*$", name):
                params.append(name)
        return params
