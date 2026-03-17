from __future__ import annotations

import re
from pathlib import Path

from aica.core.logging import get_logger

log = get_logger("repo.scanner.detectors.routes")

# Canonical HTTP method order for sorted output
_HTTP_METHODS_ORDER = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]

# Route group:  (groupname)  → transparent in URL
_RE_ROUTE_GROUP = re.compile(r"^\([^)]+\)$")

# tRPC / Next.js catch-all segment  [...slug] or [[...slug]]
_RE_CATCH_ALL = re.compile(r"^\[\[?\.\.\.")

# Variant dynamic segment pattern — locale-theme-mobile-... compound tuple
_RE_VARIANTS_SEGMENT = re.compile(r"^\[variants\]$", re.IGNORECASE)

# Server router tier inferred from file path
_TIER_PATH_MAP = {
    "/lambda/": "lambda",
    "/async/": "async",
    "/edge/": "edge",
    "/webapi/": "webapi",
    "/(backend)/api/": "api",
    "/trpc/": "trpc",
}

# Intercepted route:  (.)segment  (..)segment  (...)segment
# group 1 = interceptor prefix, group 2 = target segment name
_RE_INTERCEPTED = re.compile(r"^(\(\.+\))+(.+)$")

# Named function export:  export [async] function GET(
_RE_NAMED_EXPORT = re.compile(
    r"export\s+(?:async\s+)?function\s+(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\b"
)
# Arrow / const export:   export const GET =
_RE_CONST_EXPORT = re.compile(
    r"export\s+const\s+(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s*="
)


class RouteDetector:
    """Detect Next.js App Router routes by walking the ``app/`` directory.

    Handles:
    * ``page.tsx``  — frontend page routes (type *page*)
    * ``route.ts``  — API routes (type *api*) with HTTP method extraction
    * Route groups  ``(groupname)``  — transparent, stripped from URL
    * Dynamic segments  ``[param]``  — kept as-is in URL
    * Parallel route slots  ``@slot``  — type *parallel*, slot name recorded
    * Intercepted routes  ``(.)target`` / ``(..)target``  — type *intercepted*
    """

    def detect(self, repo_path: Path) -> list[dict]:
        """Walk *repo_path* and return a list of route descriptor dicts."""
        app_dir = self._locate_app_dir(repo_path)
        if app_dir is None:
            log.info("routes.no_app_dir", path=str(repo_path))
            return []

        log.info("routes.scanning", app_dir=str(app_dir))
        routes: list[dict] = []

        for glob_pattern, base_type in (("**/page.tsx", "page"), ("**/route.ts", "api")):
            for file_path in sorted(app_dir.glob(glob_pattern)):
                rel_file = file_path.relative_to(repo_path)
                rel_dir = file_path.parent.relative_to(app_dir)

                route_url, route_type, slot = self._path_to_route(rel_dir)

                # path_to_route returns "page" when no special segment is found;
                # in that case the glob-derived base_type (page or api) wins.
                final_type = route_type if route_type != "page" else base_type

                entry: dict = {
                    "route": route_url,
                    "type": final_type,
                    "file": rel_file.as_posix(),
                }

                if slot is not None:
                    entry["slot"] = slot

                if final_type == "api":
                    entry["methods"] = self._extract_methods(file_path)
                    entry["tier"] = self._infer_tier(rel_file.as_posix())

                routes.append(entry)
                log.debug("routes.found", route=route_url, type=final_type, file=str(rel_file))

        log.info("routes.done", count=len(routes))
        return routes

    # ── helpers ───────────────────────────────────────────────────────────────

    def _locate_app_dir(self, repo_path: Path) -> Path | None:
        """Return the first existing app directory (``src/app`` preferred)."""
        for candidate in ("src/app", "app"):
            app_dir = repo_path / candidate
            if app_dir.is_dir():
                return app_dir
        return None

    def _path_to_route(self, rel_dir: Path) -> tuple[str, str, str | None]:
        """Convert a directory path relative to the app dir into ``(url, type, slot)``.

        Segment classification rules (applied in order):
        1. Starts with ``@``  → parallel route slot; reset URL, record slot name.
        2. Matches intercepted pattern ``(.)X``  → intercepted; reset URL, use X.
        3. Matches route group ``(name)``  → skip (transparent).
        4. Anything else (including ``[param]``) → added to URL as-is.
        """
        url_parts: list[str] = []
        route_type = "page"
        slot: str | None = None

        for part in rel_dir.parts:
            if part.startswith("@"):
                # Parallel route slot — not part of the URL hierarchy
                route_type = "parallel"
                slot = part
                url_parts = []
            elif m := _RE_INTERCEPTED.match(part):
                # Intercepted route — the URL is the intercepted target, not the source path
                route_type = "intercepted"
                url_parts = [m.group(2)]
            elif _RE_ROUTE_GROUP.match(part):
                # Route group — purely organisational, invisible in the URL
                pass
            elif _RE_VARIANTS_SEGMENT.match(part):
                # Multi-tenant variants dynamic segment — tag and keep in URL
                route_type = "variants_dynamic"
                url_parts.append(part)
            else:
                url_parts.append(part)

        route_url = "/" + "/".join(url_parts) if url_parts else "/"
        return route_url, route_type, slot

    def _extract_methods(self, file_path: Path) -> list[str]:
        """Return sorted HTTP methods exported from a ``route.ts`` file."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return []

        found: set[str] = set()
        found.update(_RE_NAMED_EXPORT.findall(content))
        found.update(_RE_CONST_EXPORT.findall(content))

        return [m for m in _HTTP_METHODS_ORDER if m in found]

    @staticmethod
    def _infer_tier(rel_file_posix: str) -> str | None:
        """Infer the API tier (lambda/async/edge) from the file path."""
        for marker, tier in _TIER_PATH_MAP.items():
            if marker in rel_file_posix:
                return tier
        return None
