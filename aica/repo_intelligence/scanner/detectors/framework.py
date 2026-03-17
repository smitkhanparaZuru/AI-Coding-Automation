from __future__ import annotations

import json
import re
from pathlib import Path

from aica.core.logging import get_logger

log = get_logger("repo.scanner.framework")

_APP_ROUTER_MARKERS = ("page.tsx", "page.jsx", "layout.tsx", "layout.jsx")
_APP_ROUTER_DIRS = ("src/app", "app")

_LOCKFILES: list[tuple[str, str]] = [
    ("pnpm-lock.yaml", "pnpm"),
    ("yarn.lock", "yarn"),
    ("package-lock.json", "npm"),
    ("bun.lockb", "bun"),
]

_VERSION_RE = re.compile(r"[\^~>=<\s]*(\d+\.\d+[\w.\-]*)")


def _clean_version(raw: str) -> str:
    m = _VERSION_RE.match(raw.strip())
    return m.group(1) if m else raw.strip()


class FrameworkDetector:
    """Detect the JS/TS framework, language, and routing strategy for a repo."""

    def detect(self, repo_path: Path) -> dict:
        log.info("framework_detector.start", path=str(repo_path))

        framework: str = "unknown"
        next_version: str | None = None
        language: str = "JavaScript"
        app_router: bool = False
        package_manager: str = "npm"

        # --- package.json ---
        pkg_file = repo_path / "package.json"
        if pkg_file.is_file():
            try:
                pkg = json.loads(pkg_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                log.warning("framework_detector.package_json.parse_error", error=str(exc))
                pkg = {}

            all_deps: dict = {
                **pkg.get("dependencies", {}),
                **pkg.get("devDependencies", {}),
            }

            if "next" in all_deps:
                framework = "Next.js"
                next_version = _clean_version(all_deps["next"])
                log.debug("framework_detector.next_found", version=next_version)
            elif "react" in all_deps:
                framework = "React"
            elif "nuxt" in all_deps:
                framework = "Nuxt"
            elif "vue" in all_deps:
                framework = "Vue"
        else:
            log.warning("framework_detector.package_json.missing", path=str(pkg_file))
            pkg = {}

        # --- TypeScript ---
        if (repo_path / "tsconfig.json").is_file() or (repo_path / "tsconfig.base.json").is_file():
            language = "TypeScript"

        # --- App Router ---
        if framework == "Next.js":
            for candidate_dir in _APP_ROUTER_DIRS:
                app_dir = repo_path / candidate_dir
                if app_dir.is_dir():
                    if any((app_dir / marker).exists() for marker in _APP_ROUTER_MARKERS):
                        app_router = True
                        log.debug(
                            "framework_detector.app_router_detected",
                            dir=str(app_dir),
                        )
                        break

        # --- Package manager ---
        for lockfile, manager in _LOCKFILES:
            if (repo_path / lockfile).is_file():
                package_manager = manager
                break

        result = {
            "framework": framework,
            "language": language,
            "app_router": app_router,
            "next_version": next_version,
            "package_manager": package_manager,
        }
        log.info("framework_detector.done", **result)
        return result
