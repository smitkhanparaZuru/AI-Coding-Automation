from __future__ import annotations

from pathlib import Path

import pytest

from aica.repo_intelligence.scanner.detectors.agent_runtime import AgentRuntimeDetector


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def agent_runtime_repo(tmp_path: Path) -> Path:
    """Repo with src/libs/agent-runtime/ and sso-providers/."""
    # LLM providers
    ar_dir = tmp_path / "src" / "libs" / "agent-runtime"
    for provider, content in {
        "openai": "export const stream = true;\nexport const tools = [];\n",
        "anthropic": "export const stream = true;\nexport const vision = true;\n",
        "ollama": "export const stream = true;\n",
    }.items():
        pdir = ar_dir / provider
        pdir.mkdir(parents=True)
        (pdir / "index.ts").write_text(content, encoding="utf-8")

    # SSO providers
    sso_dir = tmp_path / "src" / "libs" / "next-auth" / "sso-providers"
    sso_dir.mkdir(parents=True)
    for name in ("github", "auth0", "azure-ad"):
        (sso_dir / f"{name}.ts").write_text(
            f"export const {name.replace('-', '')}Provider = {{}};\n", encoding="utf-8"
        )
    # index.ts should be excluded
    (sso_dir / "index.ts").write_text("export * from './github';\n", encoding="utf-8")

    return tmp_path


@pytest.fixture()
def empty_agent_runtime_repo(tmp_path: Path) -> Path:
    """Repo with no agent-runtime directory."""
    (tmp_path / "src").mkdir()
    return tmp_path


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_detect_llm_providers(agent_runtime_repo: Path) -> None:
    result = AgentRuntimeDetector().detect(agent_runtime_repo)
    providers = result["llm_providers"]
    names = {p["provider"] for p in providers}
    assert names == {"openai", "anthropic", "ollama"}


def test_provider_has_path(agent_runtime_repo: Path) -> None:
    result = AgentRuntimeDetector().detect(agent_runtime_repo)
    openai = next(p for p in result["llm_providers"] if p["provider"] == "openai")
    assert openai["path"] == "src/libs/agent-runtime/openai"


def test_streaming_capability_detected(agent_runtime_repo: Path) -> None:
    result = AgentRuntimeDetector().detect(agent_runtime_repo)
    openai = next(p for p in result["llm_providers"] if p["provider"] == "openai")
    assert "streaming" in openai["capabilities"]


def test_tool_call_capability_detected(agent_runtime_repo: Path) -> None:
    result = AgentRuntimeDetector().detect(agent_runtime_repo)
    openai = next(p for p in result["llm_providers"] if p["provider"] == "openai")
    assert "tool_call" in openai["capabilities"]


def test_vision_capability_detected(agent_runtime_repo: Path) -> None:
    result = AgentRuntimeDetector().detect(agent_runtime_repo)
    anthropic = next(p for p in result["llm_providers"] if p["provider"] == "anthropic")
    assert "vision" in anthropic["capabilities"]


def test_sso_providers_detected(agent_runtime_repo: Path) -> None:
    result = AgentRuntimeDetector().detect(agent_runtime_repo)
    assert set(result["sso_providers"]) == {"github", "auth0", "azure-ad"}


def test_sso_index_excluded(agent_runtime_repo: Path) -> None:
    result = AgentRuntimeDetector().detect(agent_runtime_repo)
    assert "index" not in result["sso_providers"]


def test_empty_repo_returns_empty_structure(empty_agent_runtime_repo: Path) -> None:
    result = AgentRuntimeDetector().detect(empty_agent_runtime_repo)
    assert result == {"llm_providers": [], "sso_providers": []}
