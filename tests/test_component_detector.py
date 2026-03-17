from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aica.interfaces.cli import app
from aica.repo_intelligence.scanner.detectors.components import ComponentDetector
from aica.repo_intelligence.scanner.writers import OutputWriter

runner = CliRunner()


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def component_repo(tmp_path: Path) -> Path:
    """Minimal repo with diverse React component export patterns."""
    src = tmp_path / "src"

    # components/UserCard.tsx — named export function with a props interface
    comp_dir = src / "components"
    comp_dir.mkdir(parents=True)
    (comp_dir / "UserCard.tsx").write_text(
        "interface UserCardProps {\n"
        "  userId: string;\n"
        "  name: string;\n"
        "}\n"
        "export function UserCard({ userId, name }: UserCardProps) {\n"
        "  return null;\n"
        "}\n",
        encoding="utf-8",
    )

    # components/Button.tsx — const arrow export, no props
    (comp_dir / "Button.tsx").write_text(
        "export const Button = () => null;\n",
        encoding="utf-8",
    )

    # app/page.tsx — default export function
    app_dir = src / "app"
    app_dir.mkdir(parents=True)
    (app_dir / "page.tsx").write_text(
        "export default function Page() { return null; }\n",
        encoding="utf-8",
    )

    # app/dashboard/Card.tsx — local function + export default identifier
    dashboard = app_dir / "dashboard"
    dashboard.mkdir()
    (dashboard / "Card.tsx").write_text(
        "function Card() { return null; }\nexport default Card;\n",
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture()
def nextjs_repo(tmp_path: Path) -> Path:
    """Minimal Next.js App Router repo with a detectable React component for CLI tests."""
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"next": "^16.0.0", "react": "^18.0.0"}}),
        encoding="utf-8",
    )
    (tmp_path / "tsconfig.json").write_text("{}", encoding="utf-8")
    (tmp_path / "pnpm-lock.yaml").write_text("lockfileVersion: '6.0'\n", encoding="utf-8")

    app_dir = tmp_path / "src" / "app"
    app_dir.mkdir(parents=True)
    (app_dir / "layout.tsx").write_text(
        "export default function RootLayout({ children }: any) { return children; }\n",
        encoding="utf-8",
    )
    (app_dir / "page.tsx").write_text(
        "export default function Page() { return null; }\n",
        encoding="utf-8",
    )

    comp_dir = tmp_path / "src" / "components"
    comp_dir.mkdir(parents=True)
    (comp_dir / "Hero.tsx").write_text(
        "export function Hero() { return null; }\n",
        encoding="utf-8",
    )

    return tmp_path


# ── ComponentDetector ─────────────────────────────────────────────────────────


def test_detect_named_export_function_component(component_repo: Path) -> None:
    result = ComponentDetector().detect(component_repo)
    names = [c["name"] for c in result]
    assert "UserCard" in names


def test_detect_default_export_function_component(component_repo: Path) -> None:
    result = ComponentDetector().detect(component_repo)
    names = [c["name"] for c in result]
    assert "Page" in names


def test_detect_arrow_function_component(component_repo: Path) -> None:
    result = ComponentDetector().detect(component_repo)
    names = [c["name"] for c in result]
    assert "Button" in names


def test_detect_default_export_of_identifier(component_repo: Path) -> None:
    result = ComponentDetector().detect(component_repo)
    names = [c["name"] for c in result]
    assert "Card" in names


def test_detect_ignores_lowercase_name(tmp_path: Path) -> None:
    comp_dir = tmp_path / "src" / "components"
    comp_dir.mkdir(parents=True)
    (comp_dir / "utils.tsx").write_text(
        "export function formatDate(d: Date) { return ''; }\n",
        encoding="utf-8",
    )
    result = ComponentDetector().detect(tmp_path)
    names = [c["name"] for c in result]
    assert "formatDate" not in names


def test_detect_props_from_interface(component_repo: Path) -> None:
    result = ComponentDetector().detect(component_repo)
    user_card = next(c for c in result if c["name"] == "UserCard")
    assert "userId" in user_card["props"]
    assert "name" in user_card["props"]


def test_detect_props_always_empty_list_when_none(component_repo: Path) -> None:
    result = ComponentDetector().detect(component_repo)
    button = next(c for c in result if c["name"] == "Button")
    assert button["props"] == []


def test_detect_scans_components_dir(tmp_path: Path) -> None:
    comp_dir = tmp_path / "src" / "components"
    comp_dir.mkdir(parents=True)
    (comp_dir / "Hero.tsx").write_text(
        "export default function Hero() { return null; }\n",
        encoding="utf-8",
    )
    result = ComponentDetector().detect(tmp_path)
    names = [c["name"] for c in result]
    assert "Hero" in names


def test_detect_scans_app_dir(tmp_path: Path) -> None:
    app_dir = tmp_path / "src" / "app" / "nested" / "deep"
    app_dir.mkdir(parents=True)
    (app_dir / "Widget.tsx").write_text(
        "export function Widget() { return null; }\n",
        encoding="utf-8",
    )
    result = ComponentDetector().detect(tmp_path)
    names = [c["name"] for c in result]
    assert "Widget" in names


def test_detect_empty_repo(tmp_path: Path) -> None:
    result = ComponentDetector().detect(tmp_path)
    assert result == []


def test_detect_multiple_components_in_file(tmp_path: Path) -> None:
    comp_dir = tmp_path / "src" / "components"
    comp_dir.mkdir(parents=True)
    (comp_dir / "cards.tsx").write_text(
        "export function SmallCard() { return null; }\n"
        "export function LargeCard() { return null; }\n",
        encoding="utf-8",
    )
    result = ComponentDetector().detect(tmp_path)
    names = [c["name"] for c in result]
    assert "SmallCard" in names
    assert "LargeCard" in names


# ── OutputWriter with list payload ────────────────────────────────────────────


def test_output_writer_saves_components_list(tmp_path: Path) -> None:
    components = [{"name": "Hero", "file": "src/components/Hero.tsx", "props": []}]
    out_path = OutputWriter().write(components, tmp_path, "components.json")
    assert out_path.exists()
    assert out_path.name == "components.json"
    assert out_path.parent.name == ".repo_intelligence"
    parsed = json.loads(out_path.read_text(encoding="utf-8"))
    assert isinstance(parsed, list)
    assert parsed[0]["name"] == "Hero"


# ── CLI: scan-next integration ────────────────────────────────────────────────


def test_cli_scan_next_writes_components_json(nextjs_repo: Path) -> None:
    result = runner.invoke(app, ["scan-repo", "--path", str(nextjs_repo)])
    assert result.exit_code == 0
    out_file = nextjs_repo / ".repo_intelligence" / "components.json"
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    names = [c["name"] for c in data]
    assert "Hero" in names


def test_cli_scan_next_shows_components_panel(nextjs_repo: Path) -> None:
    result = runner.invoke(app, ["scan-repo", "--path", str(nextjs_repo), "--verbose"])
    assert result.exit_code == 0
    assert "Hero" in result.output


def test_cli_scan_next_components_have_props_key(nextjs_repo: Path) -> None:
    runner.invoke(app, ["scan-repo", "--path", str(nextjs_repo)])
    out_file = nextjs_repo / ".repo_intelligence" / "components.json"
    data = json.loads(out_file.read_text(encoding="utf-8"))
    for component in data:
        assert "props" in component
        assert isinstance(component["props"], list)
