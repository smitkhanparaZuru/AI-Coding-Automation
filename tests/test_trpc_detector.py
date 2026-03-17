from __future__ import annotations

from pathlib import Path

import pytest

from aica.repo_intelligence.scanner.detectors.trpc import TRPCRouterDetector


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def trpc_repo(tmp_path: Path) -> Path:
    """Repo with lambda/async/edge tRPC routers."""
    routers_root = tmp_path / "src" / "server" / "routers"

    # Lambda router
    lambda_dir = routers_root / "lambda"
    lambda_dir.mkdir(parents=True)
    (lambda_dir / "agent.ts").write_text(
        "import { createTRPCRouter } from '../trpc';\n"
        "export const agentRouter = createTRPCRouter({\n"
        "  getById: publicProcedure.query(async ({ input }) => null),\n"
        "  create: publicProcedure.mutation(async ({ input }) => null),\n"
        "  update: publicProcedure.mutation(async ({ input }) => null),\n"
        "});\n",
        encoding="utf-8",
    )

    # Async router
    async_dir = routers_root / "async"
    async_dir.mkdir(parents=True)
    (async_dir / "file.ts").write_text(
        "export const fileRouter = createTRPCRouter({\n"
        "  upload: publicProcedure.mutation(async () => null),\n"
        "});\n",
        encoding="utf-8",
    )

    # Edge router
    edge_dir = routers_root / "edge"
    edge_dir.mkdir(parents=True)
    (edge_dir / "config.ts").write_text(
        "export const configRouter = createTRPCRouter({\n"
        "  getServerConfig: publicProcedure.query(async () => null),\n"
        "});\n",
        encoding="utf-8",
    )

    # Non-router file (should NOT be picked up)
    (lambda_dir / "utils.ts").write_text(
        "export const helper = () => {};\n", encoding="utf-8"
    )

    return tmp_path


@pytest.fixture()
def empty_repo(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    return tmp_path


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_detects_lambda_tier(trpc_repo: Path) -> None:
    results = TRPCRouterDetector().detect(trpc_repo)
    lambda_routers = [r for r in results if r["tier"] == "lambda"]
    assert len(lambda_routers) == 1
    assert lambda_routers[0]["router"] == "agent"


def test_detects_all_tiers(trpc_repo: Path) -> None:
    results = TRPCRouterDetector().detect(trpc_repo)
    tiers = {r["tier"] for r in results}
    assert tiers == {"lambda", "async", "edge"}


def test_extracts_procedures(trpc_repo: Path) -> None:
    results = TRPCRouterDetector().detect(trpc_repo)
    agent = next(r for r in results if r["router"] == "agent")
    assert set(agent["procedures"]) == {"getById", "create", "update"}


def test_file_is_relative_path(trpc_repo: Path) -> None:
    results = TRPCRouterDetector().detect(trpc_repo)
    for entry in results:
        assert not entry["file"].startswith("/")
        assert entry["file"].endswith(".ts")


def test_non_router_file_ignored(trpc_repo: Path) -> None:
    """utils.ts has no createTRPCRouter call and must not appear."""
    results = TRPCRouterDetector().detect(trpc_repo)
    names = [r["router"] for r in results]
    assert "utils" not in names


def test_no_routers_dir_returns_empty(empty_repo: Path) -> None:
    results = TRPCRouterDetector().detect(empty_repo)
    assert results == []


def test_root_level_routers(tmp_path: Path) -> None:
    """Root-level router files (no tier sub-dir) are detected with tier='root'."""
    routers_root = tmp_path / "src" / "server" / "routers"
    routers_root.mkdir(parents=True)
    (routers_root / "user.ts").write_text(
        "export const userRouter = createTRPCRouter({\n"
        "  profile: publicProcedure.query(async () => null),\n"
        "});\n",
        encoding="utf-8",
    )
    results = TRPCRouterDetector().detect(tmp_path)
    root_routers = [r for r in results if r["tier"] == "root"]
    assert len(root_routers) == 1
    assert root_routers[0]["router"] == "user"
    assert "profile" in root_routers[0]["procedures"]
