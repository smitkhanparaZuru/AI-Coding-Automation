from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aica.interfaces.cli import app
from aica.repo_intelligence.scanner.core import RepositoryScanner, scan_repository
from aica.repo_intelligence.scanner.detectors.framework import FrameworkDetector
from aica.repo_intelligence.scanner.detectors.routes import RouteDetector
from aica.repo_intelligence.scanner.detectors.services import ServiceDetector
from aica.repo_intelligence.scanner.detectors.structure import StructureDetector
from aica.repo_intelligence.scanner.writers import OutputWriter

runner = CliRunner()


# ── Fixtures ──────────────────────────────────────────────────────────────────


# nextjs_repo is defined in tests/conftest.py (shared with test_cli.py)


@pytest.fixture()
def empty_repo(tmp_path: Path) -> Path:
    """A directory with no package.json at all."""
    return tmp_path


# ── FrameworkDetector ─────────────────────────────────────────────────────────


def test_detect_framework_nextjs(nextjs_repo: Path) -> None:
    result = FrameworkDetector().detect(nextjs_repo)

    assert result["framework"] == "Next.js"
    assert result["language"] == "TypeScript"
    assert result["app_router"] is True
    assert result["next_version"] == "16.0.0"
    assert result["package_manager"] == "pnpm"


def test_detect_framework_missing_package_json(empty_repo: Path) -> None:
    result = FrameworkDetector().detect(empty_repo)

    assert result["framework"] == "unknown"
    assert result["language"] == "JavaScript"
    assert result["app_router"] is False
    assert result["next_version"] is None


def test_detect_framework_react_without_next(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"react": "^18.0.0"}}),
        encoding="utf-8",
    )
    result = FrameworkDetector().detect(tmp_path)

    assert result["framework"] == "React"
    assert result["app_router"] is False


def test_detect_framework_app_router_via_root_app_dir(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"next": "^15.0.0"}}),
        encoding="utf-8",
    )
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "layout.tsx").write_text("", encoding="utf-8")

    result = FrameworkDetector().detect(tmp_path)
    assert result["app_router"] is True


def test_detect_framework_corrupted_package_json(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{ invalid json }", encoding="utf-8")
    result = FrameworkDetector().detect(tmp_path)

    assert result["framework"] == "unknown"


def test_detect_framework_yarn_lockfile(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"next": "16.0.0"}}),
        encoding="utf-8",
    )
    (tmp_path / "yarn.lock").write_text("", encoding="utf-8")
    result = FrameworkDetector().detect(tmp_path)

    assert result["package_manager"] == "yarn"


# ── StructureDetector ─────────────────────────────────────────────────────────


def test_detect_structure_src_prefix(nextjs_repo: Path) -> None:
    result = StructureDetector().detect(nextjs_repo)

    assert result["has_src_prefix"] is True
    assert result["src_structure"]["app"] == "src/app/"
    assert result["src_structure"]["components"] == "src/components/"
    assert result["src_structure"]["services"] == "src/services/"


def test_detect_structure_root_level_dirs(nextjs_repo: Path) -> None:
    result = StructureDetector().detect(nextjs_repo)

    assert "src" in result["root_dirs"]


def test_detect_structure_config_files(nextjs_repo: Path) -> None:
    result = StructureDetector().detect(nextjs_repo)

    cfg = result["config_files"]
    assert cfg["package_json"] == "package.json"
    assert cfg["tsconfig"] == "tsconfig.json"
    assert cfg["next_config"] == "next.config.ts"
    assert cfg["drizzle_config"] == "drizzle.config.ts"
    assert cfg["tailwind_config"] == "tailwind.config.ts"


def test_detect_structure_env_files(nextjs_repo: Path) -> None:
    result = StructureDetector().detect(nextjs_repo)

    env_files = result["config_files"]["env_files"]
    assert ".env" in env_files
    assert ".env.local" in env_files


def test_detect_structure_no_src_prefix(tmp_path: Path) -> None:
    (tmp_path / "components").mkdir()
    (tmp_path / "lib").mkdir()
    result = StructureDetector().detect(tmp_path)

    assert result["has_src_prefix"] is False
    assert result["src_structure"]["components"] == "components/"
    assert result["src_structure"]["lib"] == "lib/"


