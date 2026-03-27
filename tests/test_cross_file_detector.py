from __future__ import annotations

import pytest

from aica.memory.graph_store.cross_file_detector import (
    detect_all_affected_files,
    find_files_calling,
    find_files_importing,
)


class TestFindFilesImporting:
    """Tests for find_files_importing function."""

    def test_single_importer(self) -> None:
        """Test finding a single file that imports a changed file."""
        changed = ["src/utils.ts"]
        imports = [
            {"file": "src/auth.ts", "from": "src/utils.ts", "import": "validateEmail"},
            {"file": "src/api.ts", "from": "react", "import": "useState"},
        ]

        importers = find_files_importing(changed, imports)

        assert importers == {"src/auth.ts"}

    def test_multiple_importers(self) -> None:
        """Test finding multiple files importing a changed file."""
        changed = ["src/utils.ts"]
        imports = [
            {"file": "src/auth.ts", "from": "src/utils.ts"},
            {"file": "src/api.ts", "from": "src/utils.ts"},
            {"file": "src/components.ts", "from": "react"},
        ]

        importers = find_files_importing(changed, imports)

        assert importers == {"src/auth.ts", "src/api.ts"}

    def test_no_importers(self) -> None:
        """Test when changed file has no importers."""
        changed = ["src/utils.ts"]
        imports = [
            {"file": "src/auth.ts", "from": "react"},
            {"file": "src/api.ts", "from": "express"},
        ]

        importers = find_files_importing(changed, imports)

        assert importers == set()

    def test_self_imports_ignored(self) -> None:
        """Test that self-imports are ignored."""
        changed = ["src/utils.ts"]
        imports = [
            {"file": "src/utils.ts", "from": "src/utils.ts"},  # Self-import
            {"file": "src/auth.ts", "from": "src/utils.ts"},
        ]

        importers = find_files_importing(changed, imports)

        assert importers == {"src/auth.ts"}
        assert "src/utils.ts" not in importers

    def test_multiple_changed_files(self) -> None:
        """Test with multiple changed files."""
        changed = ["src/utils.ts", "src/constants.ts"]
        imports = [
            {"file": "src/auth.ts", "from": "src/utils.ts"},
            {"file": "src/api.ts", "from": "src/constants.ts"},
        ]

        importers = find_files_importing(changed, imports)

        assert importers == {"src/auth.ts", "src/api.ts"}

    def test_empty_changed_files(self) -> None:
        """Test with empty changed files list."""
        imports = [
            {"file": "src/auth.ts", "from": "src/utils.ts"},
        ]

        importers = find_files_importing([], imports)

        assert importers == set()

    def test_external_imports_skipped(self) -> None:
        """Test that external imports (npm packages) are skipped."""
        changed = ["src/utils.ts"]
        imports = [
            {"file": "src/auth.ts", "from": "react"},
            {"file": "src/api.ts", "from": "express"},
        ]

        importers = find_files_importing(changed, imports)

        assert importers == set()


class TestFindFilesCalling:
    """Tests for find_files_calling function."""

    def test_single_caller(self) -> None:
        """Test finding a single file with functions calling a changed function."""
        changed = ["src/auth.ts"]
        functions = [
            {"file": "src/auth.ts", "name": "login", "line": 10},
            {"file": "src/api.ts", "name": "makeRequest", "line": 20},
        ]
        calls = [
            {"file": "src/api.ts", "caller": "makeRequest", "callee": "login"},
        ]

        callers = find_files_calling(changed, functions, calls)

        assert callers == {"src/api.ts"}

    def test_multiple_callers(self) -> None:
        """Test finding multiple files with callers."""
        changed = ["src/auth.ts"]
        functions = [
            {"file": "src/auth.ts", "name": "login", "line": 10},
            {"file": "src/auth.ts", "name": "logout", "line": 20},
            {"file": "src/api.ts", "name": "makeRequest", "line": 30},
            {"file": "src/ui.ts", "name": "render", "line": 40},
        ]
        calls = [
            {"file": "src/api.ts", "caller": "makeRequest", "callee": "login"},
            {"file": "src/ui.ts", "caller": "render", "callee": "logout"},
        ]

        callers = find_files_calling(changed, functions, calls)

        assert callers == {"src/api.ts", "src/ui.ts"}

    def test_no_callers(self) -> None:
        """Test when changed file functions are not called."""
        changed = ["src/auth.ts"]
        functions = [
            {"file": "src/auth.ts", "name": "login", "line": 10},
            {"file": "src/api.ts", "name": "makeRequest", "line": 20},
        ]
        calls = [
            {"file": "src/api.ts", "caller": "makeRequest", "callee": "anotherFunc"},
        ]

        callers = find_files_calling(changed, functions, calls)

        assert callers == set()

    def test_same_file_calls_ignored(self) -> None:
        """Test that same-file calls are ignored."""
        changed = ["src/auth.ts"]
        functions = [
            {"file": "src/auth.ts", "name": "login", "line": 10},
            {"file": "src/auth.ts", "name": "validateToken", "line": 20},
        ]
        calls = [
            {"file": "src/auth.ts", "caller": "login", "callee": "validateToken"},
        ]

        callers = find_files_calling(changed, functions, calls)

        assert callers == set()

    def test_unresolved_function_calls_skipped(self) -> None:
        """Test that calls to unresolved functions are skipped gracefully."""
        changed = ["src/auth.ts"]
        functions = [
            {"file": "src/auth.ts", "name": "login", "line": 10},
        ]
        calls = [
            {"file": "src/api.ts", "caller": "makeRequest", "callee": "unknownFunc"},
        ]

        callers = find_files_calling(changed, functions, calls)

        assert callers == set()

    def test_multiple_changed_files(self) -> None:
        """Test with multiple changed files."""
        changed = ["src/auth.ts", "src/utils.ts"]
        functions = [
            {"file": "src/auth.ts", "name": "login", "line": 10},
            {"file": "src/utils.ts", "name": "validate", "line": 20},
            {"file": "src/api.ts", "name": "makeRequest", "line": 30},
        ]
        calls = [
            {"file": "src/api.ts", "caller": "makeRequest", "callee": "login"},
            {"file": "src/api.ts", "caller": "makeRequest", "callee": "validate"},
        ]

        callers = find_files_calling(changed, functions, calls)

        assert callers == {"src/api.ts"}


