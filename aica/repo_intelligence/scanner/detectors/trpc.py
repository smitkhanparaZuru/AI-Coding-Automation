from __future__ import annotations

import re
from pathlib import Path

from aica.core.logging import get_logger

log = get_logger("repo.scanner.detectors.trpc")

# Matches router-factory call — confirms a file is a tRPC router
_RE_ROUTER_FACTORY = re.compile(r"\b(?:createTRPCRouter|router)\s*\(")

# Matches named procedure definitions: `procedureName: t.procedure.query(`
# or `procedureName: publicProcedure.mutation(`
_RE_NAMED_PROC = re.compile(
    r"([a-zA-Z_$][\w$]*)\s*:\s*\w+(?:\.\w+)*\.\s*(?:query|mutation)\s*\("
)

# Reserved words that appear before .query/.mutation but are NOT procedure names
_PROC_RESERVED = frozenset({"query", "mutation", "input", "output", "use", "middleware"})

# Tier sub-directories recognised under the routers/ root
_TIER_DIRS = ("lambda", "async", "edge", "tools")


class TRPCRouterDetector:
    """Detect tRPC router files and extract procedure names.

    Scans ``src/server/routers/{lambda,async,edge}/`` for ``.ts`` router files,
    confirms they contain a router-factory call, and extracts named procedure
    definitions.

    Output per router file::

        {
            "tier": "lambda",
            "router": "agent",
            "file": "src/server/routers/lambda/agent.ts",
            "procedures": ["getById", "create", "update"]
        }
    """

    def detect(self, repo_path: Path) -> list[dict]:
        """Return one entry per tRPC router file found under *repo_path*.

        Args:
            repo_path: Absolute path to the repository root.

        Returns:
            List of router descriptor dicts. Empty list when nothing detected.
        """
        log.info("trpc.start", path=str(repo_path))
        routers_root = self._locate_routers_dir(repo_path)
        if routers_root is None:
            log.info("trpc.no_routers_dir", path=str(repo_path))
            return []

        results: list[dict] = []

        # Scan tier subdirectories first
        for tier in _TIER_DIRS:
            tier_dir = routers_root / tier
            if not tier_dir.is_dir():
                continue
            for ts_file in sorted(tier_dir.glob("*.ts")):
                entry = self._scan_router_file(ts_file, repo_path, tier)
                if entry is not None:
                    results.append(entry)

        # Scan root-level router files (flat or non-tiered projects)
        for ts_file in sorted(routers_root.glob("*.ts")):
            entry = self._scan_router_file(ts_file, repo_path, "root")
            if entry is not None:
                results.append(entry)

        log.info("trpc.done", count=len(results))
        return results

    # ── private ───────────────────────────────────────────────────────────────

    def _locate_routers_dir(self, repo_path: Path) -> Path | None:
        for candidate in (
            "src/server/routers",
            "src/app/_trpc",
            "src/trpc",
            "server/routers",
            "src/server/api/routers",
        ):
            d = repo_path / candidate
            if d.is_dir():
                return d
        return None

    def _scan_router_file(
        self, file_path: Path, repo_path: Path, tier: str
    ) -> dict | None:
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            log.warning("trpc.read_error", file=str(file_path))
            return None

        if not _RE_ROUTER_FACTORY.search(content):
            return None  # Not a router definition file

        procedures = self._extract_procedures(content)
        rel_file = file_path.relative_to(repo_path).as_posix()
        log.debug("trpc.router", tier=tier, router=file_path.stem, procedures=len(procedures))
        return {
            "tier": tier,
            "router": file_path.stem,
            "file": rel_file,
            "procedures": procedures,
        }

    @staticmethod
    def _extract_procedures(content: str) -> list[str]:
        """Return deduplicated procedure names in source order."""
        found: list[str] = []
        seen: set[str] = set()
        for m in _RE_NAMED_PROC.finditer(content):
            name = m.group(1)
            if name not in seen and name not in _PROC_RESERVED:
                seen.add(name)
                found.append(name)
        return found
