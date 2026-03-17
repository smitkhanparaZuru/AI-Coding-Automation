from __future__ import annotations

from pathlib import Path

import pytest

from aica.repo_intelligence.scanner.detectors.i18n import I18nDetector


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def i18n_repo(tmp_path: Path) -> Path:
    """Repo with .i18nrc.js config, source namespaces, and generated locale dirs."""
    # Config file
    (tmp_path / ".i18nrc.js").write_text(
        "module.exports = {\n"
        "  sourceLocale: 'zh-CN',\n"
        "  targetLocales: ['en-US', 'zh-TW'],\n"
        "  entry: 'src/locales/default',\n"
        "  output: 'locales',\n"
        "};\n",
        encoding="utf-8",
    )

    # Source namespace files
    locales_default = tmp_path / "src" / "locales" / "default"
    locales_default.mkdir(parents=True)
    for ns in ("common", "setting", "chat", "error"):
        (locales_default / f"{ns}.ts").write_text(
            f"export default {{\n  title: '{ns}',\n}};\n", encoding="utf-8"
        )

    # Generated locale directories
    for lang in ("zh-CN", "en-US", "zh-TW"):
        lang_dir = tmp_path / "locales" / lang
        lang_dir.mkdir(parents=True)
        (lang_dir / "common.json").write_text('{"title":"common"}', encoding="utf-8")

    return tmp_path


@pytest.fixture()
def no_i18n_repo(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    return tmp_path


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_detects_source_lang(i18n_repo: Path) -> None:
    result = I18nDetector().detect(i18n_repo)
    assert result["source_lang"] == "zh-CN"


def test_detects_target_langs(i18n_repo: Path) -> None:
    result = I18nDetector().detect(i18n_repo)
    assert set(result["target_langs"]) == {"en-US", "zh-TW"}


def test_detects_namespaces(i18n_repo: Path) -> None:
    result = I18nDetector().detect(i18n_repo)
    assert set(result["namespaces"]) == {"common", "setting", "chat", "error"}


def test_namespace_count(i18n_repo: Path) -> None:
    result = I18nDetector().detect(i18n_repo)
    assert result["namespace_count"] == 4


def test_detects_generated_langs(i18n_repo: Path) -> None:
    result = I18nDetector().detect(i18n_repo)
    assert set(result["generated_langs"]) == {"zh-CN", "en-US", "zh-TW"}


def test_config_file_recorded(i18n_repo: Path) -> None:
    result = I18nDetector().detect(i18n_repo)
    assert result["config_file"] == ".i18nrc.js"


def test_no_i18n_returns_defaults(no_i18n_repo: Path) -> None:
    result = I18nDetector().detect(no_i18n_repo)
    assert result["source_lang"] is None
    assert result["target_langs"] == []
    assert result["namespaces"] == []
    assert result["namespace_count"] == 0
    assert result["generated_langs"] == []
    assert result["config_file"] is None


def test_all_keys_present(i18n_repo: Path) -> None:
    result = I18nDetector().detect(i18n_repo)
    for key in ("source_lang", "target_langs", "namespaces", "namespace_count",
                "generated_langs", "config_file"):
        assert key in result
