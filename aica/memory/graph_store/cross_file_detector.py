from __future__ import annotations

from dataclasses import dataclass

from aica.core.logging import get_logger

log = get_logger("graph_store.cross_file_detector")


@dataclass
class CrossFileDependency:
    """Represents a cross-file dependency relationship."""

    source_file: str
    affected_file: str
    dependency_type: str  # "imports" | "calls_function" | "uses_type" | "uses_hook"


def find_files_importing(
    changed_files: list[str], imports_data: list[dict]
) -> set[str]:
    """Find all files that import from changed files.

    Uses imports.json data (File→File IMPORTS relationships) to identify
    which files are affected by import changes.

    Args:
        changed_files: Files that changed (e.g., ["src/utils.ts"]).
        imports_data: Loaded from imports.json (list of import entries).

    Returns:
        Set of file paths that import from changed files.

    Example:
        >>> changed = ["src/utils.ts"]
        >>> imports = [
        ...     {"file": "src/auth.ts", "from": "src/utils.ts"},
        ...     {"file": "src/api.ts", "from": "react"}
        ... ]
        >>> importers = find_files_importing(changed, imports)
        >>> print(importers)
        {'src/auth.ts'}
    """
    changed_set = set(changed_files)
    importers = set()

    for entry in imports_data:
        # Skip if no 'from' field (external imports without resolution)
        if "from" not in entry:
            continue

        from_path = entry["from"]
        if from_path in changed_set:
            # This file imports a changed file
            importer_file = entry.get("file")
            if importer_file and importer_file != from_path:
                # Don't include self-imports
                importers.add(importer_file)

    log.debug(
        "cross_file.imports_found",
        changed_count=len(changed_set),
        importers_count=len(importers),
    )

    return importers


def find_files_calling(
    changed_files: list[str],
    functions_data: list[dict],
    calls_data: list[dict],
) -> set[str]:
    """Find all files whose functions call functions in changed files.

    Uses call_graph.json data (Function→Function CALLS relationships) to identify
    which files have functions that call into changed files.

    Args:
        changed_files: Files that changed (e.g., ["src/auth.ts"]).
        functions_data: Loaded from functions.json (for building ID map).
        calls_data: Loaded from call_graph.json (flattened calls).

    Returns:
        Set of file paths with functions that call changed functions.

    Example:
        >>> changed = ["src/auth.ts"]
        >>> functions = [
        ...     {"file": "src/auth.ts", "name": "login", "line": 10},
        ...     {"file": "src/api.ts", "name": "makeRequest", "line": 20}
        ... ]
        >>> calls = [
        ...     {"file": "src/api.ts", "caller": "makeRequest", "callee": "login"}
        ... ]
        >>> callers = find_files_calling(changed, functions, calls)
        >>> print(callers)
        {'src/api.ts'}
    """
    changed_set = set(changed_files)

    # Build function file mapping: {function_name: {file: ..., line: ...}}
    function_file_map: dict[str, list[dict]] = {}
    for func in functions_data:
        fname = func.get("name")
        if fname:
            if fname not in function_file_map:
                function_file_map[fname] = []
            function_file_map[fname].append(
                {"file": func.get("file"), "line": func.get("line")}
            )

    callers = set()

    for call in calls_data:
        callee_name = call.get("callee")
        caller_file = call.get("file")

        if not callee_name or not caller_file:
            continue

        # Check if this call targets a function in a changed file
        if callee_name in function_file_map:
            for func_info in function_file_map[callee_name]:
                callee_file = func_info.get("file")
                if callee_file in changed_set:
                    # Found a call to a changed function
                    if caller_file != callee_file:
                        # Don't include same-file calls
                        callers.add(caller_file)

    log.debug(
        "cross_file.calls_found",
        changed_count=len(changed_set),
        callers_count=len(callers),
    )

    return callers


def detect_all_affected_files(
    changed_files: list[str],
    imports_data: list[dict],
    functions_data: list[dict],
    calls_data: list[dict],
) -> set[str]:
    """Detect all files affected by changes (including cross-file dependencies).

    Aggregates:
        - Original changed files
        - Files that import changed files
        - Files with functions calling changed functions

    This ensures that when a file changes, we reprocess all files that depend
    on it (directly or indirectly).

    Args:
        changed_files: Files that changed.
        imports_data: Loaded from imports.json.
        functions_data: Loaded from functions.json.
        calls_data: Loaded from call_graph.json.

    Returns:
        Set of all affected file paths.

    Example:
        >>> changed = ["src/utils.ts"]
        >>> affected = detect_all_affected_files(
        ...     changed,
        ...     imports_data,
        ...     functions_data,
        ...     calls_data
        ... )
        >>> print(f"Affected files: {len(affected)}")
    """
    changed_set = set(changed_files)

    # Find cross-file dependencies
    importers = find_files_importing(changed_files, imports_data)
    callers = find_files_calling(changed_files, functions_data, calls_data)

    # Union all
    all_affected = changed_set | importers | callers

    log.info(
        "cross_file.affected_identified",
        original=len(changed_set),
        from_imports=len(importers),
        from_calls=len(callers),
        total=len(all_affected),
    )

    return all_affected
