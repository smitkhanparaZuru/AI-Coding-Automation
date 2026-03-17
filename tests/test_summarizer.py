from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aica.interfaces.cli import app
from aica.repo_intelligence.scanner.summarizer import RepoSummaryGenerator
from aica.repo_intelligence.scanner.writers import OutputWriter

runner = CliRunner()

_OUTPUT_DIR = ".repo_intelligence"


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _write_artifacts(base: Path, *, routes: list, components: list, services: list, database: list, structure: dict) -> None:
    """Write all five scanner artifact files into ``{base}/.repo_intelligence/``."""
    artifact_dir = base / _OUTPUT_DIR
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "routes.json").write_text(json.dumps(routes), encoding="utf-8")
    (artifact_dir / "components.json").write_text(json.dumps(components), encoding="utf-8")
    (artifact_dir / "services.json").write_text(json.dumps(services), encoding="utf-8")
    (artifact_dir / "database.json").write_text(json.dumps(database), encoding="utf-8")
    (artifact_dir / "structure.json").write_text(json.dumps(structure), encoding="utf-8")


@pytest.fixture()
def populated_repo(tmp_path: Path) -> Path:
    """Repo with all five scanner artifact files pre-populated."""
    _write_artifacts(
        tmp_path,
        routes=[
            {"route": "/", "type": "page", "file": "src/app/page.tsx", "methods": []},
            {"route": "/api/users", "type": "api", "file": "src/app/api/users/route.ts", "methods": ["GET", "POST"]},
        ],
        components=[
            {"name": "UserCard", "file": "src/components/UserCard.tsx", "props": ["userId"]},
            {"name": "Button", "file": "src/components/Button.tsx", "props": []},
        ],
        services=[
            {"service": "AuthService", "file": "src/services/auth.ts", "exported_functions": ["login"]},
        ],
        database=[
            {"orm": "Prisma", "schema": "prisma/schema.prisma", "models": [{"name": "User", "fields": ["id", "email"]}]},
        ],
        structure={"framework": "Next.js", "language": "TypeScript", "app_router": True},
    )
    return tmp_path


@pytest.fixture()
def nextjs_scan_repo(tmp_path: Path) -> Path:
    """Minimal Next.js repo suitable for the full scan-next CLI command."""
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"next": "^16.0.0", "react": "^18.0.0"}}),
        encoding="utf-8",
    )
    (tmp_path / "tsconfig.json").write_text(
        json.dumps({"compilerOptions": {"target": "ES2022"}}),
        encoding="utf-8",
    )
    app_dir = tmp_path / "src" / "app"
    app_dir.mkdir(parents=True)
    (app_dir / "page.tsx").write_text(
        "export default function Page() { return null; }\n", encoding="utf-8"
    )
    return tmp_path


# ── RepoSummaryGenerator.generate (disk-based) ────────────────────────────────


def test_generate_reads_json_files(populated_repo: Path) -> None:
    summary = RepoSummaryGenerator().generate(populated_repo)

    assert summary["framework"] == "Next.js"
    assert summary["language"] == "TypeScript"
    assert summary["routes_count"] == 2
    assert summary["components_count"] == 2
    assert summary["services_count"] == 1
    assert summary["database"] == "Prisma"


def test_generate_writes_repo_summary_json(populated_repo: Path) -> None:
    RepoSummaryGenerator().generate(populated_repo)

    out_file = populated_repo / _OUTPUT_DIR / "repo_summary.json"
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["framework"] == "Next.js"
    assert data["routes_count"] == 2


def test_generate_missing_files_graceful(tmp_path: Path) -> None:
    """All artifact files absent → defaults to zeros and null."""
    (tmp_path / _OUTPUT_DIR).mkdir()

    summary = RepoSummaryGenerator().generate(tmp_path)

    assert summary["framework"] == "unknown"
    assert summary["language"] == "unknown"
    assert summary["routes_count"] == 0
    assert summary["components_count"] == 0
    assert summary["services_count"] == 0
    assert summary["database"] is None


def test_generate_missing_database_file(tmp_path: Path) -> None:
    """Missing database.json → database field is null, others still work."""
    artifact_dir = tmp_path / _OUTPUT_DIR
    artifact_dir.mkdir()
    (artifact_dir / "routes.json").write_text(json.dumps([{"route": "/"}]), encoding="utf-8")
    (artifact_dir / "components.json").write_text(json.dumps([]), encoding="utf-8")
    (artifact_dir / "services.json").write_text(json.dumps([]), encoding="utf-8")
    (artifact_dir / "structure.json").write_text(
        json.dumps({"framework": "Next.js", "language": "TypeScript"}), encoding="utf-8"
    )
    # database.json intentionally not created

    summary = RepoSummaryGenerator().generate(tmp_path)

    assert summary["routes_count"] == 1
    assert summary["database"] is None


