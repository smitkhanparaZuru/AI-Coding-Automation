from __future__ import annotations

from pathlib import Path

import pytest

from aica.repo_intelligence.scanner.detectors.env_vars import EnvVarsDetector


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def env_example_repo(tmp_path: Path) -> Path:
    """Repo with a .env.example file containing variables from multiple categories."""
    (tmp_path / ".env.example").write_text(
        "# AI provider keys\n"
        "OPENAI_API_KEY=\n"
        "ANTHROPIC_API_KEY=\n"
        "GROQ_API_KEY=\n"
        "\n"
        "# Auth\n"
        "NEXT_AUTH_SECRET=\n"
        "CLERK_SECRET_KEY=\n"
        "\n"
        "# Database\n"
        "DATABASE_URL=\n"
        "KEY_VAULTS_SECRET=\n"
        "\n"
        "# S3\n"
        "S3_ACCESS_KEY_ID=\n"
        "S3_BUCKET=\n"
        "\n"
        "# Other\n"
        "ACCESS_CODE=\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture()
def no_env_file_repo(tmp_path: Path) -> Path:
    """Repo without any .env.example file."""
    (tmp_path / "src").mkdir()
    return tmp_path


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_detect_file_name(env_example_repo: Path) -> None:
    result = EnvVarsDetector().detect(env_example_repo)
    assert result["file"] == ".env.example"


def test_total_count(env_example_repo: Path) -> None:
    result = EnvVarsDetector().detect(env_example_repo)
    assert result["total"] == 10


def test_llm_category(env_example_repo: Path) -> None:
    result = EnvVarsDetector().detect(env_example_repo)
    llm = result["categories"]["LLM"]
    assert "OPENAI_API_KEY" in llm
    assert "ANTHROPIC_API_KEY" in llm
    assert "GROQ_API_KEY" in llm


def test_auth_category(env_example_repo: Path) -> None:
    result = EnvVarsDetector().detect(env_example_repo)
    auth = result["categories"]["AUTH"]
    assert "NEXT_AUTH_SECRET" in auth
    assert "CLERK_SECRET_KEY" in auth


def test_database_category(env_example_repo: Path) -> None:
    result = EnvVarsDetector().detect(env_example_repo)
    db = result["categories"]["DATABASE"]
    assert "DATABASE_URL" in db
    assert "KEY_VAULTS_SECRET" in db


def test_s3_category(env_example_repo: Path) -> None:
    result = EnvVarsDetector().detect(env_example_repo)
    s3 = result["categories"]["S3"]
    assert "S3_ACCESS_KEY_ID" in s3
    assert "S3_BUCKET" in s3


def test_other_category(env_example_repo: Path) -> None:
    result = EnvVarsDetector().detect(env_example_repo)
    other = result["categories"]["OTHER"]
    assert "ACCESS_CODE" in other


def test_comments_and_empty_lines_ignored(env_example_repo: Path) -> None:
    """Comment lines starting with # should not appear in any category."""
    result = EnvVarsDetector().detect(env_example_repo)
    all_vars: list[str] = []
    for vars_list in result["categories"].values():
        all_vars.extend(vars_list)
    assert not any(v.startswith("#") for v in all_vars)


def test_no_env_file_returns_empty(no_env_file_repo: Path) -> None:
    result = EnvVarsDetector().detect(no_env_file_repo)
    assert result["file"] is None
    assert result["total"] == 0
    assert result["categories"] == {}


def test_env_local_example_fallback(tmp_path: Path) -> None:
    """Falls back to .env.local.example when .env.example is absent."""
    (tmp_path / ".env.local.example").write_text("DATABASE_URL=\n", encoding="utf-8")
    result = EnvVarsDetector().detect(tmp_path)
    assert result["file"] == ".env.local.example"
    assert result["total"] == 1
