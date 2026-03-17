"""
AST Writer — writes extractor output to .repo_intelligence/ast/

Mirrors the OutputWriter in scanner/writers.py but targets
    {repo_path}/.repo_intelligence/ast/{filename}
rather than
    {repo_path}/.repo_intelligence/{filename}
"""

from __future__ import annotations

import json
from pathlib import Path

from aica.core.logging import get_logger

log = get_logger("repo.ast.writer")

_AST_OUTPUT_DIR = ".repo_intelligence/ast"


class ASTWriter:
    """Write AST extractor output lists as JSON into ``.repo_intelligence/ast/``."""

    def write(self, data: list, repo_path: Path, filename: str) -> Path:
        """Serialise *data* to ``{repo_path}/.repo_intelligence/ast/{filename}``.

        Args:
            data: List of extractor output dicts to serialise.
            repo_path: Repository root — the output sub-directory is created here.
            filename: Target filename, e.g. ``"imports.json"``.

        Returns:
            The :class:`~pathlib.Path` of the written file.
        """
        out_dir = repo_path / _AST_OUTPUT_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / filename

        out_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        log.info("ast.writer.saved", path=str(out_file), bytes=out_file.stat().st_size)
        return out_file
