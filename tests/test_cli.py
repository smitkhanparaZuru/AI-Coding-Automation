from pathlib import Path

from typer.testing import CliRunner

from aica.interfaces.cli import app

runner = CliRunner()


# ── existing ──────────────────────────────────────────────────────────────────


def test_status_exits_zero() -> None:
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0


def test_status_output_contains_version() -> None:
    result = runner.invoke(app, ["status"])
    assert "0.1.0" in result.output


def test_status_output_contains_modules() -> None:
    result = runner.invoke(app, ["status"])
    for module in ["core", "memory", "tools", "execution", "config"]:
        assert module in result.output


# ── scan-repo ─────────────────────────────────────────────────────────────────


def test_scan_repo_exits_zero(nextjs_repo: Path) -> None:
    result = runner.invoke(app, ["scan-repo", "--path", str(nextjs_repo)])
    assert result.exit_code == 0


def test_scan_repo_shows_summary_panel(nextjs_repo: Path) -> None:
    result = runner.invoke(app, ["scan-repo", "--path", str(nextjs_repo)])
    assert "scan complete" in result.output.lower()


def test_scan_repo_shows_routes_count(nextjs_repo: Path) -> None:
    result = runner.invoke(app, ["scan-repo", "--path", str(nextjs_repo)])
    assert "Routes detected" in result.output


def test_scan_repo_shows_components_count(nextjs_repo: Path) -> None:
    result = runner.invoke(app, ["scan-repo", "--path", str(nextjs_repo)])
    assert "Components detected" in result.output


def test_scan_repo_writes_intelligence_files(nextjs_repo: Path) -> None:
    runner.invoke(app, ["scan-repo", "--path", str(nextjs_repo)])
    artifact_dir = nextjs_repo / ".repo_intelligence"
    assert (artifact_dir / "structure.json").is_file()
    assert (artifact_dir / "repo_summary.json").is_file()


def test_scan_repo_error_on_missing_path() -> None:
    result = runner.invoke(app, ["scan-repo", "--path", "/nonexistent/path/that/does/not/exist"])
    assert result.exit_code == 1


# ── index-code ────────────────────────────────────────────────────────────────


def test_index_code_exits_zero() -> None:
    result = runner.invoke(app, ["index-code", "--path", "."])
    assert result.exit_code == 0


def test_index_code_creates_output() -> None:
    result = runner.invoke(app, ["index-code", "--path", "."])
    assert "index.json" in result.output


# ── plan-task ─────────────────────────────────────────────────────────────────


def test_plan_task_exits_zero() -> None:
    result = runner.invoke(app, ["plan-task", "refactor auth module"])
    assert result.exit_code == 0


def test_plan_task_shows_steps() -> None:
    result = runner.invoke(app, ["plan-task", "refactor auth module"])
    assert "Implement" in result.output


# ── run-task ──────────────────────────────────────────────────────────────────


def test_run_task_exits_zero() -> None:
    result = runner.invoke(app, ["run-task", "echo hello"])
    assert result.exit_code == 0


def test_run_task_shows_stdout() -> None:
    result = runner.invoke(app, ["run-task", "echo hello"])
    assert "hello" in result.output



def test_status_output_contains_config_fields() -> None:
    result = runner.invoke(app, ["status"])
    assert "AICA" in result.output
    assert "Log Level" in result.output
    assert "Workspace Dir" in result.output
