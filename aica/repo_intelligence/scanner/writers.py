from __future__ import annotations

import json
from pathlib import Path

from aica.core.logging import get_logger

log = get_logger("repo.writer")

_OUTPUT_DIR = ".repo_intelligence"


class OutputWriter:
    """Write scanner output dicts as JSON into the ``.repo_intelligence/`` directory."""

    def write(self, data: dict | list, repo_path: Path, filename: str) -> Path:
        """Serialise *data* to ``{repo_path}/.repo_intelligence/{filename}``.

        Args:
            data: Metadata dict to serialise.
            repo_path: Repository root — the output directory is created here.
            filename: Target filename, e.g. ``"structure.json"``.

        Returns:
            The :class:`~pathlib.Path` of the written file.
        """
        out_dir = repo_path / _OUTPUT_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / filename

        out_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        log.info("writer.saved", path=str(out_file), bytes=out_file.stat().st_size)
        return out_file
