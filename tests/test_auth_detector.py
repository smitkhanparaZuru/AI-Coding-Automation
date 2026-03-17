from __future__ import annotations

from pathlib import Path

import pytest

from aica.repo_intelligence.scanner.detectors.auth import AuthDetector


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def auth_repo(tmp_path: Path) -> Path:
    """Repo with NextAuth config, GitHub+AzureAD providers, JWT session, middleware."""
    # Auth config
    config_dir = tmp_path / "src" / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "auth.ts").write_text(
        "import NextAuth, { AuthOptions } from 'next-auth';\n"
        "import GitHubProvider from 'next-auth/providers/github';\n"
        "import AzureADProvider from 'next-auth/providers/azure-ad';\n"
        "\n"
        "export const authOptions: AuthOptions = {\n"
        "  providers: [\n"
        "    GitHubProvider({ clientId: '', clientSecret: '' }),\n"
        "    AzureADProvider({ clientId: '', clientSecret: '', tenantId: '' }),\n"
        "  ],\n"
        "  session: { strategy: 'jwt' },\n"
        "};\n",
        encoding="utf-8",
    )

    # Middleware
    (tmp_path / "middleware.ts").write_text(
        "export { default } from 'next-auth/middleware';\n"
        "export const config = {\n"
        "  matcher: ['/((?!api|_next/static|_next/image|favicon.ico).*)'],\n"
        "};\n",
        encoding="utf-8",
    )

    # (auth) route group
    auth_group = tmp_path / "src" / "app" / "(main)" / "(auth)"
    for route in ("login", "signup"):
        (auth_group / route).mkdir(parents=True)
        (auth_group / route / "page.tsx").write_text(
            f"export default function {route.title()}Page() {{ return null; }}\n",
            encoding="utf-8",
        )

    return tmp_path


@pytest.fixture()
def clerk_repo(tmp_path: Path) -> Path:
    """Repo using Clerk authentication."""
    lib_dir = tmp_path / "src" / "lib"
    lib_dir.mkdir(parents=True)
    (lib_dir / "auth.ts").write_text(
        "import { ClerkProvider } from '@clerk/nextjs';\n"
        "export const auth = ClerkProvider;\n",
        encoding="utf-8",
    )
    (tmp_path / "middleware.ts").write_text(
        "export { clerkMiddleware as default } from '@clerk/nextjs/server';\n"
        "export const config = { matcher: ['/:path*'] };\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture()
def no_auth_repo(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    return tmp_path


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_detects_next_auth_provider(auth_repo: Path) -> None:
    result = AuthDetector().detect(auth_repo)
    assert "next-auth" in result["providers"]


def test_detects_github_provider(auth_repo: Path) -> None:
    result = AuthDetector().detect(auth_repo)
    assert "github" in result["providers"]


def test_detects_azure_ad_provider(auth_repo: Path) -> None:
    result = AuthDetector().detect(auth_repo)
    assert "azure-ad" in result["providers"]


def test_detects_jwt_session_strategy(auth_repo: Path) -> None:
    result = AuthDetector().detect(auth_repo)
    assert result["session_strategy"] == "jwt"


def test_detects_middleware_file(auth_repo: Path) -> None:
    result = AuthDetector().detect(auth_repo)
    assert result["middleware_file"] == "middleware.ts"


def test_extracts_middleware_matchers(auth_repo: Path) -> None:
    result = AuthDetector().detect(auth_repo)
    assert len(result["middleware_matchers"]) >= 1
    # The matcher content should be a non-empty string
    assert all(isinstance(m, str) and m for m in result["middleware_matchers"])


def test_detects_auth_routes(auth_repo: Path) -> None:
    result = AuthDetector().detect(auth_repo)
    assert set(result["auth_routes"]) == {"login", "signup"}


def test_detects_clerk(clerk_repo: Path) -> None:
    result = AuthDetector().detect(clerk_repo)
    assert "clerk" in result["providers"]


def test_no_auth_returns_defaults(no_auth_repo: Path) -> None:
    result = AuthDetector().detect(no_auth_repo)
    assert result["providers"] == []
    assert result["session_strategy"] is None
    assert result["middleware_file"] is None
    assert result["auth_routes"] == []
    assert result["config_file"] is None


def test_all_keys_always_present(auth_repo: Path) -> None:
    result = AuthDetector().detect(auth_repo)
    for key in ("providers", "session_strategy", "middleware_file",
                "middleware_matchers", "auth_routes", "config_file"):
        assert key in result
