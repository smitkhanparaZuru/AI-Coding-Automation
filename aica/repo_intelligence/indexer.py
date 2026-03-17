from __future__ import annotations

import ast
import json
from pathlib import Path

from aica.core.logging import get_logger

log = get_logger("repo.indexer")


class CodeIndexer:
    """Walk a codebase, extract structural metadata, and persist an index file."""

    def index(self, path: Path) -> dict:
        """Analyse all Python files under *path* and write `.aica/index.json`.

        Args:
            path: Root directory to scan.

        Returns:
            The full index dict (also written to disk).
        """
        resolved = path.resolve()
        log.info("index.start", path=str(resolved))
        files: dict[str, dict] = {}
        total_lines = 0
        total_classes = 0
        total_functions = 0

        for py_file in sorted(resolved.rglob("*.py")):
            source = py_file.read_text(encoding="utf-8", errors="ignore")
            lines = source.splitlines()
            classes: list[str] = []
            functions: list[str] = []

            try:
                tree = ast.parse(source, filename=str(py_file))
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        classes.append(node.name)
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        functions.append(node.name)
            except SyntaxError:
                log.warning("index.syntax_error", file=str(py_file))

            rel = str(py_file.relative_to(resolved))
            files[rel] = {
                "lines": len(lines),
                "classes": classes,
                "functions": functions,
            }
            log.debug("index.file", file=rel, lines=len(lines), classes=len(classes), functions=len(functions))
            total_lines += len(lines)
            total_classes += len(classes)
            total_functions += len(functions)

        log.info(
            "index.done",
            files=len(files),
            lines=total_lines,
            classes=total_classes,
            functions=total_functions,
        )
        index = {
            "path": str(resolved),
            "summary": {
                "files": len(files),
                "lines": total_lines,
                "classes": total_classes,
                "functions": total_functions,
            },
            "files": files,
        }

        output_dir = resolved / ".aica"
        output_dir.mkdir(exist_ok=True)
        (output_dir / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")

        return index
