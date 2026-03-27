from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from aica.core.logging import get_logger
from aica.repo_intelligence.scanner.core import scan_repository
from aica.repo_intelligence.scanner.summarizer import RepoSummaryGenerator
from aica.repo_intelligence.scanner.writers import OutputWriter

log = get_logger("repo.scanner.incremental")

_OUTPUT_DIR = ".repo_intelligence"


@dataclass(frozen=True)
class _ListArtifact:
    data_key: str
    filename: str
    ownership_key: str


_LIST_ARTIFACTS = (
    _ListArtifact("routes", "routes.json", "file"),
    _ListArtifact("components", "components.json", "file"),
    _ListArtifact("services", "services.json", "file"),
    _ListArtifact("stores", "stores.json", "path"),
    _ListArtifact("trpc_routers", "trpc_routers.json", "file"),
    _ListArtifact("hooks", "hooks.json", "file"),
    _ListArtifact("scripts", "scripts.json", "path"),
    _ListArtifact("libs", "libs.json", "path"),
    _ListArtifact("server_modules", "server_modules.json", "path"),
)

_GLOBAL_ARTIFACTS = (
    ("database", "database.json", []),
    ("packages", "packages.json", {}),
    ("i18n", "i18n.json", {}),
    ("auth", "auth.json", {}),
    ("agent_runtime", "agent_runtime.json", {}),
    ("env_vars", "env_vars.json", {}),
)


def _normalize_paths(paths: list[str]) -> list[str]:
    """Normalize paths to stable POSIX-relative format."""
    return sorted({Path(path).as_posix().lstrip("/") for path in paths if path})


def _load_existing(repo_path: Path, filename: str, default: list | dict) -> list | dict:
    """Load existing scanner JSON output or return provided default."""
    output_file = repo_path / _OUTPUT_DIR / filename
    if not output_file.exists():
        return default

    try:
        data = json.loads(output_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        log.warning("scanner.incremental.read_failed", path=str(output_file))
        return default

    if isinstance(default, list):
        return data if isinstance(data, list) else []
    if isinstance(default, dict):
        return data if isinstance(data, dict) else {}
    return default


def _entry_matches_changed(entry: dict, changed_files: list[str], ownership_key: str) -> bool:
    """Return whether a scanner entry belongs to one of the changed files."""
    owner = entry.get(ownership_key)
    if not isinstance(owner, str) or not owner:
        return False

    owner = Path(owner).as_posix().lstrip("/")
    if ownership_key == "file":
        return owner in changed_files

    # For path-based ownership, any file under the directory invalidates that entry.
    owner_prefix = f"{owner}/"
    return any(changed == owner or changed.startswith(owner_prefix) for changed in changed_files)


def _dedupe_entries(entries: list[dict]) -> list[dict]:
    """Deduplicate list entries while preserving insertion order."""
    unique: list[dict] = []
    seen: set[str] = set()

    for entry in entries:
        signature = json.dumps(entry, sort_keys=True)
        if signature in seen:
            continue
        seen.add(signature)
        unique.append(entry)

    return unique


def run_incremental_scan(repo_path: Path, changed_files: list[str]) -> dict:
    """Run scanner detectors incrementally for changed files and merge outputs.

    Strategy:
    - Re-run scanner once to obtain fresh detector outputs.
    - For list artifacts keyed by file/path, replace only changed ownership entries.
    - For singleton/global artifacts, overwrite with refreshed values.
    - Rebuild structure.json and repo_summary.json from the merged artifact set.
    """
    normalized_changed = _normalize_paths(changed_files)
    if not normalized_changed:
        return {}

    scan_data = scan_repository(str(repo_path))
    if "error" in scan_data:
        error = str(scan_data["error"])
        raise ValueError(error)

    writer = OutputWriter()
    merged_data = dict(scan_data)

    for artifact in _LIST_ARTIFACTS:
        existing_list = _load_existing(repo_path, artifact.filename, [])
        fresh_list = scan_data.get(artifact.data_key, [])

        if not isinstance(existing_list, list):
            existing_list = []
        if not isinstance(fresh_list, list):
            fresh_list = []

        preserved = [
            entry
            for entry in existing_list
            if isinstance(entry, dict)
            and not _entry_matches_changed(entry, normalized_changed, artifact.ownership_key)
        ]
        refreshed = [
            entry
            for entry in fresh_list
            if isinstance(entry, dict)
            and _entry_matches_changed(entry, normalized_changed, artifact.ownership_key)
        ]

        merged_list = _dedupe_entries(preserved + refreshed)
        writer.write(merged_list, repo_path, artifact.filename)
        merged_data[artifact.data_key] = merged_list

        log.info(
            "scanner.incremental.list_merged",
            artifact=artifact.data_key,
            preserved=len(preserved),
            refreshed=len(refreshed),
            merged=len(merged_list),
        )

    for data_key, filename, default in _GLOBAL_ARTIFACTS:
        payload = scan_data.get(data_key, default)
        writer.write(payload, repo_path, filename)
        merged_data[data_key] = payload

    writer.write(merged_data, repo_path, "structure.json")
    writer.write(RepoSummaryGenerator.from_scan_data(merged_data), repo_path, "repo_summary.json")

    log.info(
        "scanner.incremental.done",
        changed_files=len(normalized_changed),
        routes=len(merged_data.get("routes", [])),
        components=len(merged_data.get("components", [])),
        services=len(merged_data.get("services", [])),
        stores=len(merged_data.get("stores", [])),
    )

    return merged_data
