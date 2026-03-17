from __future__ import annotations

from pathlib import Path

from aica.core.logging import get_logger

log = get_logger("repo.scanner.structure")

# Known source directories to probe (relative to repo root and src/)
_SRC_DIRS = (
    "app",
    "components",
    "lib",
    "libs",
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
    "chains",
    "prompts",
    "tools",
    "icons",
    "font",
    "layout",
    "helpers",
    "migrations",
    "locales",
    "const",
    "database",
    "assets",
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
    ("vitest_server_config", ["vitest.server.config.ts", "vitest.server.config.js"]),
    ("jest_config", ["jest.config.ts", "jest.config.js"]),
    ("playwright_config", ["playwright.config.ts", "playwright.config.js"]),
    ("docker_compose", ["docker-compose.yml", "docker-compose.yaml", "docker-compose/docker-compose.yml"]),
    ("dockerfile", ["Dockerfile", "Dockerfile.database"]),
    ("vercel_config", ["vercel.json"]),
    ("netlify_config", ["netlify.toml"]),
    ("gitlab_ci", [".gitlab-ci.yml", ".gitlab-ci.yaml"]),
    ("i18n_config", [".i18nrc.js", ".i18nrc.ts", ".i18nrc.cjs", "i18n.config.ts", "i18n.config.js"]),
    ("sentry_client_config", ["sentry.client.config.ts", "sentry.client.config.js"]),
    ("sentry_server_config", ["sentry.server.config.ts", "sentry.server.config.js"]),
    ("sentry_edge_config", ["sentry.edge.config.ts", "sentry.edge.config.js"]),
    ("commitlint_config", [".commitlintrc.js", ".commitlintrc.cjs", ".commitlintrc.json"]),
    ("release_config", [".releaserc.js", ".releaserc.json", ".releaserc.cjs"]),
    ("changelog_config", [".changelogrc.js", ".changelogrc.json"]),
    ("codecov_config", ["codecov.yml", "codecov.yaml"]),
    ("bun_config", [".bunfig.toml"]),
]

# Deployment/CI indicator directories to probe
_DEPLOY_DIRS: list[tuple[str, str]] = [
    ("github_workflows", ".github/workflows"),
    ("docker_compose_dir", "docker-compose"),
    ("devcontainer", ".devcontainer"),
    ("gitlab_ci_dir", ".gitlab"),
    ("kiro_config", ".kiro"),
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

        # Deployment directory indicators
        deploy_dirs: dict[str, str] = {}
        for key, rel_path in _DEPLOY_DIRS:
            if (repo_path / rel_path).is_dir():
                deploy_dirs[key] = rel_path

        # .env.example variable category summary
        env_summary = self._parse_env_example(repo_path)

        result = {
            "src_structure": src_structure,
            "config_files": config_files,
            "root_dirs": root_dirs,
            "has_src_prefix": has_src_prefix,
            "deploy_dirs": deploy_dirs,
            "env_summary": env_summary,
        }
        log.info(
            "structure_detector.done",
            src_dirs=len(src_structure),
            config_count=len(config_files),
            root_dirs=len(root_dirs),
            deploy_dirs=len(deploy_dirs),
        )
        return result

    # ── private ───────────────────────────────────────────────────────────────

    def _parse_env_example(self, repo_path: Path) -> dict:
        """Parse .env.example to summarise variable counts by prefix category."""
        import re

        env_candidates = [".env.example", ".env.local.example", ".env.sample"]
        for name in env_candidates:
            env_path = repo_path / name
            if not env_path.exists():
                continue
            try:
                content = env_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            all_vars = re.findall(r"^(?!#)([A-Z][A-Z0-9_]*)\s*=", content, re.MULTILINE)
            total = len(all_vars)

            # Aggregate by prefix (e.g. NEXTAUTH_, DATABASE_, AUTH_, OPENAI_)
            category_counts: dict[str, int] = {}
            for var in all_vars:
                prefix = var.split("_")[0] if "_" in var else var
                category_counts[prefix] = category_counts.get(prefix, 0) + 1

            return {"file": name, "total_vars": total, "categories": category_counts}

        return {}
