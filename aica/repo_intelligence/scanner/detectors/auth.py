from __future__ import annotations

import re
from pathlib import Path

from aica.core.logging import get_logger

log = get_logger("repo.scanner.detectors.auth")

# ── Provider detection patterns ───────────────────────────────────────────────
# Each value is a compiled regex; a match in any auth-related file → provider present.
_PROVIDER_PATTERNS: dict[str, re.Pattern[str]] = {
    "clerk": re.compile(r"\bClerkProvider\b|\bclerkMiddleware\b|@clerk/"),
    "next-auth": re.compile(r"\bNextAuth\b|\bAuthOptions\b|next[-_]auth"),
    "auth0": re.compile(r"\bauth0\b|Auth0Provider", re.IGNORECASE),
    "github": re.compile(r"\bGitHubProvider\b"),
    "azure-ad": re.compile(r"\bAzureADProvider\b|\bAzureB2CProvider\b|azure[_-]ad", re.IGNORECASE),
    "google": re.compile(r"\bGoogleProvider\b"),
    "credentials": re.compile(r"\bCredentialsProvider\b"),
    "authentik": re.compile(r"\bauthentik\b", re.IGNORECASE),
    "zitadel": re.compile(r"\bzitadel\b", re.IGNORECASE),
    "facebook": re.compile(r"\bFacebookProvider\b"),
    "discord": re.compile(r"\bDiscordProvider\b"),
}

# Session strategy detection
_RE_SESSION_JWT = re.compile(r"strategy\s*:\s*['\"]jwt['\"]")
_RE_SESSION_DB = re.compile(r"strategy\s*:\s*['\"]database['\"]")

# middleware.ts route-matcher config block: matcher: [...] or matcher: "..."
_RE_MATCHER = re.compile(r"\bmatcher\s*[=:]\s*(\[[\s\S]*?\]|['\"][^'\"]+['\"])")

# Auth config file candidates (tried in order; first match wins)
_AUTH_CONFIG_CANDIDATES = [
    "src/config/auth.ts",
    "src/lib/auth.ts",
    "src/lib/auth/index.ts",
    "auth.ts",
    "src/auth.ts",
    "pages/api/auth/[...nextauth].ts",
    "src/app/api/auth/[...nextauth]/route.ts",
]

_MIDDLEWARE_CANDIDATES = [
    "middleware.ts",
    "src/middleware.ts",
    "middleware.js",
    "src/middleware.js",
]

# SSO provider directories (stem of each .ts file = provider name)
_SSO_PROVIDER_DIRS = (
    "src/libs/next-auth/sso-providers",
    "src/lib/next-auth/sso-providers",
    "src/libs/auth/sso-providers",
)


class AuthDetector:
    """Detect authentication configuration in a Next.js repository.

    Scans auth config files, ``middleware.ts``, and ``(auth)/`` route groups
    to identify providers, session strategy, middleware matchers, and
    protected routes.

    Output::

        {
            "providers": ["next-auth", "github", "azure-ad"],
            "session_strategy": "jwt",
            "middleware_file": "middleware.ts",
            "middleware_matchers": ["/((?!api|_next).*)"],
            "auth_routes": ["login", "signup"],
            "config_file": "src/config/auth.ts"
        }
    """

    def detect(self, repo_path: Path) -> dict:
        """Detect auth configuration under *repo_path*.

        Args:
            repo_path: Absolute path to the repository root.

        Returns:
            Dict with auth metadata. All keys are always present.
        """
        log.info("auth.start", path=str(repo_path))

        providers: set[str] = set()
        session_strategy: str | None = None
        config_file: str | None = None

        # ── Auth config file ─────────────────────────────────────────────────
        for candidate in _AUTH_CONFIG_CANDIDATES:
            cfg_path = repo_path / candidate
            if not cfg_path.exists():
                continue
            try:
                content = cfg_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            config_file = candidate
            for name, pattern in _PROVIDER_PATTERNS.items():
                if pattern.search(content):
                    providers.add(name)
            if _RE_SESSION_JWT.search(content):
                session_strategy = "jwt"
            elif _RE_SESSION_DB.search(content):
                session_strategy = "database"
            break  # only process first matching auth config

        # ── Middleware ────────────────────────────────────────────────────────
        middleware_file, middleware_matchers = self._scan_middleware(repo_path)
        if middleware_file:
            try:
                mw_content = (repo_path / middleware_file).read_text(
                    encoding="utf-8", errors="ignore"
                )
                for name, pattern in _PROVIDER_PATTERNS.items():
                    if pattern.search(mw_content):
                        providers.add(name)
            except OSError:
                pass

        # ── Auth route groups ─────────────────────────────────────────────────
        auth_routes = self._scan_auth_routes(repo_path)

        # ── SSO providers from next-auth sso-providers directory ──────────────
        sso_providers = self._scan_sso_providers(repo_path)

        result: dict = {
            "providers": sorted(providers),
            "session_strategy": session_strategy,
            "middleware_file": middleware_file,
            "middleware_matchers": middleware_matchers,
            "auth_routes": auth_routes,
            "config_file": config_file,
            "sso_providers": sso_providers,
        }
        log.info(
            "auth.done",
            providers=len(providers),
            session=session_strategy,
            auth_routes=len(auth_routes),
            sso_providers=len(sso_providers),
        )
        return result

    # ── private ───────────────────────────────────────────────────────────────

    def _scan_middleware(self, repo_path: Path) -> tuple[str | None, list[str]]:
        """Return (relative path, matcher strings) for the first middleware file found."""
        for candidate in _MIDDLEWARE_CANDIDATES:
            mw_path = repo_path / candidate
            if not mw_path.exists():
                continue
            try:
                content = mw_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            matchers: list[str] = []
            m = _RE_MATCHER.search(content)
            if m:
                raw = m.group(1).strip()
                matchers = re.findall(r"['\"]([^'\"]+)['\"]", raw)

            return candidate, matchers
        return None, []

    def _scan_auth_routes(self, repo_path: Path) -> list[str]:
        """Return sub-route names found inside ``(auth)/`` groups in the app dir."""
        auth_routes: list[str] = []
        for app_base in ("src/app", "app"):
            app_dir = repo_path / app_base
            if not app_dir.is_dir():
                continue
            for auth_group in sorted(app_dir.rglob("(auth)")):
                if auth_group.is_dir():
                    for sub in sorted(auth_group.iterdir()):
                        if sub.is_dir() and not sub.name.startswith(("@", "(")):
                            auth_routes.append(sub.name)
            break  # only process first found app dir
        return auth_routes

    def _scan_sso_providers(self, repo_path: Path) -> list[str]:
        """Return a sorted list of SSO provider names from the sso-providers directory."""
        for candidate in _SSO_PROVIDER_DIRS:
            sso_dir = repo_path / candidate
            if not sso_dir.is_dir():
                continue
            return sorted(
                f.stem
                for f in sso_dir.glob("*.ts")
                if not f.name.startswith(("_", "index"))
            )
        return []
