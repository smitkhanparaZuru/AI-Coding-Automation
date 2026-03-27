from __future__ import annotations

import json
from pathlib import Path

from aica.repo_intelligence.scanner.incremental import run_incremental_scan


def _write_json(path: Path, data: list | dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _read_json(path: Path) -> list | dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_run_incremental_scan_merges_file_owned_artifact(tmp_path: Path) -> None:
    repo_path = tmp_path

    card_file = repo_path / "src" / "components" / "Card.tsx"
    card_file.parent.mkdir(parents=True, exist_ok=True)
    card_file.write_text(
        "export function NewCard(props: NewCardProps) { return null }\n"
        "interface NewCardProps { title: string }\n",
        encoding="utf-8",
    )

    other_file = repo_path / "src" / "components" / "Other.tsx"
    other_file.write_text("export function Other() { return null }\n", encoding="utf-8")

    output_dir = repo_path / ".repo_intelligence"
    _write_json(
        output_dir / "components.json",
        [
            {"name": "OldCard", "file": "src/components/Card.tsx", "props": []},
            {"name": "KeepMe", "file": "src/components/Other.tsx", "props": []},
        ],
    )

    run_incremental_scan(repo_path, ["src/components/Card.tsx"])

    components = _read_json(output_dir / "components.json")
    names = sorted(entry["name"] for entry in components)

    assert "OldCard" not in names
    assert "NewCard" in names
    assert "KeepMe" in names


def test_run_incremental_scan_merges_path_owned_artifact(tmp_path: Path) -> None:
    repo_path = tmp_path

    build_dir = repo_path / "scripts" / "build"
    keep_dir = repo_path / "scripts" / "keep"
    build_dir.mkdir(parents=True, exist_ok=True)
    keep_dir.mkdir(parents=True, exist_ok=True)

    (build_dir / "index.ts").write_text("export const x = 1\n", encoding="utf-8")
    (build_dir / "new.ts").write_text("export const y = 2\n", encoding="utf-8")
    (keep_dir / "index.ts").write_text("export const z = 3\n", encoding="utf-8")

    output_dir = repo_path / ".repo_intelligence"
    _write_json(
        output_dir / "scripts.json",
        [
            {
                "name": "build",
                "path": "scripts/build",
                "type": "dir",
                "files": ["index.ts"],
            },
            {
                "name": "keep",
                "path": "scripts/keep",
                "type": "dir",
                "files": ["index.ts"],
            },
        ],
    )

    run_incremental_scan(repo_path, ["scripts/build/new.ts"])

    scripts = _read_json(output_dir / "scripts.json")
    indexed = {entry["path"]: entry for entry in scripts}

    assert indexed["scripts/keep"]["files"] == ["index.ts"]
    assert "new.ts" in indexed["scripts/build"]["files"]


def test_run_incremental_scan_removes_deleted_file_owned_entries(tmp_path: Path) -> None:
    repo_path = tmp_path

    output_dir = repo_path / ".repo_intelligence"
    _write_json(
        output_dir / "hooks.json",
        [{"name": "useRemoved", "file": "src/hooks/useRemoved.ts", "parameters": []}],
    )

    run_incremental_scan(repo_path, ["src/hooks/useRemoved.ts"])

    hooks = _read_json(output_dir / "hooks.json")
    assert hooks == []
