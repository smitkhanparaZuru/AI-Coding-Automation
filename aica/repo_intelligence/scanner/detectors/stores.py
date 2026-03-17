from __future__ import annotations

import re
from pathlib import Path

from aica.core.logging import get_logger

log = get_logger("repo.scanner.detectors.stores")

# Zustand middleware identifiers referenced in store files
_RE_MIDDLEWARE = re.compile(
    r"\b(devtools|subscribeWithSelector|persist|immer|combine)\b"
)

# Stem names that are structural (not slice names) within a store module
_STRUCTURAL_STEMS = frozenset({"initialState", "action", "selectors", "index", "helpers", "types"})


class ZustandStoreDetector:
    """Detect Zustand store modules under ``src/store/``.

    For each store module (subdirectory of the store root) records:

    * **store** — module directory name (e.g. ``"user"``)
    * **path**  — relative path from repo root (e.g. ``"src/store/user"``)
    * **slices** — slice names discovered under a ``slices/`` subdirectory or
      via sub‑folder detection (folders that contain ``action.ts`` /
      ``initialState.ts`` / ``selectors.ts``).
    * **middleware** — Zustand middleware detected in any ``.ts``/``.tsx``
      file within the module.

    Output per store::

        {
            "store": "user",
            "path": "src/store/user",
            "slices": ["auth", "credits", "modelList"],
            "middleware": ["devtools", "subscribeWithSelector"]
        }
    """

    def detect(self, repo_path: Path) -> list[dict]:
        """Return one entry per Zustand store module found under *repo_path*.

        Args:
            repo_path: Absolute path to the repository root.

        Returns:
            List of store descriptor dicts.  Empty list when nothing is detected.
        """
        log.info("stores.start", path=str(repo_path))
        store_root = self._locate_store_dir(repo_path)
        if store_root is None:
            log.info("stores.no_store_dir", path=str(repo_path))
            return []

        results: list[dict] = []
        for entry in sorted(store_root.iterdir()):
            if not entry.is_dir():
                continue
            record = self._scan_store_module(entry, repo_path)
            if record is not None:
                results.append(record)

        log.info("stores.done", count=len(results))
        return results

    # ── private ───────────────────────────────────────────────────────────────

    def _locate_store_dir(self, repo_path: Path) -> Path | None:
        for candidate in ("src/store", "store"):
            d = repo_path / candidate
            if d.is_dir():
                return d
        return None

    def _scan_store_module(self, module_dir: Path, repo_path: Path) -> dict | None:
        ts_files = list(module_dir.glob("**/*.ts")) + list(module_dir.glob("**/*.tsx"))
        if not ts_files:
            return None

        slices = self._detect_slices(module_dir)
        middleware = self._detect_middleware(ts_files)
        rel_path = module_dir.relative_to(repo_path).as_posix()

        log.debug(
            "stores.module",
            store=module_dir.name,
            slices=len(slices),
            middleware=len(middleware),
        )
        return {
            "store": module_dir.name,
            "path": rel_path,
            "slices": slices,
            "middleware": middleware,
        }

    def _detect_slices(self, module_dir: Path) -> list[str]:
        """Return slice names for a store module."""
        slices: set[str] = set()

        # Priority 1 — explicit slices/ subdirectory (zuru-gpt pattern)
        slices_dir = module_dir / "slices"
        if slices_dir.is_dir():
            for child in sorted(slices_dir.iterdir()):
                if child.is_dir():
                    slices.add(child.name)
                elif child.suffix in (".ts", ".tsx") and child.stem not in _STRUCTURAL_STEMS:
                    slices.add(child.stem)
            return sorted(slices)

        # Priority 2 — subdirectories containing slice-marker files
        for subdir in sorted(module_dir.iterdir()):
            if not subdir.is_dir():
                continue
            sub_stems = {f.stem for f in subdir.iterdir() if f.suffix in (".ts", ".tsx")}
            if sub_stems & {"action", "initialState", "selectors"}:
                slices.add(subdir.name)

        return sorted(slices)

    def _detect_middleware(self, ts_files: list[Path]) -> list[str]:
        found: set[str] = set()
        for file_path in ts_files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for m in _RE_MIDDLEWARE.finditer(content):
                found.add(m.group(1))
        return sorted(found)
