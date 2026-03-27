"""Tests for aica/memory/graph_store/import_builder.py — Sub-Plan 4.4"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

from aica.memory.graph_store.import_builder import (
    BATCH_SIZE,
    insert_import_edges,
    resolve_import_path,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client() -> MagicMock:
    """A mock Neo4jClient with run_query stubbed out."""
    mock = MagicMock()
    mock.run_query = MagicMock(return_value=[])
    return mock


# ---------------------------------------------------------------------------
# Sample import factory
# ---------------------------------------------------------------------------


def _imp(
    source: str,
    file: str = "src/app.ts",
    import_kind: str | None = None,
) -> dict:
    return {
        "file": file,
        "source": source,
        "import_kind": import_kind or _auto_kind(source),
        "default": None,
        "named": [],
        "namespace": None,
        "type_only": False,
        "side_effect": False,
        "line": 1,
    }


def _auto_kind(source: str) -> str:
    if source.startswith("./") or source.startswith("../"):
        return "relative"
    if source.startswith("@") or source.startswith("~"):
        return "alias"
    return "external"


# ---------------------------------------------------------------------------
# TestResolveImportPath — real filesystem via tmp_path
# ---------------------------------------------------------------------------


class TestResolveImportPath:
    def test_external_returns_none(self, tmp_path: Path) -> None:
        assert resolve_import_path("react", "src/app.ts", tmp_path) is None

    def test_relative_resolves_ts_extension(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "utils.ts").touch()
        result = resolve_import_path("./utils", "src/app.ts", tmp_path)
        assert result == "src/utils.ts"

    def test_relative_resolves_tsx_extension(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "Button.tsx").touch()
        result = resolve_import_path("./Button", "src/app.ts", tmp_path)
        assert result == "src/Button.tsx"

    def test_relative_resolves_index_file(self, tmp_path: Path) -> None:
        comps = tmp_path / "src" / "components"
        comps.mkdir(parents=True)
        (comps / "index.ts").touch()
        result = resolve_import_path("./components", "src/app.ts", tmp_path)
        assert result == "src/components/index.ts"

    def test_relative_parent_traversal(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "shared.ts").touch()
        (tmp_path / "src" / "app").mkdir()
        result = resolve_import_path("../shared", "src/app/page.ts", tmp_path)
        assert result == "src/shared.ts"

    def test_relative_unresolvable_returns_none(self, tmp_path: Path) -> None:
        (tmp_path / "src").mkdir()
        result = resolve_import_path("./nonexistent", "src/app.ts", tmp_path)
        assert result is None

    def test_alias_at_slash_resolves(self, tmp_path: Path) -> None:
        utils = tmp_path / "src" / "utils"
        utils.mkdir(parents=True)
        (utils / "foo.ts").touch()
        result = resolve_import_path("@/utils/foo", "src/app.ts", tmp_path)
        assert result == "src/utils/foo.ts"

    def test_alias_tilde_slash_resolves(self, tmp_path: Path) -> None:
        utils = tmp_path / "src" / "utils"
        utils.mkdir(parents=True)
        (utils / "bar.ts").touch()
        result = resolve_import_path("~/utils/bar", "src/app.ts", tmp_path)
        assert result == "src/utils/bar.ts"

    def test_alias_scoped_package_returns_none(self, tmp_path: Path) -> None:
        # @lobehub/ui has no matching file on disk; treated as unresolvable
        result = resolve_import_path("@lobehub/ui", "src/app.ts", tmp_path)
        assert result is None

    def test_path_traversal_blocked(self, tmp_path: Path) -> None:
        # A specifier that resolves to outside repo_root must return None
        result = resolve_import_path(
            "../../../../etc/passwd", "src/a.ts", tmp_path
        )
        assert result is None

    def test_prefers_ts_over_tsx(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "util.ts").touch()
        (src / "util.tsx").touch()
        result = resolve_import_path("./util", "src/app.ts", tmp_path)
        assert result == "src/util.ts"

    def test_resolves_bare_path_with_extension(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "styles.css").touch()
        result = resolve_import_path("./styles.css", "src/app.ts", tmp_path)
        assert result == "src/styles.css"


# ---------------------------------------------------------------------------
# TestInsertImportEdges — mock client
# ---------------------------------------------------------------------------


class TestInsertImportEdges:
    def test_empty_input_returns_zero(self, client: MagicMock, tmp_path: Path) -> None:
        result = insert_import_edges(client, [], tmp_path)
        assert result == 0
        client.run_query.assert_not_called()

    def test_external_imports_merge_module_nodes(
        self, client: MagicMock, tmp_path: Path
    ) -> None:
        imports = [_imp("react", file="src/app.ts", import_kind="external")]
        insert_import_edges(client, imports, tmp_path)
        assert client.run_query.call_count == 1
        cypher = client.run_query.call_args[0][0]
        assert "Module" in cypher
        assert "IMPORTS" in cypher
        assert "File" in cypher

    def test_internal_imports_merge_file_to_file(
        self, client: MagicMock, tmp_path: Path
    ) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "utils.ts").touch()
        imports = [_imp("./utils", file="src/app.ts", import_kind="relative")]
        insert_import_edges(client, imports, tmp_path)
        assert client.run_query.call_count == 1
        cypher = client.run_query.call_args[0][0]
        # Two File MERGEs + one IMPORTS relationship
        assert cypher.count("MERGE") >= 3
        assert "IMPORTS" in cypher
        assert "File" in cypher

    def test_unresolvable_relative_skipped(
        self, client: MagicMock, tmp_path: Path
    ) -> None:
        # No file created → resolve_import_path returns None
        imports = [_imp("./missing", file="src/app.ts", import_kind="relative")]
        result = insert_import_edges(client, imports, tmp_path)
        assert result == 0
        client.run_query.assert_not_called()

    def test_deduplicates_external_imports(
        self, client: MagicMock, tmp_path: Path
    ) -> None:
        imports = [
            _imp("react", file="src/app.ts", import_kind="external"),
            _imp("react", file="src/app.ts", import_kind="external"),  # duplicate
        ]
        result = insert_import_edges(client, imports, tmp_path)
        # Only 1 unique (file, module) pair → 1 row in batch → 1 query call
        assert result == 1
        assert client.run_query.call_count == 1
        params = client.run_query.call_args[0][1]
        assert len(params["batch"]) == 1

    def test_returns_total_edge_count(
        self, client: MagicMock, tmp_path: Path
    ) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "utils.ts").touch()
        imports = [
            _imp("react", file="src/app.ts", import_kind="external"),
            _imp("./utils", file="src/app.ts", import_kind="relative"),
        ]
        result = insert_import_edges(client, imports, tmp_path)
        assert result == 2

    def test_batching_at_boundary_external(
        self, client: MagicMock, tmp_path: Path
    ) -> None:
        # BATCH_SIZE + 1 unique external imports → 2 run_query calls
        imports = [
            _imp(f"pkg-{i}", file=f"src/file_{i}.ts", import_kind="external")
            for i in range(BATCH_SIZE + 1)
        ]
        insert_import_edges(client, imports, tmp_path)
        assert client.run_query.call_count == 2

    def test_batching_at_boundary_internal(
        self, client: MagicMock, tmp_path: Path
    ) -> None:
        # BATCH_SIZE + 1 unique internal imports → 2 run_query calls
        src = tmp_path / "src"
        src.mkdir()
        imports = []
        for i in range(BATCH_SIZE + 1):
            target = src / f"util_{i}.ts"
            target.touch()
            imports.append(
                _imp(f"./util_{i}", file="src/app.ts", import_kind="relative")
            )
        insert_import_edges(client, imports, tmp_path)
        assert client.run_query.call_count == 2

    def test_mixed_imports_two_query_groups(
        self, client: MagicMock, tmp_path: Path
    ) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "helper.ts").touch()
        imports = [
            _imp("lodash", file="src/app.ts", import_kind="external"),
            _imp("./helper", file="src/app.ts", import_kind="relative"),
        ]
        insert_import_edges(client, imports, tmp_path)
        # One external batch + one internal batch = 2 queries
        assert client.run_query.call_count == 2

    def test_import_kind_inferred_when_missing(
        self, client: MagicMock, tmp_path: Path
    ) -> None:
        # Dict has no import_kind key — should be derived from source
        imp = {
            "file": "src/app.ts",
            "source": "react",
            "default": None,
            "named": [],
            "type_only": False,
            "side_effect": False,
            "line": 1,
        }
        result = insert_import_edges(client, [imp], tmp_path)
        assert result == 1
        cypher = client.run_query.call_args[0][0]
        assert "Module" in cypher
