from __future__ import annotations

import re
from pathlib import Path

from aica.core.logging import get_logger

log = get_logger("repo.scanner.detectors.i18n")

# Regex for extracting source/target locale values from JS/TS config files
_RE_SOURCE_LOCALE = re.compile(
    r"['\"]?sourceLocale['\"]?\s*[=:]\s*['\"]([^'\"]+)['\"]"
)
_RE_TARGET_LOCALES_ARRAY = re.compile(
    r"['\"]?(?:targetLocales?|outputLocales?)['\"]?\s*[=:]\s*\[([^\]]+)\]",
    re.DOTALL,
)

# Folder names that look like locale codes  e.g. en-US, zh-CN, pt-BR, fr
_RE_LOCALE_DIR = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")


class I18nDetector:
    """Detect i18n configuration, translation namespaces, and generated locales.

    Reads ``.i18nrc.js`` / ``i18n.config.ts`` etc. for source and target
    languages.  Scans ``src/locales/default/`` (or equivalent) for TypeScript
    namespace source files.  Lists generated locale folders under ``locales/``.

    Output::

        {
            "source_lang": "zh-CN",
            "target_langs": ["en-US", "zh-TW"],
            "namespaces": ["common", "setting", "chat"],
            "namespace_count": 12,
            "generated_langs": ["en-US", "zh-CN", "zh-TW"],
            "config_file": ".i18nrc.js"
        }
    """

    def detect(self, repo_path: Path) -> dict:
        """Detect i18n setup under *repo_path*.

        Args:
            repo_path: Absolute path to the repository root.

        Returns:
            Dict with i18n metadata. All keys are always present.
        """
        log.info("i18n.start", path=str(repo_path))
        config_file, source_lang, target_langs = self._read_config(repo_path)
        namespaces = self._scan_namespaces(repo_path)
        generated_langs = self._scan_generated_langs(repo_path)

        result: dict = {
            "source_lang": source_lang,
            "target_langs": target_langs,
            "namespaces": namespaces,
            "namespace_count": len(namespaces),
            "generated_langs": generated_langs,
            "config_file": config_file,
        }
        log.info(
            "i18n.done",
            source=source_lang,
            targets=len(target_langs),
            namespaces=len(namespaces),
            generated=len(generated_langs),
        )
        return result

    # ── private ───────────────────────────────────────────────────────────────

    def _read_config(
        self, repo_path: Path
    ) -> tuple[str | None, str | None, list[str]]:
        candidates = [
            ".i18nrc.js",
            ".i18nrc.ts",
            ".i18nrc.cjs",
            "i18n.config.js",
            "i18n.config.ts",
            "src/i18n.ts",
            "src/i18n/config.ts",
        ]
        for name in candidates:
            cfg_path = repo_path / name
            if not cfg_path.exists():
                continue
            try:
                content = cfg_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            source_match = _RE_SOURCE_LOCALE.search(content)
            source = source_match.group(1) if source_match else None

            target_langs: list[str] = []
            array_match = _RE_TARGET_LOCALES_ARRAY.search(content)
            if array_match:
                # Extract quoted locale strings from the array body
                raw_locales = re.findall(r"['\"]([^'\"]+)['\"]", array_match.group(1))
                seen: set[str] = set()
                for loc in raw_locales:
                    if loc != source and loc not in seen:
                        seen.add(loc)
                        target_langs.append(loc)

            log.debug("i18n.config_found", file=name, source=source, targets=len(target_langs))
            return name, source, target_langs

        return None, None, []

    def _scan_namespaces(self, repo_path: Path) -> list[str]:
        """Return namespace names from the i18n source directory."""
        candidates = [
            "src/locales/default",
            "src/i18n/locales",
            "src/locales",
            "messages",
            "locales/default",
        ]
        for candidate in candidates:
            d = repo_path / candidate
            if not d.is_dir():
                continue
            namespaces = sorted(
                f.stem
                for f in d.iterdir()
                if f.is_file() and f.suffix in (".ts", ".json") and not f.stem.startswith("_")
            )
            if namespaces:
                log.debug("i18n.namespaces_found", dir=candidate, count=len(namespaces))
                return namespaces
        return []

    def _scan_generated_langs(self, repo_path: Path) -> list[str]:
        """Return locale codes from generated locale output directories."""
        for candidate in ("locales", "src/locales", "public/locales"):
            d = repo_path / candidate
            if not d.is_dir():
                continue
            langs = sorted(
                entry.name
                for entry in d.iterdir()
                if entry.is_dir() and _RE_LOCALE_DIR.match(entry.name)
            )
            if langs:
                log.debug("i18n.generated_langs", dir=candidate, count=len(langs))
                return langs
        return []