def test_detect_structure_empty_repo(empty_repo: Path) -> None:
    result = StructureDetector().detect(empty_repo)

    assert result["src_structure"] == {}
    assert result["config_files"] == {}
    assert result["root_dirs"] == []


# ── RepositoryScanner (integration) ───────────────────────────────────────────


def test_scan_repository_integration(nextjs_repo: Path) -> None:
    data = scan_repository(str(nextjs_repo))

    assert data["framework"] == "Next.js"
    assert data["language"] == "TypeScript"
    assert data["app_router"] is True
    assert data["next_version"] == "16.0.0"
    assert data["package_manager"] == "pnpm"
    assert "src_structure" in data
    assert "config_files" in data
    assert "root_dirs" in data
    assert data["repo_path"] == str(nextjs_repo)


def test_scan_repository_nonexistent_path() -> None:
    data = scan_repository("/nonexistent/path/that/does/not/exist")

    assert "error" in data


def test_repository_scanner_scan_returns_dict(nextjs_repo: Path) -> None:
    scanner = RepositoryScanner()
    result = scanner.scan(nextjs_repo)

    assert isinstance(result, dict)
    assert "framework" in result
    assert "src_structure" in result


# ── OutputWriter ──────────────────────────────────────────────────────────────


def test_output_writer_creates_file(tmp_path: Path) -> None:
    data = {"framework": "Next.js", "language": "TypeScript"}
    out_path = OutputWriter().write(data, tmp_path, "structure.json")

    assert out_path.exists()
    assert out_path.name == "structure.json"
    assert out_path.parent.name == ".repo_intelligence"


def test_output_writer_valid_json(tmp_path: Path) -> None:
    data = {"framework": "Next.js", "app_router": True, "env_files": [".env", ".env.local"]}
    out_path = OutputWriter().write(data, tmp_path, "structure.json")

    parsed = json.loads(out_path.read_text(encoding="utf-8"))
    assert parsed["framework"] == "Next.js"
    assert parsed["app_router"] is True
    assert parsed["env_files"] == [".env", ".env.local"]


def test_output_writer_creates_parent_dirs(tmp_path: Path) -> None:
    deep_path = tmp_path / "a" / "b" / "c"
    deep_path.mkdir(parents=True)
    out_path = OutputWriter().write({"x": 1}, deep_path, "out.json")

    assert out_path.is_file()


def test_output_writer_overwrites_existing(tmp_path: Path) -> None:
    writer = OutputWriter()
    writer.write({"version": 1}, tmp_path, "structure.json")
    writer.write({"version": 2}, tmp_path, "structure.json")

    out_file = tmp_path / ".repo_intelligence" / "structure.json"
    parsed = json.loads(out_file.read_text(encoding="utf-8"))
    assert parsed["version"] == 2


# ── CLI: scan-next ────────────────────────────────────────────────────────────


def test_cli_scan_next_exits_zero(nextjs_repo: Path) -> None:
    result = runner.invoke(app, ["scan-next", "--path", str(nextjs_repo)])
    assert result.exit_code == 0


def test_cli_scan_next_shows_framework(nextjs_repo: Path) -> None:
    result = runner.invoke(app, ["scan-next", "--path", str(nextjs_repo)])
    assert "Next.js" in result.output


def test_cli_scan_next_shows_language(nextjs_repo: Path) -> None:
    result = runner.invoke(app, ["scan-next", "--path", str(nextjs_repo)])
    assert "TypeScript" in result.output


def test_cli_scan_next_writes_output_file(nextjs_repo: Path) -> None:
    runner.invoke(app, ["scan-next", "--path", str(nextjs_repo)])
    out_file = nextjs_repo / ".repo_intelligence" / "structure.json"
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["framework"] == "Next.js"


def test_cli_scan_next_nonexistent_path(tmp_path: Path) -> None:
    bad_path = tmp_path / "does_not_exist"
    result = runner.invoke(app, ["scan-next", "--path", str(bad_path)])
    assert result.exit_code != 0


