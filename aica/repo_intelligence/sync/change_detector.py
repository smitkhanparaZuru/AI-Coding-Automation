from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from aica.core.logging import get_logger
from aica.execution import TerminalRunner
from aica.repo_intelligence.sync.exceptions import GitNotFoundError, NotAGitRepositoryError

log = get_logger("repo.sync.change_detector")

_CACHE_DIR = Path(".repo_intelligence") / ".cache"
_CACHE_FILE = _CACHE_DIR / "file_hashes.json"
_TS_EXTENSIONS = frozenset({".ts", ".tsx"})


@dataclass(frozen=True)
class GitChangeSet:
    """Normalized set of changed and deleted TypeScript files."""

    changed_files: list[str]
    deleted_files: list[str]


def _normalize_repo_path(file_path: str) -> str:
    return Path(file_path).as_posix()


def _is_relevant_path(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in _TS_EXTENSIONS


def _raise_git_error(stderr: str, repo_path: Path) -> None:
    stderr_lower = stderr.lower()
    if "not recognized" in stderr_lower or "not found" in stderr_lower:
        raise GitNotFoundError("git executable not found")
    if "not a git repository" in stderr_lower:
        raise NotAGitRepositoryError(f"Path is not a git repository: {repo_path}")
    raise NotAGitRepositoryError(f"Failed to access git repository: {repo_path}")


def _run_git_command(repo_path: Path, command: str) -> str:
    runner = TerminalRunner(timeout=30)
    result = runner.run(command, cwd=str(repo_path))

    if not result.success:
        _raise_git_error(result.stderr or result.stdout, repo_path)

    return result.stdout


def _ensure_git_repository(repo_path: Path) -> None:
    result = TerminalRunner(timeout=30).run(
        "git rev-parse --is-inside-work-tree",
        cwd=str(repo_path),
    )
    if not result.success or result.stdout.strip().lower() != "true":
        _raise_git_error(result.stderr or result.stdout, repo_path)


def _parse_status_output(output: str) -> GitChangeSet:
    changed: set[str] = set()
    deleted: set[str] = set()

    for raw_line in output.splitlines():
        line = raw_line.rstrip()
        if len(line) < 3:
            continue

        if len(line) >= 3 and line[2] == " ":
            status = line[:2]
            path_part = line[3:]
        elif len(line) >= 2 and line[1] == " ":
            status = line[0]
            path_part = line[2:]
        else:
            continue

        if " -> " in path_part:
            old_path, new_path = path_part.split(" -> ", 1)
            old_path = _normalize_repo_path(old_path)
            new_path = _normalize_repo_path(new_path)

            if _is_relevant_path(old_path):
                deleted.add(old_path)
            if _is_relevant_path(new_path):
                changed.add(new_path)
            continue

        path = _normalize_repo_path(path_part)
        if not _is_relevant_path(path):
            continue

        if "D" in status:
            deleted.add(path)
        else:
            changed.add(path)

    return GitChangeSet(changed_files=sorted(changed), deleted_files=sorted(deleted))


def _parse_name_status_output(output: str) -> GitChangeSet:
    changed: set[str] = set()
    deleted: set[str] = set()

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        parts = line.split("\t")
        status = parts[0]

        if status.startswith("R") and len(parts) >= 3:
            old_path = _normalize_repo_path(parts[1])
            new_path = _normalize_repo_path(parts[2])
            if _is_relevant_path(old_path):
                deleted.add(old_path)
            if _is_relevant_path(new_path):
                changed.add(new_path)
            continue

        if len(parts) < 2:
            continue

        path = _normalize_repo_path(parts[1])
        if not _is_relevant_path(path):
            continue

        if status.startswith("D"):
            deleted.add(path)
        else:
            changed.add(path)

    return GitChangeSet(changed_files=sorted(changed), deleted_files=sorted(deleted))


def collect_git_changes(repo_path: Path, base_ref: str = "HEAD") -> GitChangeSet:
    """Collect relevant TypeScript changes from git status and optional diff fallback."""
    _ensure_git_repository(repo_path)

    status_output = _run_git_command(repo_path, "git status --porcelain --untracked-files=all")
    status_changes = _parse_status_output(status_output)

    if status_changes.changed_files or status_changes.deleted_files:
        log.info(
            "repo.sync.git_status_changes",
            path=str(repo_path),
            changed=len(status_changes.changed_files),
            deleted=len(status_changes.deleted_files),
        )
        return status_changes

    diff_output = _run_git_command(repo_path, f"git diff --name-status {base_ref}")
    diff_changes = _parse_name_status_output(diff_output)
    log.info(
        "repo.sync.git_diff_changes",
        path=str(repo_path),
        base_ref=base_ref,
        changed=len(diff_changes.changed_files),
        deleted=len(diff_changes.deleted_files),
    )
    return diff_changes


def get_changed_files(repo_path: Path, base_ref: str = "HEAD") -> list[str]:
    """Detect changed TypeScript files using git status and diff fallback."""
    return collect_git_changes(repo_path, base_ref=base_ref).changed_files


def get_file_hash(file_path: Path) -> str:
    """Calculate a SHA-256 hash for the current file contents."""
    digest = hashlib.sha256()
    with file_path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def detect_real_changes(
    files: list[str],
    cached_hashes: dict[str, str],
    repo_path: Path | None = None,
) -> list[str]:
    """Compare current file hashes with the cache and return files with content changes."""
    root = repo_path or Path.cwd()
    real_changes: list[str] = []

    for relative_path in files:
        file_path = root / relative_path
        if not file_path.is_file():
            continue

        current_hash = get_file_hash(file_path)
        if cached_hashes.get(relative_path) != current_hash:
            real_changes.append(relative_path)

    return sorted(real_changes)


def load_cached_hashes(repo_path: Path) -> dict[str, str]:
    """Load cached file hashes from the sync cache file."""
    cache_path = repo_path / _CACHE_FILE
    if not cache_path.is_file():
        return {}

    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        log.warning("repo.sync.cache_invalid", path=str(cache_path), error=str(exc))
        return {}

    if not isinstance(payload, dict):
        log.warning("repo.sync.cache_invalid_shape", path=str(cache_path))
        return {}

    return {
        _normalize_repo_path(str(key)): str(value)
        for key, value in payload.items()
        if isinstance(key, str) and isinstance(value, str)
    }


def save_hashes(repo_path: Path, hashes: dict[str, str]) -> None:
    """Persist normalized file hashes to the sync cache file."""
    cache_dir = repo_path / _CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = repo_path / _CACHE_FILE

    normalized = {
        _normalize_repo_path(path): file_hash
        for path, file_hash in sorted(hashes.items())
        if _is_relevant_path(path)
    }
    cache_path.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
    log.info("repo.sync.cache_saved", path=str(cache_path), entries=len(normalized))


def get_cache_path(repo_path: Path) -> Path:
    """Return the absolute path to the sync hash cache file."""
    return repo_path / _CACHE_FILE