from __future__ import annotations

from pathlib import Path

from aica.core.logging import get_logger

log = get_logger("repo.scanner.structure")

# Known source directories to probe (relative to repo root and src/)
_SRC_DIRS = (
    "app",
    "components",
    "lib",
    "services",
    "hooks",
    "utils",
    "types",
    "store",
    "features",
    "db",
    "pages",
    "api",
    "styles",
    "public",
    "middleware",
    "config",
    "actions",
    "server",
    "trpc",
)

# Config file probe specs: (result_key, list_of_candidates)
_CONFIG_FILES: list[tuple[str, list[str]]] = [
    ("package_json", ["package.json"]),
    ("tsconfig", ["tsconfig.json", "tsconfig.base.json"]),
    ("next_config", ["next.config.ts", "next.config.mjs", "next.config.js"]),
    ("drizzle_config", ["drizzle.config.ts", "drizzle.config.js"]),
    ("tailwind_config", ["tailwind.config.ts", "tailwind.config.js", "tailwind.config.cjs"]),
    ("eslint_config", [".eslintrc.js", ".eslintrc.cjs", ".eslintrc.json", ".eslintrc.yaml", ".eslintrc"]),  # noqa: E501
    ("prettier_config", [".prettierrc", ".prettierrc.json", ".prettierrc.js", "prettier.config.js"]),  # noqa: E501
    ("postcss_config", ["postcss.config.js", "postcss.config.cjs", "postcss.config.mjs"]),
    ("vitest_config", ["vitest.config.ts", "vitest.config.js"]),
    ("jest_config", ["jest.config.ts", "jest.config.js"]),
    ("playwright_config", ["playwright.config.ts", "playwright.config.js"]),
    ("docker_compose", ["docker-compose.yml", "docker-compose.yaml"]),
    ("dockerfile", ["Dockerfile"]),
]

# Hidden/system dirs to exclude from root_dirs listing
_EXCLUDE_DIRS = frozenset({
    "node_modules", ".git", ".next", ".turbo", ".vercel",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "dist", "build", "out", ".cache", ".yarn",
})


class StructureDetector:
    """Detect the source directory layout and config files for a repo."""

    def detect(self, repo_path: Path) -> dict:
        log.info("structure_detector.start", path=str(repo_path))

        # --- Root dirs ---
        root_dirs = sorted(
            d.name
            for d in repo_path.iterdir()
            if d.is_dir() and d.name not in _EXCLUDE_DIRS
        )

        # --- src/ prefix detection ---
        has_src_prefix = (repo_path / "src").is_dir()

        # --- Source directory mapping ---
        src_structure: dict[str, str] = {}
        probe_roots = [repo_path / "src", repo_path] if has_src_prefix else [repo_path]

        for probe_root in probe_roots:
            prefix = "src/" if probe_root.name == "src" else ""
            for dirname in _SRC_DIRS:
                if dirname in src_structure:
                    continue
                candidate = probe_root / dirname
                if candidate.is_dir():
                    src_structure[dirname] = f"{prefix}{dirname}/"

        # --- Config files ---
        config_files: dict[str, str | list[str]] = {}

        for key, candidates in _CONFIG_FILES:
            for candidate in candidates:
                if (repo_path / candidate).is_file():
                    config_files[key] = candidate
                    break

        # Collect env files separately (can be multiple)
        env_files = sorted(
            f.name
            for f in repo_path.iterdir()
            if f.is_file() and f.name.startswith(".env")
        )
        if env_files:
            config_files["env_files"] = env_files

        result = {
            "src_structure": src_structure,
            "config_files": config_files,
            "root_dirs": root_dirs,
            "has_src_prefix": has_src_prefix,
        }
        log.info(
            "structure_detector.done",
            src_dirs=len(src_structure),
            config_count=len(config_files),
            root_dirs=len(root_dirs),
        )
        return result
