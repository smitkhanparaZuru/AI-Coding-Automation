from __future__ import annotations

from pathlib import Path

import pytest

from aica.repo_intelligence.scanner.detectors.server_modules import ServerModulesDetector


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def server_modules_repo(tmp_path: Path) -> Path:
    """Repo with a src/server/modules/ directory containing two modules."""
    modules_dir = tmp_path / "src" / "server" / "modules"

    # AgentRuntime module
    ar_dir = modules_dir / "AgentRuntime"
    ar_dir.mkdir(parents=True)
    (ar_dir / "index.ts").write_text(
        "export class AgentRuntime {}\n"
        "export function createAgentRuntime() {}\n",
        encoding="utf-8",
    )
    (ar_dir / "types.ts").write_text(
        "export interface AgentConfig {}\n",
        encoding="utf-8",
    )

    # KeyVaultsEncrypt module
    kv_dir = modules_dir / "KeyVaultsEncrypt"
    kv_dir.mkdir(parents=True)
    (kv_dir / "index.ts").write_text(
        "export const encrypt = (data: string) => data;\n"
        "export const decrypt = (data: string) => data;\n",
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture()
def empty_server_modules_repo(tmp_path: Path) -> Path:
    """Repo without a server modules directory."""
    (tmp_path / "src").mkdir()
    return tmp_path


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_detect_two_modules(server_modules_repo: Path) -> None:
    results = ServerModulesDetector().detect(server_modules_repo)
    assert len(results) == 2
    names = {r["module"] for r in results}
    assert names == {"AgentRuntime", "KeyVaultsEncrypt"}


def test_module_path_is_relative(server_modules_repo: Path) -> None:
    results = ServerModulesDetector().detect(server_modules_repo)
    ar = next(r for r in results if r["module"] == "AgentRuntime")
    assert ar["path"] == "src/server/modules/AgentRuntime"


def test_module_files_listed(server_modules_repo: Path) -> None:
    results = ServerModulesDetector().detect(server_modules_repo)
    ar = next(r for r in results if r["module"] == "AgentRuntime")
    assert "index.ts" in ar["files"]
    assert "types.ts" in ar["files"]


def test_exports_extracted(server_modules_repo: Path) -> None:
    results = ServerModulesDetector().detect(server_modules_repo)
    ar = next(r for r in results if r["module"] == "AgentRuntime")
    assert "AgentRuntime" in ar["exports"]
    assert "createAgentRuntime" in ar["exports"]


def test_key_vaults_exports(server_modules_repo: Path) -> None:
    results = ServerModulesDetector().detect(server_modules_repo)
    kv = next(r for r in results if r["module"] == "KeyVaultsEncrypt")
    assert "encrypt" in kv["exports"]
    assert "decrypt" in kv["exports"]


def test_no_modules_dir_returns_empty(empty_server_modules_repo: Path) -> None:
    results = ServerModulesDetector().detect(empty_server_modules_repo)
    assert results == []


def test_hidden_dirs_skipped(tmp_path: Path) -> None:
    """Directories starting with '.' or '_' should be skipped."""
    modules_dir = tmp_path / "src" / "server" / "modules"
    (modules_dir / ".hidden").mkdir(parents=True)
    (modules_dir / "_private").mkdir(parents=True)
    (modules_dir / "Public").mkdir(parents=True)
    (modules_dir / "Public" / "index.ts").write_text("export const x = 1;\n", encoding="utf-8")

    results = ServerModulesDetector().detect(tmp_path)
    assert len(results) == 1
    assert results[0]["module"] == "Public"