# ── RouteDetector fixture ─────────────────────────────────────────────────────


@pytest.fixture()
def routes_repo(tmp_path: Path) -> Path:
    """Next.js App Router repo with diverse route types for route detection tests."""
    (tmp_path / "package.json").write_text(
        json.dumps({"dependencies": {"next": "^16.0.0"}}),
        encoding="utf-8",
    )

    app_dir = tmp_path / "src" / "app"

    # Root page
    app_dir.mkdir(parents=True)
    (app_dir / "page.tsx").write_text(
        "export default function Page() { return null; }\n", encoding="utf-8"
    )

    # Simple nested page
    (app_dir / "dashboard").mkdir()
    (app_dir / "dashboard" / "page.tsx").write_text(
        "export default function Dashboard() { return null; }\n", encoding="utf-8"
    )

    # Route group — (auth)/login → /login
    auth_dir = app_dir / "(auth)" / "login"
    auth_dir.mkdir(parents=True)
    (auth_dir / "page.tsx").write_text(
        "export default function Login() { return null; }\n", encoding="utf-8"
    )

    # Dynamic segment — users/[id] → /users/[id]
    uid_dir = app_dir / "users" / "[id]"
    uid_dir.mkdir(parents=True)
    (uid_dir / "page.tsx").write_text(
        "export default function User() { return null; }\n", encoding="utf-8"
    )

    # Parallel route slot — @modal/photo/[id] → /photo/[id], slot=@modal
    modal_dir = app_dir / "@modal" / "photo" / "[id]"
    modal_dir.mkdir(parents=True)
    (modal_dir / "page.tsx").write_text(
        "export default function ModalPhoto() { return null; }\n", encoding="utf-8"
    )

    # Intercepted route — feed/(.)photo/[id] → /photo/[id], type=intercepted
    intercepted_dir = app_dir / "feed" / "(.)photo" / "[id]"
    intercepted_dir.mkdir(parents=True)
    (intercepted_dir / "page.tsx").write_text(
        "export default function FeedPhoto() { return null; }\n", encoding="utf-8"
    )

    # API route with GET + POST
    users_api_dir = app_dir / "api" / "users"
    users_api_dir.mkdir(parents=True)
    (users_api_dir / "route.ts").write_text(
        "export async function GET(request: Request) { return Response.json([]); }\n"
        "export async function POST(request: Request) { return Response.json({}); }\n",
        encoding="utf-8",
    )

    # API route with GET only
    posts_api_dir = app_dir / "api" / "posts"
    posts_api_dir.mkdir(parents=True)
    (posts_api_dir / "route.ts").write_text(
        "export async function GET(request: Request) { return Response.json([]); }\n",
        encoding="utf-8",
    )

    return tmp_path


# ── RouteDetector ─────────────────────────────────────────────────────────────


def test_route_detector_pages(routes_repo: Path) -> None:
    routes = RouteDetector().detect(routes_repo)
    page_routes = {r["route"] for r in routes if r["type"] == "page"}

    assert "/" in page_routes
    assert "/dashboard" in page_routes


def test_route_detector_api_methods(routes_repo: Path) -> None:
    routes = RouteDetector().detect(routes_repo)
    api_by_route = {r["route"]: r for r in routes if r["type"] == "api"}

    assert "/api/users" in api_by_route
    assert api_by_route["/api/users"]["methods"] == ["GET", "POST"]

    assert "/api/posts" in api_by_route
    assert api_by_route["/api/posts"]["methods"] == ["GET"]


def test_route_detector_route_group_stripped(routes_repo: Path) -> None:
    routes = RouteDetector().detect(routes_repo)
    route_urls = {r["route"] for r in routes}

    assert "/login" in route_urls
    assert "/(auth)/login" not in route_urls


def test_route_detector_dynamic_segment(routes_repo: Path) -> None:
    routes = RouteDetector().detect(routes_repo)
    route_urls = {r["route"] for r in routes}

    assert "/users/[id]" in route_urls