# ── RepoSummaryGenerator.from_scan_data (in-memory) ──────────────────────────


def test_from_scan_data_classmethod() -> None:
    scan_data = {
        "framework": "Next.js",
        "language": "TypeScript",
        "routes": [{"route": "/"}, {"route": "/about"}, {"route": "/api/users"}],
        "components": [{"name": "A"}, {"name": "B"}, {"name": "C"}, {"name": "D"}],
        "services": [{"service": "Auth"}, {"service": "Email"}],
        "database": [{"orm": "Drizzle"}],
    }

    summary = RepoSummaryGenerator.from_scan_data(scan_data)

    assert summary["framework"] == "Next.js"
    assert summary["language"] == "TypeScript"
    assert summary["routes_count"] == 3
    assert summary["components_count"] == 4
    assert summary["services_count"] == 2
    assert summary["database"] == "Drizzle"


def test_from_scan_data_no_database() -> None:
    scan_data = {
        "framework": "React",
        "language": "JavaScript",
        "routes": [],
        "components": [{"name": "App"}],
        "services": [],
        "database": [],
    }

    summary = RepoSummaryGenerator.from_scan_data(scan_data)

    assert summary["database"] is None
    assert summary["components_count"] == 1


def test_from_scan_data_missing_keys() -> None:
    """Empty dict should produce safe defaults without raising."""
    summary = RepoSummaryGenerator.from_scan_data({})

    assert summary["framework"] == "unknown"
    assert summary["language"] == "unknown"
    assert summary["routes_count"] == 0
    assert summary["components_count"] == 0
    assert summary["services_count"] == 0
    assert summary["database"] is None


def test_from_scan_data_summary_json_is_null_not_string(tmp_path: Path) -> None:
    """JSON serialisation: database=None must appear as JSON null, not the string 'null'."""
    scan_data = {"framework": "Vue", "language": "JavaScript", "routes": [], "components": [], "services": [], "database": []}
    summary = RepoSummaryGenerator.from_scan_data(scan_data)

    out_path = OutputWriter().write(summary, tmp_path, "repo_summary.json")
    raw = out_path.read_text(encoding="utf-8")
    parsed = json.loads(raw)

    assert parsed["database"] is None
    assert '"null"' not in raw  # must not be serialised as the string "null"


# ── CLI: summarize-repo command ───────────────────────────────────────────────


def test_summarize_repo_cli_exits_zero(populated_repo: Path) -> None:
    result = runner.invoke(app, ["summarize-repo", "--path", str(populated_repo)])
    assert result.exit_code == 0


def test_summarize_repo_cli_shows_summary_panel(populated_repo: Path) -> None:
    result = runner.invoke(app, ["summarize-repo", "--path", str(populated_repo)])
    assert "Next.js" in result.output
    assert "TypeScript" in result.output
    assert "Prisma" in result.output


def test_summarize_repo_cli_writes_file(populated_repo: Path) -> None:
    runner.invoke(app, ["summarize-repo", "--path", str(populated_repo)])
    out_file = populated_repo / _OUTPUT_DIR / "repo_summary.json"
    assert out_file.exists()


def test_summarize_repo_cli_exits_one_when_no_artifact_dir(tmp_path: Path) -> None:
    """Should exit with code 1 when .repo_intelligence/ does not exist."""
    result = runner.invoke(app, ["summarize-repo", "--path", str(tmp_path)])
    assert result.exit_code == 1
    assert ".repo_intelligence" in result.output or "scan-next" in result.output


# ── CLI: scan-next auto-generates repo_summary.json ──────────────────────────


def test_scan_next_auto_generates_summary(nextjs_scan_repo: Path) -> None:
    result = runner.invoke(app, ["scan-next", "--path", str(nextjs_scan_repo)])

    assert result.exit_code == 0
    summary_file = nextjs_scan_repo / _OUTPUT_DIR / "repo_summary.json"
    assert summary_file.exists(), "scan-next must auto-generate repo_summary.json"


def test_scan_next_summary_has_correct_shape(nextjs_scan_repo: Path) -> None:
    runner.invoke(app, ["scan-next", "--path", str(nextjs_scan_repo)])

    summary_file = nextjs_scan_repo / _OUTPUT_DIR / "repo_summary.json"
    data = json.loads(summary_file.read_text(encoding="utf-8"))

    assert "framework" in data
    assert "language" in data
    assert "routes_count" in data
    assert "components_count" in data
    assert "services_count" in data
    assert "database" in data
    assert data["framework"] == "Next.js"
    assert data["language"] == "TypeScript"
