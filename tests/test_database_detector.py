from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aica.interfaces.cli import app
from aica.repo_intelligence.scanner.core import scan_repository
from aica.repo_intelligence.scanner.detectors.database import DatabaseDetector

runner = CliRunner()


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def empty_repo(tmp_path: Path) -> Path:
    """Repo with no ORM dependencies."""
    (tmp_path / "package.json").write_text(
        json.dumps({"name": "bare-app", "dependencies": {"react": "^18"}}),
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture()
def prisma_repo(tmp_path: Path) -> Path:
    """Repo with Prisma dependency and schema file."""
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "name": "prisma-app",
                "dependencies": {"@prisma/client": "^5.0.0"},
                "devDependencies": {"prisma": "^5.0.0"},
            }
        ),
        encoding="utf-8",
    )
    prisma_dir = tmp_path / "prisma"
    prisma_dir.mkdir()
    (prisma_dir / "schema.prisma").write_text(
        """
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model User {
  id    String @id @default(cuid())
  email String @unique
  name  String?
  posts Post[]
}

model Post {
  id       String @id @default(cuid())
  title    String
  authorId String
  author   User   @relation(fields: [authorId], references: [id])
}
""",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture()
def drizzle_repo(tmp_path: Path) -> Path:
    """Repo with drizzle-orm dependency, config file, and schema in src/db/."""
    (tmp_path / "package.json").write_text(
        json.dumps({"name": "drizzle-app", "dependencies": {"drizzle-orm": "^0.30.0"}}),
        encoding="utf-8",
    )
    (tmp_path / "drizzle.config.ts").write_text(
        "import { defineConfig } from 'drizzle-kit';\nexport default defineConfig({});\n",
        encoding="utf-8",
    )
    db_dir = tmp_path / "src" / "db"
    db_dir.mkdir(parents=True)
    (db_dir / "schema.ts").write_text(
        """
import { pgTable, text, serial } from 'drizzle-orm/pg-core';

export const users = pgTable('users', {
  id: serial('id').primaryKey(),
  email: text('email').notNull(),
  name: text('name'),
});

export const posts = pgTable('posts', {
  id: serial('id').primaryKey(),
  title: text('title').notNull(),
  userId: text('userId').notNull(),
});
""",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture()
def typeorm_repo(tmp_path: Path) -> Path:
    """Repo with typeorm dependency and entity files."""
    (tmp_path / "package.json").write_text(
        json.dumps({"name": "typeorm-app", "dependencies": {"typeorm": "^0.3.0"}}),
        encoding="utf-8",
    )
    entities_dir = tmp_path / "src" / "entities"
    entities_dir.mkdir(parents=True)
    (entities_dir / "User.ts").write_text(
        """
import { Entity, PrimaryGeneratedColumn, Column } from 'typeorm';

@Entity()
export class User {
  @PrimaryGeneratedColumn()
  id: number;

  @Column()
  email: string;

  @Column()
  name: string;
}
""",
        encoding="utf-8",
    )
    (entities_dir / "Post.ts").write_text(
        """
import { Entity, PrimaryGeneratedColumn, Column } from 'typeorm';

@Entity()
export class Post {
  @PrimaryGeneratedColumn()
  id: number;

  @Column()
  title: string;

  @Column()
  authorId: string;
}
""",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture()
def multi_orm_repo(tmp_path: Path) -> Path:
    """Repo with both Prisma and Drizzle declared (edge-case multi-ORM)."""
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "name": "multi-orm",
                "dependencies": {
                    "@prisma/client": "^5.0.0",
                    "drizzle-orm": "^0.30.0",
                },
                "devDependencies": {"prisma": "^5.0.0"},
            }
        ),
        encoding="utf-8",
    )
    # Copy Prisma schema
    (tmp_path / "prisma").mkdir()
    (tmp_path / "prisma" / "schema.prisma").write_text(
        "model Item { id String @id }\n", encoding="utf-8"
    )
    # Copy Drizzle config + schema
    (tmp_path / "drizzle.config.ts").write_text("export default {};\n", encoding="utf-8")
    db_dir = tmp_path / "src" / "db"
    db_dir.mkdir(parents=True)
    (db_dir / "schema.ts").write_text(
        "import { pgTable, text } from 'drizzle-orm/pg-core';\n"
        "export const items = pgTable('items', { id: text('id') });\n",
        encoding="utf-8",
    )
    return tmp_path


# ── Tests: empty repo ─────────────────────────────────────────────────────────


def test_no_orm_returns_empty_list(empty_repo: Path) -> None:
    result = DatabaseDetector().detect(empty_repo)
    assert result == []


def test_missing_package_json_returns_empty_list(tmp_path: Path) -> None:
    result = DatabaseDetector().detect(tmp_path)
    assert result == []


# ── Tests: Prisma ─────────────────────────────────────────────────────────────


def test_prisma_detection(prisma_repo: Path) -> None:
    result = DatabaseDetector().detect(prisma_repo)
    assert len(result) == 1
    entry = result[0]
    assert entry["orm"] == "Prisma"
    assert entry["schema"] == "prisma/schema.prisma"


