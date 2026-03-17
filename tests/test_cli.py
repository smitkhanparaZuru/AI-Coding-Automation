from pathlib import Path
from unittest.mock import MagicMock, patch

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

_EMPTY_AST_RESULT = {
    "imports": [],
    "functions": [],
    "exports": [],
    "calls": [],
    "hooks": [],
    "components": [],
    "types": [],
}


def test_index_code_exits_zero(tmp_path: Path) -> None:
    with patch("aica.interfaces.cli.ASTExtractorRunner") as MockRunner, \
         patch("aica.interfaces.cli.ASTWriter") as MockWriter:
        MockRunner.return_value.run.return_value = _EMPTY_AST_RESULT
        MockWriter.return_value.write.return_value = tmp_path / "out.json"
        result = runner.invoke(app, ["index-code", "--path", str(tmp_path)])
    assert result.exit_code == 0


def test_index_code_shows_summary(tmp_path: Path) -> None:
    with patch("aica.interfaces.cli.ASTExtractorRunner") as MockRunner, \
         patch("aica.interfaces.cli.ASTWriter") as MockWriter:
        MockRunner.return_value.run.return_value = _EMPTY_AST_RESULT
        MockWriter.return_value.write.return_value = tmp_path / "out.json"
        result = runner.invoke(app, ["index-code", "--path", str(tmp_path)])
    assert "ast indexing complete" in result.output.lower()


def test_index_code_writes_all_seven_files(tmp_path: Path) -> None:
    mock_result = {
        "imports": [{"file": "a.ts", "source": "react", "import_kind": "external",
                     "default": None, "named": [], "namespace": None,
                     "type_only": False, "side_effect": False, "line": 1}],
        "functions": [{"file": "a.ts", "name": "foo", "kind": "function",
                       "async": False, "params": [], "line": 1, "exported": True}],
        "exports": [{"file": "a.ts", "name": "foo", "local_name": None,
                     "kind": "named", "type_only": False, "source": None, "line": 1}],
        "calls": [{"file": "a.ts", "caller": "foo", "callee": "bar",
                   "callee_object": None, "kind": "call", "line": 2}],
        "hooks": [{"file": "a.tsx", "name": "useState", "caller": "MyComp",
                   "args_count": 1, "line": 5}],
        "components": [{"file": "a.tsx", "name": "MyComp", "kind": "function",
                        "props": [], "exported": True, "line": 1}],
        "types": [{"file": "a.ts", "name": "User", "kind": "interface",
                   "exported": True, "members": ["id"], "line": 3}],
    }
    with patch("aica.interfaces.cli.ASTExtractorRunner") as MockRunner, \
         patch("aica.interfaces.cli.ASTWriter") as MockWriter:
        MockRunner.return_value.run.return_value = mock_result
        mock_writer_instance = MagicMock()
        mock_writer_instance.write.return_value = tmp_path / "out.json"
        MockWriter.return_value = mock_writer_instance
        result = runner.invoke(app, ["index-code", "--path", str(tmp_path)])

    assert result.exit_code == 0
    # 7 files: imports, functions, exports, call_graph, hooks, components, types
    assert mock_writer_instance.write.call_count == 7
    written_filenames = {call.args[2] for call in mock_writer_instance.write.call_args_list}
    assert written_filenames == {
        "imports.json", "functions.json", "exports.json",
        "call_graph.json", "hooks.json", "components.json", "types.json",
    }


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


# ── scan-repo --verbose ────────────────────────────────────────────────────────


def test_scan_repo_verbose_shows_entity_tables(nextjs_repo: Path) -> None:
    result = runner.invoke(app, ["scan-repo", "--path", str(nextjs_repo), "--verbose"])
    assert result.exit_code == 0
    # Per-entity panels rendered by _render_verbose_tables
    assert "Framework" in result.output
    assert "Routes" in result.output
    assert "Components" in result.output


def test_scan_repo_no_verbose_skips_entity_tables(nextjs_repo: Path) -> None:
    result = runner.invoke(app, ["scan-repo", "--path", str(nextjs_repo)])
    assert result.exit_code == 0
    # Summary table present but per-entity framework panel absent
    assert "scan complete" in result.output.lower()
    # The per-entity Framework panel header should NOT appear without --verbose
    assert "Package Manager" not in result.output
