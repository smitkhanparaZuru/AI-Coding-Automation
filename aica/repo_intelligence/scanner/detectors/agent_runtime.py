from __future__ import annotations

import re
from pathlib import Path

from aica.core.logging import get_logger

log = get_logger("repo.scanner.detectors.agent_runtime")

# Keywords we search for inside a provider's source files to infer capabilities
_CAPABILITY_KEYWORDS: dict[str, re.Pattern[str]] = {
    "streaming": re.compile(r"\bstream\b|\bStreamingTextResponse\b|\bReadableStream\b", re.IGNORECASE),
    "vision": re.compile(r"\bvision\b|\bimage_url\b|\bimageUrl\b", re.IGNORECASE),
    "tool_call": re.compile(r"\btool_call\b|\btoolCall\b|\bfunction_call\b|\btools\b", re.IGNORECASE),
    "image_generation": re.compile(r"\bimage.*generat\b|\bDALL.E\b|\bstable.diffusion\b", re.IGNORECASE),
    "embedding": re.compile(r"\bembedding\b|\bEmbed\b", re.IGNORECASE),
}

# Agent-runtime root candidates
_AGENT_RUNTIME_ROOTS = (
    "src/libs/agent-runtime",
    "src/lib/agent-runtime",
    "libs/agent-runtime",
)

# SSO provider directory candidates
_SSO_PROVIDER_DIRS = (
    "src/libs/next-auth/sso-providers",
    "src/lib/next-auth/sso-providers",
    "src/libs/auth/sso-providers",
)


class AgentRuntimeDetector:
    """Detect LLM provider implementations and SSO providers in the agent-runtime layer.

    Scans ``src/libs/agent-runtime/`` for LLM provider directories and
    ``src/libs/next-auth/sso-providers/`` for SSO provider files.

    Output::

        {
            "llm_providers": [
                {"provider": "openai", "path": "src/libs/agent-runtime/openai",
                 "capabilities": ["streaming", "vision", "tool_call"]}
            ],
            "sso_providers": ["auth0", "github", "azure-ad", "zitadel"]
        }
    """

    def detect(self, repo_path: Path) -> dict:
        """Detect LLM providers and SSO providers under *repo_path*.

        Args:
            repo_path: Absolute path to the repository root.

        Returns:
            Dict with ``llm_providers`` list and ``sso_providers`` list.
        """
        log.info("agent_runtime.start", path=str(repo_path))
        llm_providers = self._detect_llm_providers(repo_path)
        sso_providers = self._detect_sso_providers(repo_path)

        result = {
            "llm_providers": llm_providers,
            "sso_providers": sso_providers,
        }
        log.info(
            "agent_runtime.done",
            llm_providers=len(llm_providers),
            sso_providers=len(sso_providers),
        )
        return result

    # ── private ───────────────────────────────────────────────────────────────

    def _detect_llm_providers(self, repo_path: Path) -> list[dict]:
        runtime_dir = self._locate_dir(repo_path, _AGENT_RUNTIME_ROOTS)
        if runtime_dir is None:
            return []

        providers: list[dict] = []
        for subdir in sorted(runtime_dir.iterdir()):
            if not subdir.is_dir() or subdir.name.startswith((".", "_")):
                continue
            capabilities = self._infer_capabilities(subdir)
            rel_path = subdir.relative_to(repo_path).as_posix()
            providers.append({
                "provider": subdir.name,
                "path": rel_path,
                "capabilities": capabilities,
            })
        return providers

    def _detect_sso_providers(self, repo_path: Path) -> list[str]:
        sso_dir = self._locate_dir(repo_path, _SSO_PROVIDER_DIRS)
        if sso_dir is None:
            return []

        return sorted(
            f.stem
            for f in sso_dir.glob("*.ts")
            if not f.name.startswith(("_", "index"))
        )

    def _infer_capabilities(self, provider_dir: Path) -> list[str]:
        """Scan up to 120 lines per .ts file to infer provider capabilities."""
        combined = ""
        for ts_file in sorted(provider_dir.glob("**/*.ts"))[:8]:
            try:
                lines = ts_file.read_text(encoding="utf-8", errors="ignore").splitlines()[:120]
                combined += "\n".join(lines) + "\n"
            except OSError:
                continue

        return sorted(
            cap for cap, pattern in _CAPABILITY_KEYWORDS.items() if pattern.search(combined)
        )

    @staticmethod
    def _locate_dir(repo_path: Path, candidates: tuple[str, ...]) -> Path | None:
        for candidate in candidates:
            d = repo_path / candidate
            if d.is_dir():
                return d
        return None
