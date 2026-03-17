from __future__ import annotations

import json
import re
from pathlib import Path

from aica.core.logging import get_logger

log = get_logger("repo.scanner.detectors.database")

# Drizzle table-definition call variants
_RE_DRIZZLE_TABLE = re.compile(
    r"(?:pgTable|mysqlTable|sqliteTable)\s*\(\s*['\"]([^'\"]+)['\"]"
)

# Drizzle field key:  fieldName: someHelper(
_RE_DRIZZLE_FIELD = re.compile(r"^\s*([a-zA-Z_$][\w$]*)\s*:", re.MULTILINE)

# Prisma model block opener
_RE_PRISMA_MODEL = re.compile(r"^model\s+(\w+)\s*\{", re.MULTILINE)

# Prisma field line (skip @@-directives)
_RE_PRISMA_FIELD = re.compile(r"^\s+(\w+)\s+\w+", re.MULTILINE)

# TypeORM @Entity decorator
_RE_TYPEORM_ENTITY_CLASS = re.compile(
    r"@Entity\s*\(.*?\)\s*(?:export\s+)?(?:abstract\s+)?class\s+(\w+)",
    re.DOTALL,
)

# TypeORM column decorators
_RE_TYPEORM_COLUMN = re.compile(
    r"@(?:Column|PrimaryColumn|PrimaryGeneratedColumn)\b[^)]*\)\s*\n\s*([a-zA-Z_$][\w$]*)\s*[!?]?\s*:"
)

# Directories to scan for Drizzle schema files
_DRIZZLE_SCAN_DIRS = ("db", "drizzle", "src/db", "src/drizzle")

# Entity directories for TypeORM
_TYPEORM_ENTITY_DIRS = ("src/entities", "src/entity", "entities", "entity")


