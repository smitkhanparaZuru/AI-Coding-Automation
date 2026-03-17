from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aica.interfaces.cli import app
from aica.repo_intelligence.scanner.core import scan_repository
from aica.repo_intelligence.scanner.detectors.packages import PackageDetector

runner = CliRunner()


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def empty_repo(tmp_path: Path) -> Path:
    """Repo with no package.json."""
    return tmp_path


@pytest.fixture()
def nextjs_pkg_repo(tmp_path: Path) -> Path:
    """Full-stack Next.js repo with ui/database/auth/state deps."""
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "name": "full-stack-app",
                "dependencies": {
                    "next": "^16.0.0",
                    "react": "^18.0.0",
                    "react-dom": "^18.0.0",
                    "next-auth": "^5.0.0",
                    "zustand": "^4.0.0",
                    "@prisma/client": "^5.0.0",
                },
                "devDependencies": {
                    "tailwindcss": "^3.0.0",
                    "prisma": "^5.0.0",
                    "typescript": "^5.0.0",
                },
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture()
def react_only_repo(tmp_path: Path) -> Path:
    """Repo with react but no other full-stack packages."""
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "name": "react-app",
                "dependencies": {
                    "react": "^18.0.0",
                    "react-dom": "^18.0.0",
                },
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture()
def corrupt_json_repo(tmp_path: Path) -> Path:
    """Repo with a malformed package.json."""
    (tmp_path / "package.json").write_text("{not valid json", encoding="utf-8")
    return tmp_path


@pytest.fixture()
def devdeps_repo(tmp_path: Path) -> Path:
    """Repo where auth / state / ui libraries live in devDependencies only."""
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "name": "devdeps-app",
                "dependencies": {"next": "^16.0.0"},
                "devDependencies": {
                    "tailwindcss": "^3.0.0",
                    "@clerk/nextjs": "^4.0.0",
                    "jotai": "^2.0.0",
                },
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture()
def scoped_ui_repo(tmp_path: Path) -> Path:
    """Repo with multiple @radix-ui/* packages (prefix-matching test)."""
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "name": "radix-app",
                "dependencies": {
                    "next": "^16.0.0",
                    "@radix-ui/react-dialog": "^1.0.0",
                    "@radix-ui/react-dropdown-menu": "^2.0.0",
                    "@radix-ui/react-tooltip": "^1.0.0",
                },
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture()
def peer_deps_repo(tmp_path: Path) -> Path:
    """Repo where a dep lives only in peerDependencies."""
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "name": "peer-deps-app",
                "dependencies": {"vue": "^3.0.0"},
                "peerDependencies": {"mongoose": "^8.0.0"},
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


# ── Unit tests — missing / corrupt file ───────────────────────────────────────


def test_missing_package_json_returns_empty(empty_repo: Path) -> None:
    result = PackageDetector().detect(empty_repo)
    assert result["framework"] is None
    assert result["ui"] == []
    assert result["database"] == []
    assert result["auth"] == []
    assert result["state"] == []


def test_corrupt_json_returns_empty(corrupt_json_repo: Path) -> None:
    result = PackageDetector().detect(corrupt_json_repo)
    assert result["framework"] is None
    assert result["ui"] == []
    assert result["database"] == []


# ── Unit tests — framework detection ─────────────────────────────────────────


def test_framework_next_wins_over_react(nextjs_pkg_repo: Path) -> None:
    """next should be picked before react because it has higher catalog priority."""
    result = PackageDetector().detect(nextjs_pkg_repo)
    assert result["framework"] == "next"


def test_framework_react_only(react_only_repo: Path) -> None:
    result = PackageDetector().detect(react_only_repo)
    assert result["framework"] == "react"


def test_framework_none_when_no_match(empty_repo: Path) -> None:
    result = PackageDetector().detect(empty_repo)
    assert result["framework"] is None


def test_alternate_frameworks() -> None:
    """Verify each catalog framework is detected when it is the only one present."""
    frameworks = ["vue", "nuxt", "svelte", "remix", "astro", "gatsby"]
    for fw in frameworks:
        detector = PackageDetector()
        # Simulate reading deps by calling _read_deps internals via detect()
        # We need a tmp directory with a package.json — use a simple inline fixture.
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "package.json"
            pkg.write_text(json.dumps({"dependencies": {fw: "^1.0.0"}}), encoding="utf-8")
            result = detector.detect(Path(tmp))
        assert result["framework"] == fw, f"Expected '{fw}', got {result['framework']}"


# ── Unit tests — UI detection ─────────────────────────────────────────────────


def test_ui_tailwindcss(nextjs_pkg_repo: Path) -> None:
    result = PackageDetector().detect(nextjs_pkg_repo)
    assert "tailwindcss" in result["ui"]


def test_ui_radix_prefix_collapsed(scoped_ui_repo: Path) -> None:
    """All @radix-ui/* packages should collapse to a single '@radix-ui' entry."""
    result = PackageDetector().detect(scoped_ui_repo)
    assert result["ui"] == ["@radix-ui"]