def test_prisma_model_names(prisma_repo: Path) -> None:
    result = DatabaseDetector().detect(prisma_repo)
    model_names = [m["name"] for m in result[0]["models"]]
    assert "User" in model_names
    assert "Post" in model_names


def test_prisma_field_extraction(prisma_repo: Path) -> None:
    result = DatabaseDetector().detect(prisma_repo)
    user_model = next(m for m in result[0]["models"] if m["name"] == "User")
    assert "id" in user_model["fields"]
    assert "email" in user_model["fields"]
    assert "name" in user_model["fields"]


def test_prisma_no_schema_file_skipped(tmp_path: Path) -> None:
    """Prisma dep declared but schema.prisma missing → no entry."""
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"prisma": "^5"}}), encoding="utf-8"
    )
    result = DatabaseDetector().detect(tmp_path)
    assert result == []


# ── Tests: Drizzle ────────────────────────────────────────────────────────────


def test_drizzle_detection(drizzle_repo: Path) -> None:
    result = DatabaseDetector().detect(drizzle_repo)
    assert len(result) == 1
    entry = result[0]
    assert entry["orm"] == "Drizzle"
    assert entry["schema"] == "drizzle.config.ts"


def test_drizzle_model_names(drizzle_repo: Path) -> None:
    result = DatabaseDetector().detect(drizzle_repo)
    model_names = [m["name"] for m in result[0]["models"]]
    assert "users" in model_names
    assert "posts" in model_names


def test_drizzle_field_extraction(drizzle_repo: Path) -> None:
    result = DatabaseDetector().detect(drizzle_repo)
    users_model = next(m for m in result[0]["models"] if m["name"] == "users")
    assert "id" in users_model["fields"]
    assert "email" in users_model["fields"]
    assert "name" in users_model["fields"]


def test_drizzle_no_files_skipped(tmp_path: Path) -> None:
    """drizzle-orm dep but no scan dirs or config → no entry."""
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"drizzle-orm": "^0.30"}}), encoding="utf-8"
    )
    result = DatabaseDetector().detect(tmp_path)
    assert result == []


# ── Tests: TypeORM ────────────────────────────────────────────────────────────


def test_typeorm_detection(typeorm_repo: Path) -> None:
    result = DatabaseDetector().detect(typeorm_repo)
    assert len(result) == 1
    entry = result[0]
    assert entry["orm"] == "TypeORM"
    assert entry["schema"] is None


def test_typeorm_model_names(typeorm_repo: Path) -> None:
    result = DatabaseDetector().detect(typeorm_repo)
    model_names = [m["name"] for m in result[0]["models"]]
    assert "User" in model_names
    assert "Post" in model_names


def test_typeorm_field_extraction(typeorm_repo: Path) -> None:
    result = DatabaseDetector().detect(typeorm_repo)
    user_model = next(m for m in result[0]["models"] if m["name"] == "User")
    assert "id" in user_model["fields"]
    assert "email" in user_model["fields"]
    assert "name" in user_model["fields"]


def test_typeorm_no_entity_dirs_skipped(tmp_path: Path) -> None:
    """typeorm dep but no entity dirs → no entry."""
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"typeorm": "^0.3"}}), encoding="utf-8"
    )
    result = DatabaseDetector().detect(tmp_path)
    assert result == []


# ── Tests: multi-ORM ─────────────────────────────────────────────────────────


def test_multi_orm_detection(multi_orm_repo: Path) -> None:
    result = DatabaseDetector().detect(multi_orm_repo)
    orm_names = [e["orm"] for e in result]
    assert "Prisma" in orm_names
    assert "Drizzle" in orm_names


# ── Integration: scan_repository ─────────────────────────────────────────────


def test_scan_repository_includes_database_key(prisma_repo: Path) -> None:
    result = scan_repository(str(prisma_repo))
    assert "database" in result
    assert isinstance(result["database"], list)


def test_scan_repository_database_empty_for_no_orm(empty_repo: Path) -> None:
    result = scan_repository(str(empty_repo))
    assert result["database"] == []


# ── Integration: CLI writes database.json ─────────────────────────────────────


def test_cli_scan_next_writes_database_json(prisma_repo: Path) -> None:
    result = runner.invoke(app, ["scan-repo", "--path", str(prisma_repo)])
    assert result.exit_code == 0, result.output
    db_file = prisma_repo / ".repo_intelligence" / "database.json"
    assert db_file.exists(), "database.json not written"
    data = json.loads(db_file.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert any(e["orm"] == "Prisma" for e in data)


def test_cli_scan_next_writes_empty_database_json(empty_repo: Path) -> None:
    result = runner.invoke(app, ["scan-repo", "--path", str(empty_repo)])
    assert result.exit_code == 0, result.output
    db_file = empty_repo / ".repo_intelligence" / "database.json"
    assert db_file.exists(), "database.json not written"
    data = json.loads(db_file.read_text(encoding="utf-8"))
    assert data == []