def test_route_detector_parallel_route(routes_repo: Path) -> None:
    routes = RouteDetector().detect(routes_repo)
    parallel = [r for r in routes if r["type"] == "parallel"]

    assert len(parallel) == 1
    assert parallel[0]["slot"] == "@modal"
    assert parallel[0]["route"] == "/photo/[id]"


def test_route_detector_intercepted_route(routes_repo: Path) -> None:
    routes = RouteDetector().detect(routes_repo)
    intercepted = [r for r in routes if r["type"] == "intercepted"]

    assert len(intercepted) == 1
    assert intercepted[0]["route"] == "/photo/[id]"


def test_route_detector_empty_app_dir(tmp_path: Path) -> None:
    result = RouteDetector().detect(tmp_path)

    assert result == []


def test_scanner_routes_json_written(routes_repo: Path) -> None:
    runner.invoke(app, ["scan-next", "--path", str(routes_repo)])
    routes_file = routes_repo / ".repo_intelligence" / "routes.json"

    assert routes_file.exists()
    data = json.loads(routes_file.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert any(r["type"] == "api" for r in data)


def test_scan_next_cli_routes_table(routes_repo: Path) -> None:
    result = runner.invoke(app, ["scan-next", "--path", str(routes_repo)])

    assert result.exit_code == 0
    assert "/dashboard" in result.output
    assert "/api/users" in result.output


# ── ServiceDetector fixture ───────────────────────────────────────────────────


@pytest.fixture()
def services_repo(tmp_path: Path) -> Path:
    """Repo with service, lib, and utils files for ServiceDetector tests."""
    src = tmp_path / "src"

    # services/auth.service.ts — class-based with exported methods
    svc_dir = src / "services"
    svc_dir.mkdir(parents=True)
    (svc_dir / "auth.service.ts").write_text(
        "export class AuthService {\n"
        "  async login(email: string, password: string) {}\n"
        "  async logout() {}\n"
        "}\n"
        "export async function login(email: string, password: string) {}\n"
        "export async function logout() {}\n",
        encoding="utf-8",
    )

    # src/lib/formatDate.ts — function-only, no class (fallback name)
    lib_dir = src / "lib"
    lib_dir.mkdir(parents=True)
    (lib_dir / "formatDate.ts").write_text(
        "export function formatDate(date: Date): string { return ''; }\n"
        "export const formatRelative = (date: Date) => '';\n",
        encoding="utf-8",
    )

    # src/utils/cn.ts — const arrow export only
    utils_dir = src / "utils"
    utils_dir.mkdir(parents=True)
    (utils_dir / "cn.ts").write_text(
        "export const cn = (...classes: string[]) => classes.filter(Boolean).join(' ');\n",
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture()
def services_repo_root_level(tmp_path: Path) -> Path:
    """Repo with services/ at the root level (no src/ prefix)."""
    svc_dir = tmp_path / "services"
    svc_dir.mkdir()
    (svc_dir / "user.service.ts").write_text(
        "export class UserService {}\n"
        "export function getUser(id: string) {}\n",
        encoding="utf-8",
    )

    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    (lib_dir / "helpers.ts").write_text(
        "export function slugify(text: string): string { return text; }\n",
        encoding="utf-8",
    )

    return tmp_path


# ── ServiceDetector ───────────────────────────────────────────────────────────


def test_service_detector_class_export(services_repo: Path) -> None:
    results = ServiceDetector().detect(services_repo)

    auth = next((s for s in results if "auth" in s["file"]), None)
    assert auth is not None
    assert auth["service"] == "AuthService"


def test_service_detector_function_exports(services_repo: Path) -> None:
    results = ServiceDetector().detect(services_repo)

    auth = next((s for s in results if "auth" in s["file"]), None)
    assert auth is not None
    assert "login" in auth["exported_functions"]
    assert "logout" in auth["exported_functions"]


def test_service_detector_fallback_name_from_stem(services_repo: Path) -> None:
    results = ServiceDetector().detect(services_repo)

    fmt = next((s for s in results if "formatDate" in s["file"]), None)
    assert fmt is not None
    # "formatDate" → no dots/dashes → capitalised → "FormatDate"
    assert fmt["service"] == "FormatDate"
    assert "formatDate" in fmt["exported_functions"]
    assert "formatRelative" in fmt["exported_functions"]


def test_service_detector_const_arrow_export(services_repo: Path) -> None:
    results = ServiceDetector().detect(services_repo)

    cn_entry = next((s for s in results if "cn.ts" in s["file"]), None)
    assert cn_entry is not None
    assert "cn" in cn_entry["exported_functions"]


def test_service_detector_src_prefix_preferred(tmp_path: Path) -> None:
    """src/services/ should be scanned; root services/ should be skipped."""
    # Create both — src/ prefix should win
    (tmp_path / "src" / "services").mkdir(parents=True)
    (tmp_path / "src" / "services" / "a.ts").write_text(
        "export class AService {}\n", encoding="utf-8"
    )
    (tmp_path / "services").mkdir()
    (tmp_path / "services" / "b.ts").write_text(
        "export class BService {}\n", encoding="utf-8"
    )

    results = ServiceDetector().detect(tmp_path)
    files = {s["file"] for s in results}

    assert any("src/services/a.ts" in f for f in files)
    assert not any("services/b.ts" in f and "src" not in f for f in files)


def test_service_detector_multiple_dirs(services_repo: Path) -> None:
    results = ServiceDetector().detect(services_repo)
    files = {s["file"] for s in results}

    assert any("services/" in f for f in files)
    assert any("lib/" in f for f in files)
    assert any("utils/" in f for f in files)


def test_service_detector_empty_repo(empty_repo: Path) -> None:
    results = ServiceDetector().detect(empty_repo)
    assert results == []


def test_service_detector_root_level_dirs(services_repo_root_level: Path) -> None:
    results = ServiceDetector().detect(services_repo_root_level)

    assert any("user.service.ts" in s["file"] for s in results)
    assert any("helpers.ts" in s["file"] for s in results)

    user = next((s for s in results if "user.service" in s["file"]), None)
    assert user is not None
    assert user["service"] == "UserService"
    assert "getUser" in user["exported_functions"]


# ── Integration: scan_repository includes services ────────────────────────────


def test_scan_repository_includes_services(services_repo: Path) -> None:
    # Provide a minimal package.json so framework detection doesn't error
    (services_repo / "package.json").write_text(
        json.dumps({"dependencies": {"next": "^16.0.0"}}),
        encoding="utf-8",
    )
    data = scan_repository(str(services_repo))

    assert "services" in data
    assert isinstance(data["services"], list)
    assert len(data["services"]) > 0


# ── CLI: scan-next writes services.json ───────────────────────────────────────


def test_cli_scan_next_writes_services_json(nextjs_repo: Path) -> None:
    # Add a service file to the fixture repo
    svc_dir = nextjs_repo / "src" / "services"
    svc_dir.mkdir(parents=True, exist_ok=True)
    (svc_dir / "auth.service.ts").write_text(
        "export class AuthService {}\n"
        "export async function login() {}\n",
        encoding="utf-8",
    )

    runner.invoke(app, ["scan-next", "--path", str(nextjs_repo)])

    svc_file = nextjs_repo / ".repo_intelligence" / "services.json"
    assert svc_file.exists()
    data = json.loads(svc_file.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert any(s["service"] == "AuthService" for s in data)


def test_cli_scan_next_services_table_shown(nextjs_repo: Path) -> None:
    svc_dir = nextjs_repo / "src" / "services"
    svc_dir.mkdir(parents=True, exist_ok=True)
    (svc_dir / "auth.service.ts").write_text(
        "export class AuthService {}\n"
        "export async function login() {}\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["scan-next", "--path", str(nextjs_repo)])

    assert result.exit_code == 0
    assert "AuthService" in result.output


def test_cli_scan_next_services_json_empty_when_no_services(nextjs_repo: Path) -> None:
    """services.json should be written (as empty list) even when no services exist."""
    runner.invoke(app, ["scan-next", "--path", str(nextjs_repo)])

    svc_file = nextjs_repo / ".repo_intelligence" / "services.json"
    assert svc_file.exists()
    data = json.loads(svc_file.read_text(encoding="utf-8"))
    assert isinstance(data, list)