class TestDetectAllAffectedFiles:
    """Tests for detect_all_affected_files orchestrator."""

    def test_changed_plus_importers(self) -> None:
        """Test detection of changed files plus files importing them."""
        changed = ["src/utils.ts"]
        imports = [
            {"file": "src/auth.ts", "from": "src/utils.ts"},
        ]
        functions = [
            {"file": "src/utils.ts", "name": "validate", "line": 10},
        ]
        calls = []

        affected = detect_all_affected_files(changed, imports, functions, calls)

        assert "src/utils.ts" in affected
        assert "src/auth.ts" in affected

    def test_changed_plus_callers(self) -> None:
        """Test detection of changed files plus files calling them."""
        changed = ["src/auth.ts"]
        imports = []
        functions = [
            {"file": "src/auth.ts", "name": "login", "line": 10},
            {"file": "src/api.ts", "name": "makeRequest", "line": 20},
        ]
        calls = [
            {"file": "src/api.ts", "caller": "makeRequest", "callee": "login"},
        ]

        affected = detect_all_affected_files(changed, imports, functions, calls)

        assert "src/auth.ts" in affected
        assert "src/api.ts" in affected

    def test_combined_importers_and_callers(self) -> None:
        """Test detection with both importers and callers."""
        changed = ["src/utils.ts"]
        imports = [
            {"file": "src/auth.ts", "from": "src/utils.ts"},
        ]
        functions = [
            {"file": "src/utils.ts", "name": "validate", "line": 10},
            {"file": "src/api.ts", "name": "makeRequest", "line": 20},
        ]
        calls = [
            {"file": "src/api.ts", "caller": "makeRequest", "callee": "validate"},
        ]

        affected = detect_all_affected_files(changed, imports, functions, calls)

        assert affected == {"src/utils.ts", "src/auth.ts", "src/api.ts"}

    def test_no_cross_file_dependencies(self) -> None:
        """Test when there are no cross-file dependencies."""
        changed = ["src/utils.ts"]
        imports = []
        functions = [{"file": "src/utils.ts", "name": "validate", "line": 10}]
        calls = []

        affected = detect_all_affected_files(changed, imports, functions, calls)

        assert affected == {"src/utils.ts"}

    def test_multiple_changed_files(self) -> None:
        """Test with multiple changed files."""
        changed = ["src/utils.ts", "src/constants.ts"]
        imports = [
            {"file": "src/auth.ts", "from": "src/utils.ts"},
            {"file": "src/api.ts", "from": "src/constants.ts"},
        ]
        functions = []
        calls = []

        affected = detect_all_affected_files(changed, imports, functions, calls)

        assert affected == {
            "src/utils.ts",
            "src/constants.ts",
            "src/auth.ts",
            "src/api.ts",
        }

    def test_empty_changed_files(self) -> None:
        """Test with empty changed files."""
        imports = []
        functions = []
        calls = []

        affected = detect_all_affected_files([], imports, functions, calls)

        assert affected == set()

    def test_transitive_dependencies_not_detected(self) -> None:
        """Note: Current implementation doesn't detect transitive dependencies.

        This test documents current behavior:
        - A imports B (B changed) → A is affected
        - C imports A → C is NOT affected (no transitive detection)

        This is acceptable for MVP; can be enhanced in future phases.
        """
        changed = ["src/utils.ts"]
        imports = [
            {"file": "src/auth.ts", "from": "src/utils.ts"},
            {"file": "src/api.ts", "from": "src/auth.ts"},  # Transitive
        ]
        functions = []
        calls = []

        affected = detect_all_affected_files(changed, imports, functions, calls)

        # Only direct importers detected
        assert "src/auth.ts" in affected
        assert "src/api.ts" not in affected  # Transitive not detected
