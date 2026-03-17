from __future__ import annotations

import re
from pathlib import Path

from aica.core.logging import get_logger

log = get_logger("repo.scanner.detectors.components")

# Directories to scan for .tsx files (src/-prefixed variants are preferred)
_SCAN_DIRS = ("components", "app")

# export [default] [async] function PascalName(  or  PascalName<GenericParam>(
_RE_NAMED_EXPORT_FN = re.compile(
    r"export\s+(?:default\s+)?(?:async\s+)?function\s+([A-Z][A-Za-z0-9_]*)\s*[(<]"
)

# export const PascalName [: TypeAnnotation] =  (arrow)  or wrapped in memo/forwardRef/lazy
_RE_CONST_EXPORT = re.compile(
    r"export\s+const\s+([A-Z][A-Za-z0-9_]*)\s*(?::[^=\n]+)?\s*=\s*"
    r"(?:\(|(?:React\.)?(?:memo|forwardRef|lazy)\s*\()"
)

# export default PascalName  — identifier re-export (not an inline function/class)
_RE_DEFAULT_EXPORT_ID = re.compile(
    r"export\s+default\s+([A-Z][A-Za-z0-9_]*)\s*(?:;|$)",
    re.MULTILINE,
)

# Prop name inside an interface or type body:  propName:  or  propName?:
_RE_PROP_NAME = re.compile(
    r"^\s*(?:readonly\s+)?([a-zA-Z_$][\w$]*)\s*\??:",
    re.MULTILINE,
)


class ComponentDetector:
    """Detect exported React function components in ``.tsx`` files.

    Scans ``components/`` and ``app/`` directories (preferring the ``src/``
    prefix layout used by Next.js).  Detection is regex-only — no Node.js
    runtime required.

    Output per component::

        {"name": "UserCard", "file": "src/components/UserCard.tsx", "props": ["userId", "name"]}
    """

    def detect(self, repo_path: Path) -> list[dict]:
        """Return all React components found under *repo_path*.

        Args:
            repo_path: Absolute path to the repository root.

        Returns:
            List of dicts with keys ``name``, ``file``, and ``props``.
        """
        log.info("components.start", path=str(repo_path))
        components: list[dict] = []

        for file_path in self._locate_tsx_files(repo_path):
            found = self._extract_components(file_path, repo_path)
            components.extend(found)
            if found:
                log.debug(
                    "components.file_found",
                    file=str(file_path.relative_to(repo_path)),
                    count=len(found),
                )

        log.info("components.done", count=len(components))
        return components

    # ── private ───────────────────────────────────────────────────────────────

    def _locate_tsx_files(self, repo_path: Path) -> list[Path]:
        """Return all ``.tsx`` files from each scan directory.

        The ``src/`` prefix is preferred; if ``src/<dir>`` exists that takes
        precedence over a root-level ``<dir>`` to avoid double-counting.
        """
        result: list[Path] = []
        for base_name in _SCAN_DIRS:
            for prefix in ("src", ""):
                candidate = repo_path / prefix / base_name if prefix else repo_path / base_name
                if candidate.is_dir():
                    result.extend(sorted(candidate.glob("**/*.tsx")))
                    break  # src/ prefix wins; skip root-level variant
        return result

    def _extract_components(self, file_path: Path, repo_path: Path) -> list[dict]:
        """Return component descriptor dicts for every exported component in *file_path*."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            log.warning("components.read_error", file=str(file_path))
            return []

        rel_file = file_path.relative_to(repo_path).as_posix()
        found: dict[str, dict] = {}  # keyed by component name for deduplication

        # Pattern 1: export [default] [async] function ComponentName(
        for m in _RE_NAMED_EXPORT_FN.finditer(content):
            name = m.group(1)
            if name not in found:
                found[name] = self._make_entry(name, rel_file, content)

        # Pattern 2: export const ComponentName [: Type] = (arrow) / memo / forwardRef
        for m in _RE_CONST_EXPORT.finditer(content):
            name = m.group(1)
            if name not in found:
                found[name] = self._make_entry(name, rel_file, content)

        # Pattern 3: function ComponentName() { ... }  +  export default ComponentName
        for m in _RE_DEFAULT_EXPORT_ID.finditer(content):
            name = m.group(1)
            if name not in found and re.search(
                rf"(?:async\s+)?function\s+{re.escape(name)}\b", content
            ):
                found[name] = self._make_entry(name, rel_file, content)

        return list(found.values())

    def _make_entry(self, name: str, file: str, content: str) -> dict:
        return {"name": name, "file": file, "props": self._extract_props(content, name)}

    def _extract_props(self, content: str, component_name: str) -> list[str]:
        """Return prop names from the ``ComponentNameProps`` interface or type alias."""
        body = self._find_props_body(content, f"{component_name}Props")
        if body is None:
            return []
        return _RE_PROP_NAME.findall(body)

    def _find_props_body(self, content: str, type_name: str) -> str | None:
        """Locate the brace-delimited body of the *type_name* interface or type alias.

        Uses brace-counting to correctly handle nested types.
        """
        pattern = re.compile(
            rf"(?:interface\s+{re.escape(type_name)}\s*(?:<[^>]*>)?\s*\{{|"
            rf"type\s+{re.escape(type_name)}\s*(?:<[^>]*>)?\s*=\s*\{{)"
        )
        m = pattern.search(content)
        if m is None:
            return None

        # Brace-count from the opening { to find its matching closing }
        start = content.index("{", m.start())
        depth = 0
        for i in range(start, len(content)):
            if content[i] == "{":
                depth += 1
            elif content[i] == "}":
                depth -= 1
                if depth == 0:
                    return content[start + 1 : i]
        return None
