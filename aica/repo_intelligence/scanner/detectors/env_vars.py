from __future__ import annotations

import re
from pathlib import Path

from aica.core.logging import get_logger

log = get_logger("repo.scanner.detectors.env_vars")

# Matches a variable assignment line: VAR_NAME=... (optional value)
_RE_VAR_LINE = re.compile(r"^([A-Z][A-Z0-9_]*)(?:\s*=.*)?$")

# Candidate .env example file names (first found wins)
_ENV_EXAMPLE_CANDIDATES = (
    ".env.example",
    ".env.local.example",
    ".env.sample",
    ".env.template",
)

# Maps variable name prefix → category label.
# Checked in order; first match wins.
_PREFIX_CATEGORY_MAP: list[tuple[str | tuple[str, ...], str]] = [
    # LLM / AI model providers
    (("OPENAI_", "AZURE_", "ANTHROPIC_", "GOOGLE_", "GROQ_", "MISTRAL_",
      "PERPLEXITY_", "OLLAMA_", "OPENROUTER_", "ZHIPU_", "MOONSHOT_",
      "MINIMAX_", "DEEPSEEK_", "QWEN_", "CLOUDFLARE_", "SILICONCLOUD_",
      "TOGETHERAI_", "ZEROONE_", "AWS_", "FAL_"), "LLM"),
    # Authentication
    (("NEXT_AUTH_", "NEXT_PUBLIC_CLERK_", "CLERK_", "AUTH_", "NEXTAUTH_"), "AUTH"),
    # Database / encryption
    (("DATABASE_", "KEY_VAULTS_", "DB_"), "DATABASE"),
    # Object storage / S3
    (("S3_", "DOC_S3_", "MINIO_"), "S3"),
    # Observability / analytics
    (("SENTRY_", "POSTHOG_", "VERCEL_ANALYTICS_", "LOGFLARE_", "LOGTO_"), "OBSERVABILITY"),
    # NEXT_PUBLIC_ catch-all (that didn't match above)
    (("NEXT_PUBLIC_",), "PUBLIC"),
]

# Fallback category for variables not matching any prefix
_OTHER = "OTHER"


class EnvVarsDetector:
    """Parse environment variable definitions from an ``.env.example`` file.

    Groups all variables by semantic category (LLM, Auth, Database, S3, etc.)
    so downstream consumers can quickly understand the project's integration
    surface without reading the raw file.

    Output::

        {
            "file": ".env.example",
            "total": 54,
            "categories": {
                "LLM": ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "..."],
                "AUTH": ["NEXT_AUTH_SECRET", "CLERK_SECRET_KEY"],
                "DATABASE": ["DATABASE_URL", "KEY_VAULTS_SECRET"],
                "S3": ["S3_ACCESS_KEY_ID", "S3_BUCKET"],
                "PUBLIC": ["NEXT_PUBLIC_ENABLE_NEXT_AUTH"],
                "OTHER": ["ACCESS_CODE"]
            }
        }
    """

    def detect(self, repo_path: Path) -> dict:
        """Parse the .env.example file under *repo_path*.

        Args:
            repo_path: Absolute path to the repository root.

        Returns:
            Dict with keys ``file``, ``total``, ``categories``.  Returns an
            empty shell ``{"file": null, "total": 0, "categories": {}}`` when
            no env example file is found.
        """
        log.info("env_vars.start", path=str(repo_path))

        env_file, var_names = self._load_env_vars(repo_path)
        if env_file is None:
            log.info("env_vars.no_file", path=str(repo_path))
            return {"file": None, "total": 0, "categories": {}}

        categories = self._categorise(var_names)
        total = sum(len(v) for v in categories.values())

        result = {
            "file": env_file,
            "total": total,
            "categories": categories,
        }
        log.info("env_vars.done", file=env_file, total=total, categories=len(categories))
        return result

    # ── private ───────────────────────────────────────────────────────────────

    def _load_env_vars(self, repo_path: Path) -> tuple[str | None, list[str]]:
        """Return (filename, [var_names]) from the first env example file found."""
        for name in _ENV_EXAMPLE_CANDIDATES:
            path = repo_path / name
            if not path.exists():
                continue
            try:
                lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            var_names: list[str] = []
            for line in lines:
                line = line.strip()
                if line.startswith("#") or not line:
                    continue
                m = _RE_VAR_LINE.match(line)
                if m:
                    var_names.append(m.group(1))
            return name, var_names
        return None, []

    @staticmethod
    def _categorise(var_names: list[str]) -> dict[str, list[str]]:
        """Group variable names into semantic categories."""
        categories: dict[str, list[str]] = {}
        for var in var_names:
            assigned = False
            for prefixes, label in _PREFIX_CATEGORY_MAP:
                if isinstance(prefixes, str):
                    prefixes = (prefixes,)
                if any(var.startswith(p) for p in prefixes):
                    categories.setdefault(label, []).append(var)
                    assigned = True
                    break
            if not assigned:
                categories.setdefault(_OTHER, []).append(var)
        return categories