class DatabaseDetector:
    """Detect Prisma, Drizzle, and TypeORM ORM usage in a repository.

    Detection is *package.json deps authoritative*: directory heuristics are
    only applied after a matching dependency is confirmed, preventing false
    positives.

    Output per detected ORM::

        {
            "orm": "Prisma",
            "schema": "prisma/schema.prisma",
            "models": [{"name": "User", "fields": ["id", "email"]}]
        }
    """

    def detect(self, repo_path: Path) -> list[dict]:
        """Return one entry per detected ORM under *repo_path*.

        Args:
            repo_path: Absolute path to the repository root.

        Returns:
            List of ORM descriptor dicts.  Empty list when nothing is detected.
        """
        log.info("database.start", path=str(repo_path))
        deps = self._read_deps(repo_path)
        results: list[dict] = []

        if "prisma" in deps or "@prisma/client" in deps:
            entry = self._detect_prisma(repo_path)
            if entry is not None:
                results.append(entry)

        if "drizzle-orm" in deps:
            entry = self._detect_drizzle(repo_path)
            if entry is not None:
                results.append(entry)

        if "typeorm" in deps:
            entry = self._detect_typeorm(repo_path)
            if entry is not None:
                results.append(entry)

        log.info("database.done", count=len(results), orms=[r["orm"] for r in results])
        return results

    # ── private ───────────────────────────────────────────────────────────────

    def _read_deps(self, repo_path: Path) -> set[str]:
        """Return all dependency names from *repo_path*/package.json."""
        pkg = repo_path / "package.json"
        if not pkg.exists():
            return set()
        try:
            data = json.loads(pkg.read_text(encoding="utf-8", errors="ignore"))
        except (json.JSONDecodeError, OSError):
            log.warning("database.pkg_json_error", path=str(pkg))
            return set()
        deps: set[str] = set()
        for section in ("dependencies", "devDependencies", "peerDependencies"):
            deps.update(data.get(section, {}).keys())
        return deps

    # ── Prisma ────────────────────────────────────────────────────────────────

    def _detect_prisma(self, repo_path: Path) -> dict | None:
        schema_path = repo_path / "prisma" / "schema.prisma"
        if not schema_path.exists():
            log.debug("database.prisma.no_schema")
            return None

        try:
            content = schema_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            log.warning("database.prisma.read_error", path=str(schema_path))
            return None

        models = self._extract_prisma_models(content)
        rel_schema = schema_path.relative_to(repo_path).as_posix()
        log.debug("database.prisma.found", models=len(models), schema=rel_schema)
        return {"orm": "Prisma", "schema": rel_schema, "models": models}

    def _extract_prisma_models(self, content: str) -> list[dict]:
        models: list[dict] = []
        for m in _RE_PRISMA_MODEL.finditer(content):
            name = m.group(1)
            # Find the opening brace and extract content up to matching close
            body = self._find_brace_body(content, m.end() - 1)  # end() points after {
            if body is None:
                continue
            fields = [
                f.group(1)
                for f in _RE_PRISMA_FIELD.finditer(body)
                if not f.group(1).startswith("@@")
            ]
            models.append({"name": name, "fields": fields})
        return models

    # ── Drizzle ───────────────────────────────────────────────────────────────

    def _detect_drizzle(self, repo_path: Path) -> dict | None:
        # Locate drizzle config file (schema pointer)
        schema_rel: str | None = None
        for cfg_name in ("drizzle.config.ts", "drizzle.config.js", "drizzle.config.mjs"):
            cfg = repo_path / cfg_name
            if cfg.exists():
                schema_rel = cfg_name
                break

        # Scan known directories for table definitions
        ts_files: list[Path] = []
        for subdir in _DRIZZLE_SCAN_DIRS:
            candidate = repo_path / subdir
            if candidate.is_dir():
                ts_files.extend(sorted(candidate.glob("**/*.ts")))
                ts_files.extend(sorted(candidate.glob("**/*.tsx")))

        if not ts_files and schema_rel is None:
            log.debug("database.drizzle.no_files")
            return None

        models: list[dict] = []
        seen_names: set[str] = set()
        for file_path in ts_files:
            models.extend(self._extract_drizzle_models(file_path, repo_path, seen_names))

        log.debug("database.drizzle.found", models=len(models), schema=schema_rel)
        return {"orm": "Drizzle", "schema": schema_rel, "models": models}

    def _extract_drizzle_models(
        self, file_path: Path, repo_path: Path, seen_names: set[str]
    ) -> list[dict]:
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            log.warning("database.drizzle.read_error", file=str(file_path))
            return []

        found: list[dict] = []
        for m in _RE_DRIZZLE_TABLE.finditer(content):
            table_name = m.group(1)
            if table_name in seen_names:
                continue
            seen_names.add(table_name)

            # The table definition body starts at the second argument: an object literal
            # Find the opening { that follows the table-name string argument
            search_start = m.end()
            # Advance past comma+whitespace to find the opening brace of the column obj
            obj_start = content.find("{", search_start)
            if obj_start == -1:
                found.append({"name": table_name, "fields": []})
                continue

            body = self._find_brace_body(content, obj_start)
            if body is None:
                found.append({"name": table_name, "fields": []})
                continue

            # Extract field keys (first identifier on each line before ':')
            # Skip lines that look like nested objects or comments
            fields = [
                fm.group(1)
                for fm in _RE_DRIZZLE_FIELD.finditer(body)
                if not fm.group(1).startswith("//")
            ]
            found.append({"name": table_name, "fields": fields})

        return found

    # ── TypeORM ───────────────────────────────────────────────────────────────

    def _detect_typeorm(self, repo_path: Path) -> dict | None:
        ts_files: list[Path] = []
        for subdir in _TYPEORM_ENTITY_DIRS:
            candidate = repo_path / subdir
            if candidate.is_dir():
                ts_files.extend(sorted(candidate.glob("**/*.ts")))

        if not ts_files:
            log.debug("database.typeorm.no_entity_dirs")
            return None

        models: list[dict] = []
        for file_path in ts_files:
            models.extend(self._extract_typeorm_entities(file_path))

        if not models:
            return None

        log.debug("database.typeorm.found", models=len(models))
        return {"orm": "TypeORM", "schema": None, "models": models}

    def _extract_typeorm_entities(self, file_path: Path) -> list[dict]:
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            log.warning("database.typeorm.read_error", file=str(file_path))
            return []

        found: list[dict] = []
        for m in _RE_TYPEORM_ENTITY_CLASS.finditer(content):
            name = m.group(1)
            fields = [f.group(1) for f in _RE_TYPEORM_COLUMN.finditer(content)]
            found.append({"name": name, "fields": fields})
        return found

    # ── helpers ───────────────────────────────────────────────────────────────

    def _find_brace_body(self, content: str, open_brace_pos: int) -> str | None:
        """Return the inner content between *open_brace_pos* and its matching ``}``."""
        if open_brace_pos >= len(content) or content[open_brace_pos] != "{":
            return None
        depth = 0
        for i in range(open_brace_pos, len(content)):
            if content[i] == "{":
                depth += 1
            elif content[i] == "}":
                depth -= 1
                if depth == 0:
                    return content[open_brace_pos + 1 : i]
        return None