def test_ui_no_entries_when_none_installed(react_only_repo: Path) -> None:
    result = PackageDetector().detect(react_only_repo)
    assert result["ui"] == []


# ── Unit tests — database detection ──────────────────────────────────────────


def test_database_prisma(nextjs_pkg_repo: Path) -> None:
    result = PackageDetector().detect(nextjs_pkg_repo)
    # Both 'prisma' (devDeps) and '@prisma/client' (deps) are installed
    assert "@prisma/client" in result["database"]
    assert "prisma" in result["database"]


def test_database_none_when_no_match(react_only_repo: Path) -> None:
    result = PackageDetector().detect(react_only_repo)
    assert result["database"] == []


# ── Unit tests — auth detection ───────────────────────────────────────────────


def test_auth_next_auth(nextjs_pkg_repo: Path) -> None:
    result = PackageDetector().detect(nextjs_pkg_repo)
    assert "next-auth" in result["auth"]


def test_auth_clerk_from_devdeps(devdeps_repo: Path) -> None:
    result = PackageDetector().detect(devdeps_repo)
    assert "@clerk/nextjs" in result["auth"]


def test_auth_none_when_no_match(react_only_repo: Path) -> None:
    result = PackageDetector().detect(react_only_repo)
    assert result["auth"] == []


# ── Unit tests — state detection ──────────────────────────────────────────────


def test_state_zustand(nextjs_pkg_repo: Path) -> None:
    result = PackageDetector().detect(nextjs_pkg_repo)
    assert "zustand" in result["state"]


def test_state_jotai_from_devdeps(devdeps_repo: Path) -> None:
    result = PackageDetector().detect(devdeps_repo)
    assert "jotai" in result["state"]


def test_state_none_when_no_match(react_only_repo: Path) -> None:
    result = PackageDetector().detect(react_only_repo)
    assert result["state"] == []


# ── Unit tests — peerDependencies ────────────────────────────────────────────


def test_peer_deps_included(peer_deps_repo: Path) -> None:
    result = PackageDetector().detect(peer_deps_repo)
    assert "mongoose" in result["database"]
    assert result["framework"] == "vue"


# ── Unit tests — output schema completeness ───────────────────────────────────


def test_all_keys_present_even_when_empty(react_only_repo: Path) -> None:
    result = PackageDetector().detect(react_only_repo)
    for key in ("framework", "ui", "database", "auth", "state"):
        assert key in result, f"Missing key: {key}"


def test_array_values_are_sorted(nextjs_pkg_repo: Path) -> None:
    result = PackageDetector().detect(nextjs_pkg_repo)
    for key in ("ui", "database", "auth", "state"):
        values = result[key]
        assert values == sorted(values), f"{key} is not sorted: {values}"


# ── Integration — scan_repository includes 'packages' key ────────────────────


def test_scan_repository_includes_packages_key(nextjs_pkg_repo: Path) -> None:
    data = scan_repository(str(nextjs_pkg_repo))
    assert "packages" in data
    pkgs = data["packages"]
    assert pkgs["framework"] == "next"
    assert "tailwindcss" in pkgs["ui"]
    assert "next-auth" in pkgs["auth"]
    assert "zustand" in pkgs["state"]


def test_scan_repository_packages_key_present_on_empty(empty_repo: Path) -> None:
    # Give the repo a package.json so scan_repository doesn't fail elsewhere
    (empty_repo / "package.json").write_text(
        json.dumps({"name": "empty"}), encoding="utf-8"
    )
    data = scan_repository(str(empty_repo))
    assert "packages" in data
    pkgs = data["packages"]
    assert pkgs["framework"] is None


# ── CLI — scan-next writes packages.json ──────────────────────────────────────


def test_scan_next_writes_packages_json(nextjs_pkg_repo: Path) -> None:
    result = runner.invoke(app, ["scan-next", "--path", str(nextjs_pkg_repo)])
    assert result.exit_code == 0, result.output
    pkg_file = nextjs_pkg_repo / ".repo_intelligence" / "packages.json"
    assert pkg_file.exists(), "packages.json was not created"
    data = json.loads(pkg_file.read_text(encoding="utf-8"))
    assert data["framework"] == "next"
    assert isinstance(data["ui"], list)
    assert isinstance(data["database"], list)
    assert isinstance(data["auth"], list)
    assert isinstance(data["state"], list)


def test_scan_next_packages_json_schema(nextjs_pkg_repo: Path) -> None:
    runner.invoke(app, ["scan-next", "--path", str(nextjs_pkg_repo)])
    pkg_file = nextjs_pkg_repo / ".repo_intelligence" / "packages.json"
    data = json.loads(pkg_file.read_text(encoding="utf-8"))
    for key in ("framework", "ui", "database", "auth", "state"):
        assert key in data, f"Missing key '{key}' in packages.json"
    assert "tailwindcss" in data["ui"]
    assert "next-auth" in data["auth"]
    assert "zustand" in data["state"]
