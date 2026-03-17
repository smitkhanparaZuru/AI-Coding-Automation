from __future__ import annotations

import json
from pathlib import Path

from aica.core.logging import get_logger

log = get_logger("repo.scanner.detectors.packages")

# ---------------------------------------------------------------------------
# Catalog sets — each entry is matched as an exact package name OR as a
# prefix (when the entry ends with "/").  Prefix-matching collapses all
# scoped variants (e.g. every @radix-ui/react-* → "@radix-ui") into one
# canonical label.
# ---------------------------------------------------------------------------

# Priority-ordered so the first match wins for `framework`.
_FRAMEWORK_CATALOG: list[str] = [
    "next",
    "nuxt",
    "gatsby",
    "remix",
    "astro",
    "svelte",
    "@angular/core",
    "react",
    "vue",
]

# (catalog_name, set_of_packages_or_prefixes)
_UI_CATALOG: list[str] = [
    "tailwindcss",
    "@mui/material",
    "antd",
    "@chakra-ui/react",
    "@mantine/core",
    "@radix-ui/",   # prefix — any @radix-ui/* package → label: "@radix-ui"
    "framer-motion",
    "styled-components",
    "@emotion/react",
    "shadcn-ui",
]

_DATABASE_CATALOG: list[str] = [
    "@prisma/client",
    "prisma",
    "drizzle-orm",
    "mongoose",
    "typeorm",
    "sequelize",
    "pg",
    "mysql2",
    "better-sqlite3",
    "@planetscale/database",
    "@vercel/postgres",
]

_AUTH_CATALOG: list[str] = [
    "next-auth",
    "@auth/core",
    "@clerk/nextjs",
    "lucia",
    "@supabase/auth-helpers-nextjs",
    "firebase-admin",
    "passport",
]

_STATE_CATALOG: list[str] = [
    "zustand",
    "redux",
    "@reduxjs/toolkit",
    "jotai",
    "recoil",
    "mobx",
    "valtio",
    "@tanstack/react-query",
    "swr",
    "xstate",
]


def _match_catalog(installed: set[str], catalog: list[str]) -> list[str]:
    """Return canonical catalog labels that matched any installed package name.

    A catalog entry ending in ``/`` is treated as a **prefix**: the canonical
    label is the entry with the trailing slash stripped.  Multiple installed
    packages sharing the same prefix produce a single label.

    Args:
        installed: Set of raw package names from ``package.json``.
        catalog: Ordered list of catalog entries (exact names or prefixes).

    Returns:
        Sorted, deduplicated list of matched canonical labels.
    """
    matched: set[str] = set()
    for entry in catalog:
        if entry.endswith("/"):
            prefix = entry
            label = entry.rstrip("/")
            if any(pkg.startswith(prefix) for pkg in installed):
                matched.add(label)
        elif entry in installed:
            matched.add(entry)
    return sorted(matched)


class PackageDetector:
    """Classify ``package.json`` dependencies into five semantic buckets.

    Reads ``dependencies``, ``devDependencies``, and ``peerDependencies`` from
    the project's ``package.json`` and categorises them as:

    * **framework** — single string (primary framework) or ``null``
    * **ui** — UI / component libraries
    * **database** — database clients, ORMs
    * **auth** — authentication packages
    * **state** — state-management and data-fetching libraries

    Output schema::

        {
            "framework": "next",
            "ui": ["tailwindcss"],
            "database": ["prisma"],
            "auth": ["next-auth"],
            "state": ["zustand"]
        }

    All five keys are always present even when their value is ``null`` / ``[]``.
    """

    def detect(self, repo_path: Path) -> dict:
        """Analyse ``package.json`` under *repo_path* and return categorised deps.

        Args:
            repo_path: Absolute path to the repository root.

        Returns:
            Dict with keys ``framework``, ``ui``, ``database``, ``auth``,
            ``state``.  Never raises; returns empty arrays / null for missing
            or corrupt ``package.json``.
        """
        log.info("packages.start", path=str(repo_path))
        installed = self._read_deps(repo_path)

        framework = self._detect_framework(installed)
        ui = _match_catalog(installed, _UI_CATALOG)
        database = _match_catalog(installed, _DATABASE_CATALOG)
        auth = _match_catalog(installed, _AUTH_CATALOG)
        state = _match_catalog(installed, _STATE_CATALOG)

        result = {
            "framework": framework,
            "ui": ui,
            "database": database,
            "auth": auth,
            "state": state,
        }
        log.info(
            "packages.done",
            framework=framework,
            ui=ui,
            database=database,
            auth=auth,
            state=state,
        )
        return result

    # ── private ───────────────────────────────────────────────────────────────

    def _read_deps(self, repo_path: Path) -> set[str]:
        """Return all dependency names across all three dep sections."""
        pkg = repo_path / "package.json"
        if not pkg.exists():
            return set()
        try:
            data = json.loads(pkg.read_text(encoding="utf-8", errors="ignore"))
        except (json.JSONDecodeError, OSError):
            log.warning("packages.pkg_json_error", path=str(pkg))
            return set()
        deps: set[str] = set()
        for section in ("dependencies", "devDependencies", "peerDependencies"):
            deps.update(data.get(section, {}).keys())
        return deps

    def _detect_framework(self, installed: set[str]) -> str | None:
        """Return the first matching framework catalog name, or ``None``."""
        for entry in _FRAMEWORK_CATALOG:
            if entry.endswith("/"):
                if any(pkg.startswith(entry) for pkg in installed):
                    return entry.rstrip("/")
            elif entry in installed:
                return entry
        return None
