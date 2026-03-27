from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from aica.__about__ import __version__
from aica.config import get_settings
from aica.core import TaskPlanner
from aica.core.logging import get_logger, setup_logging
from aica.execution import ExecutionRunner
from aica.memory.graph_store.neo4j_client import GraphAuthError, GraphConnectionError, GraphQueryError
from aica.memory.graph_store.graph_builder import build_dependency_graph
from aica.repo_intelligence.ast.extractors import build_call_graph
from aica.repo_intelligence.ast.runner import ASTExtractorRunner
from aica.repo_intelligence.ast.writer import ASTWriter
from aica.repo_intelligence.scanner import scan_repository
from aica.repo_intelligence.scanner.summarizer import RepoSummaryGenerator
from aica.repo_intelligence.scanner.writers import OutputWriter
from aica.repo_intelligence.sync import NoChangesError, SyncError, sync_repository

app = typer.Typer(
    name="aica",
    help="AICA — AI Coding Automation Engine",
    add_completion=False,
    no_args_is_help=True,
)

console = Console()
log = get_logger("cli")

_MODULES = [
    "core",
    "repo_intelligence",
    "memory",
    "tools",
    "execution",
    "interfaces",
    "config",
]


@app.callback()
def _setup() -> None:
    """AICA — AI Coding Automation Engine."""
    settings = get_settings()
    setup_logging(log_level=settings.log_level, debug=settings.debug)


@app.command()
def status() -> None:
    """Show current engine status and configuration."""
    log.info("cli.status.invoked")
    settings = get_settings()

    config_table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    config_table.add_column("Setting", style="dim", min_width=20)
    config_table.add_column("Value")
    config_table.add_row("Version", __version__)
    config_table.add_row("App Name", settings.app_name)
    config_table.add_row("Debug", str(settings.debug))
    config_table.add_row("Log Level", settings.log_level)
    config_table.add_row("Workspace Dir", str(settings.workspace_dir.resolve()))

    modules_table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    modules_table.add_column("Module", style="dim", min_width=20)
    modules_table.add_column("Status")
    for module in _MODULES:
        modules_table.add_row(module, "[green]✓ loaded[/green]")

    console.print(Panel(config_table, title="[bold]AICA Status[/bold]", border_style="cyan"))
    console.print(Panel(modules_table, title="[bold]Modules[/bold]", border_style="cyan"))


@app.command()
def version() -> None:
    """Print the installed AICA version."""
    console.print(f"aica {__version__}")


def _render_verbose_tables(data: dict, console: Console) -> None:
    """Render per-entity rich tables to the console for the --verbose scan output."""
    # Framework info panel
    fw_table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    fw_table.add_column("Property", style="dim", min_width=20)
    fw_table.add_column("Value")
    fw_table.add_row("Framework", data.get("framework", "unknown"))
    fw_table.add_row("Language", data.get("language", "unknown"))
    fw_table.add_row("App Router", str(data.get("app_router", False)))
    fw_table.add_row("Next.js Version", data.get("next_version") or "—")
    fw_table.add_row("Package Manager", data.get("package_manager", "unknown"))
    console.print(Panel(fw_table, title="[bold]Framework[/bold]", border_style="cyan"))

    # Source structure table
    src_structure: dict = data.get("src_structure", {})
    if src_structure:
        src_table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
        src_table.add_column("Directory", style="dim", min_width=20)
        src_table.add_column("Path")
        for dir_name, rel_path in src_structure.items():
            src_table.add_row(dir_name, rel_path)
        console.print(Panel(src_table, title="[bold]Source Structure[/bold]", border_style="cyan"))

    # Config files table
    config_files: dict = data.get("config_files", {})
    if config_files:
        cfg_table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
        cfg_table.add_column("Config", style="dim", min_width=20)
        cfg_table.add_column("File")
        for key, value in config_files.items():
            display = ", ".join(value) if isinstance(value, list) else value
            cfg_table.add_row(key, display)
        console.print(Panel(cfg_table, title="[bold]Config Files[/bold]", border_style="cyan"))

    # Routes table
    routes: list = data.get("routes", [])
    if routes:
        routes_table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
        routes_table.add_column("Route", style="dim", min_width=25)
        routes_table.add_column("Type", min_width=12)
        routes_table.add_column("Methods", min_width=20)
        routes_table.add_column("File")
        for entry in sorted(routes, key=lambda r: (r["type"], r["route"])):
            methods_str = ", ".join(entry.get("methods", [])) or "—"
            routes_table.add_row(entry["route"], entry["type"], methods_str, entry["file"])
        console.print(Panel(routes_table, title="[bold]Routes[/bold]", border_style="cyan"))

    # Components table
    components: list = data.get("components", [])
    if components:
        comp_table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
        comp_table.add_column("Component", style="dim", min_width=25)
        comp_table.add_column("File", min_width=35)
        comp_table.add_column("Props")
        for entry in sorted(components, key=lambda c: c["name"]):
            props_str = ", ".join(entry.get("props", [])) or "—"
            comp_table.add_row(entry["name"], entry["file"], props_str)
        console.print(Panel(comp_table, title="[bold]Components[/bold]", border_style="cyan"))

    # Services table
    services: list = data.get("services", [])
    if services:
        svc_table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
        svc_table.add_column("Service", style="dim", min_width=25)
        svc_table.add_column("File", min_width=35)
        svc_table.add_column("Exported Functions")
        for entry in sorted(services, key=lambda s: s["service"]):
            fns_str = ", ".join(entry.get("exported_functions", [])) or "—"
            svc_table.add_row(entry["service"], entry["file"], fns_str)
        console.print(Panel(svc_table, title="[bold]Services[/bold]", border_style="cyan"))

    # Database table
    database: list = data.get("database", [])
    if database:
        db_table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
        db_table.add_column("ORM", style="dim", min_width=12)
        db_table.add_column("Schema", min_width=30)
        db_table.add_column("Models")
        for entry in database:
            models_str = ", ".join(m["name"] for m in entry.get("models", [])) or "—"
            db_table.add_row(entry["orm"], entry.get("schema") or "—", models_str)
        console.print(Panel(db_table, title="[bold]Database[/bold]", border_style="cyan"))

    # Packages table
    packages: dict = data.get("packages", {})
    pkg_table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    pkg_table.add_column("Category", style="dim", min_width=16)
    pkg_table.add_column("Packages")
    pkg_table.add_row("framework", packages.get("framework") or "—")
    for category in (
        "ui",
        "database",
        "auth",
        "state",
        "ai_sdk",
        "sync",
        "file_parsing",
        "monitoring",
        "payment",
        "realtime",
    ):
        items: list = packages.get(category, [])
        pkg_table.add_row(category, ", ".join(items) if items else "—")
    console.print(Panel(pkg_table, title="[bold]Packages[/bold]", border_style="cyan"))

    # Zustand stores table
    stores: list = data.get("stores", [])
    if stores:
        stores_table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
        stores_table.add_column("Store", style="dim", min_width=16)
        stores_table.add_column("Slices", min_width=30)
        stores_table.add_column("Middleware")
        for entry in sorted(stores, key=lambda s: s["store"]):
            slices_str = ", ".join(entry.get("slices", [])) or "—"
            mw_str = ", ".join(entry.get("middleware", [])) or "—"
            stores_table.add_row(entry["store"], slices_str, mw_str)
        console.print(Panel(stores_table, title="[bold]Zustand Stores[/bold]", border_style="cyan"))

    # tRPC routers table
    trpc_routers: list = data.get("trpc_routers", [])
    if trpc_routers:
        trpc_table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
        trpc_table.add_column("Tier", style="dim", min_width=10)
        trpc_table.add_column("Router", min_width=20)
        trpc_table.add_column("Procedures")
        for entry in sorted(trpc_routers, key=lambda r: (r["tier"], r["router"])):
            procs_str = ", ".join(entry.get("procedures", [])) or "—"
            trpc_table.add_row(entry["tier"], entry["router"], procs_str)
        console.print(Panel(trpc_table, title="[bold]tRPC Routers[/bold]", border_style="cyan"))

    # i18n table
    i18n: dict = data.get("i18n", {})
    if i18n.get("source_lang") or i18n.get("namespaces"):
        i18n_table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
        i18n_table.add_column("Property", style="dim", min_width=20)
        i18n_table.add_column("Value")
        i18n_table.add_row("Source language", i18n.get("source_lang") or "—")
        i18n_table.add_row("Target languages", ", ".join(i18n.get("target_langs", [])) or "—")
        i18n_table.add_row("Generated locales", ", ".join(i18n.get("generated_langs", [])) or "—")
        i18n_table.add_row("Namespace count", str(i18n.get("namespace_count", 0)))
        i18n_table.add_row("Namespaces", ", ".join(i18n.get("namespaces", [])) or "—")
        console.print(Panel(i18n_table, title="[bold]i18n[/bold]", border_style="cyan"))

    # Auth table
    auth: dict = data.get("auth", {})
    if auth.get("providers") or auth.get("config_file"):
        auth_table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
        auth_table.add_column("Property", style="dim", min_width=20)
        auth_table.add_column("Value")
        auth_table.add_row("Providers", ", ".join(auth.get("providers", [])) or "—")
        auth_table.add_row("Session strategy", auth.get("session_strategy") or "—")
        auth_table.add_row("Middleware", auth.get("middleware_file") or "—")
        auth_table.add_row("Auth routes", ", ".join(auth.get("auth_routes", [])) or "—")
        auth_table.add_row("Config file", auth.get("config_file") or "—")
        console.print(Panel(auth_table, title="[bold]Auth[/bold]", border_style="cyan"))

    # Server modules table
    server_modules: list = data.get("server_modules", [])
    if server_modules:
        sm_table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
        sm_table.add_column("Module", style="dim", min_width=20)
        sm_table.add_column("Files", min_width=25)
        sm_table.add_column("Exports")
        for entry in sorted(server_modules, key=lambda m: m["module"]):
            files_str = ", ".join(entry.get("files", [])) or "—"
            exports_str = ", ".join(entry.get("exports", [])[:5]) or "—"
            sm_table.add_row(entry["module"], files_str, exports_str)
        console.print(Panel(sm_table, title="[bold]Server Modules[/bold]", border_style="cyan"))

    # Agent runtime / LLM providers table
    agent_runtime: dict = data.get("agent_runtime", {})
    llm_providers: list = agent_runtime.get("llm_providers", [])
    sso_providers_list: list = agent_runtime.get("sso_providers", [])
    if llm_providers or sso_providers_list:
        ar_table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
        ar_table.add_column("Property", style="dim", min_width=20)
        ar_table.add_column("Value")
        ar_table.add_row("LLM providers", str(len(llm_providers)))
        ar_table.add_row(
            "Capabilities (sample)",
            ", ".join(llm_providers[0].get("capabilities", [])) if llm_providers else "—",
        )
        ar_table.add_row("SSO providers", ", ".join(sso_providers_list) or "—")
        console.print(Panel(ar_table, title="[bold]Agent Runtime[/bold]", border_style="cyan"))

    # Env vars table
    env_vars: dict = data.get("env_vars", {})
    if env_vars.get("total"):
        ev_table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
        ev_table.add_column("Category", style="dim", min_width=16)
        ev_table.add_column("Count", min_width=8)
        ev_table.add_column("Sample variables")
        for category, var_list in env_vars.get("categories", {}).items():
            sample = ", ".join(var_list[:3])
            ev_table.add_row(category, str(len(var_list)), sample)
        console.print(Panel(ev_table, title="[bold]Env Vars[/bold]", border_style="cyan"))

    # Hooks table
    hooks: list = data.get("hooks", [])
    if hooks:
        hooks_table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
        hooks_table.add_column("Hook", style="dim", min_width=25)
        hooks_table.add_column("File", min_width=35)
        hooks_table.add_column("Parameters")
        for entry in sorted(hooks, key=lambda h: h["name"]):
            params_str = ", ".join(entry.get("parameters", [])) or "—"
            hooks_table.add_row(entry["name"], entry["file"], params_str)
        console.print(Panel(hooks_table, title="[bold]Custom Hooks[/bold]", border_style="cyan"))

    # Scripts table
    scripts: list = data.get("scripts", [])
    if scripts:
        sc_table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
        sc_table.add_column("Script", style="dim", min_width=22)
        sc_table.add_column("Type", min_width=6)
        sc_table.add_column("Files")
        for entry in sorted(scripts, key=lambda s: s["name"]):
            files_str = ", ".join(entry.get("files", [])) or "—"
            sc_table.add_row(entry["name"], entry["type"], files_str)
        console.print(Panel(sc_table, title="[bold]Scripts[/bold]", border_style="cyan"))

    # Libs table
    libs: list = data.get("libs", [])
    if libs:
        libs_table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
        libs_table.add_column("Lib", style="dim", min_width=22)
        libs_table.add_column("Path", min_width=30)
        libs_table.add_column("Main files")
        for entry in sorted(libs, key=lambda lib: lib["lib"]):
            files_str = ", ".join(entry.get("main_files", [])) or "—"
            libs_table.add_row(entry["lib"], entry["path"], files_str)
        console.print(Panel(libs_table, title="[bold]Libs[/bold]", border_style="cyan"))


@app.command(name="scan-repo")
def scan_repo(
    path: Annotated[
        Path | None,
        typer.Option("--path", help="Path to the repository to scan."),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", help="Render per-entity tables in addition to the summary."),
    ] = False,
) -> None:
    """Scan a repository, generate all intelligence files, and display a summary.

    Use --verbose to also render per-entity tables (routes, components, services,
    database, packages, stores, tRPC routers, i18n, auth, server modules, agent runtime,
    env vars, hooks, scripts, libs).
    """
    settings = get_settings()
    target = (path or settings.workspace_dir).resolve()
    log.info("cli.scan_repo.start", path=str(target))

    data = scan_repository(str(target))

    if "error" in data:
        console.print(f"[red]Error:[/red] {data['error']}")
        raise typer.Exit(code=1)

    # Write all intelligence files
    OutputWriter().write(data.get("routes", []), target, "routes.json")
    OutputWriter().write(data.get("components", []), target, "components.json")
    OutputWriter().write(data.get("services", []), target, "services.json")
    OutputWriter().write(data.get("database", []), target, "database.json")
    OutputWriter().write(data.get("packages", {}), target, "packages.json")
    OutputWriter().write(data.get("stores", []), target, "stores.json")
    OutputWriter().write(data.get("trpc_routers", []), target, "trpc_routers.json")
    OutputWriter().write(data.get("i18n", {}), target, "i18n.json")
    OutputWriter().write(data.get("auth", {}), target, "auth.json")
    OutputWriter().write(data.get("server_modules", []), target, "server_modules.json")
    OutputWriter().write(data.get("agent_runtime", {}), target, "agent_runtime.json")
    OutputWriter().write(data.get("env_vars", {}), target, "env_vars.json")
    OutputWriter().write(data.get("hooks", []), target, "hooks.json")
    OutputWriter().write(data.get("scripts", []), target, "scripts.json")
    OutputWriter().write(data.get("libs", []), target, "libs.json")
    OutputWriter().write(data, target, "structure.json")

    summary = RepoSummaryGenerator.from_scan_data(data)
    OutputWriter().write(summary, target, "repo_summary.json")

    if verbose:
        _render_verbose_tables(data, console)

    routes_count = len(data.get("routes", []))
    components_count = len(data.get("components", []))
    services_count = len(data.get("services", []))
    database = summary.get("database") or "\u2014"
    stores_count = len(data.get("stores", []))
    trpc_count = len(data.get("trpc_routers", []))
    i18n_namespaces = data.get("i18n", {}).get("namespace_count", 0)
    auth_providers = len(data.get("auth", {}).get("providers", []))
    server_modules_count = len(data.get("server_modules", []))
    llm_providers_count = len(data.get("agent_runtime", {}).get("llm_providers", []))
    sso_providers_count = len(data.get("agent_runtime", {}).get("sso_providers", []))
    hooks_count = len(data.get("hooks", []))
    scripts_count = len(data.get("scripts", []))
    env_vars_total = data.get("env_vars", {}).get("total", 0)
    libs_count = len(data.get("libs", []))

    log.info(
        "cli.scan_repo.done",
        routes=routes_count,
        components=components_count,
        services=services_count,
        database=database,
        stores=stores_count,
        trpc_routers=trpc_count,
        server_modules=server_modules_count,
        llm_providers=llm_providers_count,
        hooks=hooks_count,
    )

    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    table.add_column("Metric", style="dim", min_width=25)
    table.add_column("Value")
    table.add_row("Routes detected", str(routes_count))
    table.add_row("Components detected", str(components_count))
    table.add_row("Services detected", str(services_count))
    table.add_row("Database", database)
    table.add_row("Zustand stores", str(stores_count))
    table.add_row("tRPC routers", str(trpc_count))
    table.add_row("i18n namespaces", str(i18n_namespaces))
    table.add_row("Auth providers", str(auth_providers))
    table.add_row("Server modules", str(server_modules_count))
    table.add_row("LLM providers", str(llm_providers_count))
    table.add_row("SSO providers", str(sso_providers_count))
    table.add_row("Custom hooks", str(hooks_count))
    table.add_row("Scripts", str(scripts_count))
    table.add_row("Env vars", str(env_vars_total))
    table.add_row("Libs", str(libs_count))

    console.print(Panel(table, title="[bold]Repository scan complete[/bold]", border_style="cyan"))


@app.command(name="index-code")
def index_code(
    path: Annotated[
        Path | None,
        typer.Option("--path", help="Path to the repository to index."),
    ] = None,
) -> None:
    """Run full AST analysis on all TypeScript/TSX files and write to .repo_intelligence/ast/.

    Writes:
        .repo_intelligence/ast/imports.json    — all import statements
        .repo_intelligence/ast/functions.json  — all function definitions
        .repo_intelligence/ast/exports.json    — all export statements
        .repo_intelligence/ast/call_graph.json — per-file function call graph
        .repo_intelligence/ast/hooks.json      — React hook invocations
        .repo_intelligence/ast/components.json — React component definitions
        .repo_intelligence/ast/types.json      — TypeScript interfaces and type aliases
    """
    settings = get_settings()
    target = (path or settings.workspace_dir).resolve()
    log.info("cli.index_code.start", path=str(target))

    result = ASTExtractorRunner().run(target)

    imports_list: list = result["imports"]
    functions_list: list = result["functions"]
    exports_list: list = result["exports"]
    calls_list: list = result["calls"]
    hooks_list: list = result["hooks"]
    components_list: list = result["components"]
    types_list: list = result["types"]

    writer = ASTWriter()
    imports_path = writer.write(imports_list, target, "imports.json")
    functions_path = writer.write(functions_list, target, "functions.json")
    exports_path = writer.write(exports_list, target, "exports.json")
    call_graph = build_call_graph(calls_list)
    call_graph_path = writer.write(call_graph, target, "call_graph.json")
    hooks_path = writer.write(hooks_list, target, "hooks.json")
    components_path = writer.write(components_list, target, "components.json")
    types_path = writer.write(types_list, target, "types.json")

    log.info(
        "cli.index_code.done",
        functions=len(functions_list),
        imports=len(imports_list),
        calls=len(calls_list),
        exports=len(exports_list),
        hooks=len(hooks_list),
        components=len(components_list),
        types=len(types_list),
    )

    # ── summary subcounts ─────────────────────────────────────────────────
    relative_count = sum(1 for i in imports_list if i.get("import_kind") == "relative")
    alias_count = sum(1 for i in imports_list if i.get("import_kind") == "alias")
    external_count = sum(1 for i in imports_list if i.get("import_kind") == "external")
    exported_fn_count = sum(1 for f in functions_list if f.get("exported"))
    named_count = sum(1 for e in exports_list if e.get("kind") == "named")
    default_count = sum(1 for e in exports_list if e.get("kind") == "default")
    reexport_count = sum(
        1 for e in exports_list if e.get("kind") in ("re-export", "namespace-reexport")
    )
    new_expr_count = sum(1 for c in calls_list if c.get("kind") == "new")

    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    table.add_column("Metric", style="dim", min_width=28)
    table.add_column("Value")
    table.add_row("Functions", str(len(functions_list)))
    table.add_row("  Exported", str(exported_fn_count))
    table.add_row("Imports", str(len(imports_list)))
    table.add_row("  External", str(external_count))
    table.add_row("  Alias (@/~)", str(alias_count))
    table.add_row("  Relative (./)", str(relative_count))
    table.add_row("Call relations", str(len(calls_list)))
    table.add_row("  New expressions", str(new_expr_count))
    table.add_row("Exports", str(len(exports_list)))
    table.add_row("  Named", str(named_count))
    table.add_row("  Default", str(default_count))
    table.add_row("  Re-exports", str(reexport_count))
    table.add_row("Hooks", str(len(hooks_list)))
    table.add_row("Components", str(len(components_list)))
    table.add_row("Types", str(len(types_list)))

    console.print(Panel(table, title="[bold]AST Indexing Complete[/bold]", border_style="cyan"))
    console.print(f"[dim]Functions saved to:[/dim]   [green]{functions_path}[/green]")
    console.print(f"[dim]Imports saved to:[/dim]     [green]{imports_path}[/green]")
    console.print(f"[dim]Call graph saved to:[/dim]  [green]{call_graph_path}[/green]")
    console.print(f"[dim]Exports saved to:[/dim]     [green]{exports_path}[/green]")
    console.print(f"[dim]Hooks saved to:[/dim]       [green]{hooks_path}[/green]")
    console.print(f"[dim]Components saved to:[/dim]  [green]{components_path}[/green]")
    console.print(f"[dim]Types saved to:[/dim]       [green]{types_path}[/green]")


@app.command(name="sync-repo")
def sync_repo(
    path: Annotated[
        Path | None,
        typer.Option("--path", help="Path to the repository to sync."),
    ] = None,
    base: Annotated[
        str,
        typer.Option("--base", help="Git ref to compare against when the working tree is clean."),
    ] = "HEAD",
    full: Annotated[
        bool,
        typer.Option("--full", help="Force a full reindex instead of incremental sync."),
    ] = False,
    threshold: Annotated[
        float | None,
        typer.Option(
            "--threshold",
            min=0.0,
            max=1.0,
            help="Override incremental fallback threshold (0.0-1.0).",
        ),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", help="Render changed file lists in addition to the summary."),
    ] = False,
) -> None:
    """Sync repository changes via incremental update with automatic full fallback."""
    settings = get_settings()
    target = (path or settings.workspace_dir).resolve()
    log.info("cli.sync_repo.start", path=str(target), base_ref=base, force_full=full)

    try:
        result = sync_repository(
            target,
            base_ref=base,
            force_full=full,
            fallback_threshold=threshold,
        )
    except NoChangesError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        raise typer.Exit(code=0) from exc
    except SyncError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    except GraphConnectionError as exc:
        console.print(
            "[red]Neo4j connection failed:[/red] "
            f"{exc}\nStart Neo4j and verify AICA_NEO4J_URI/AICA_NEO4J_USER/AICA_NEO4J_PASSWORD."
        )
        raise typer.Exit(code=1) from exc
    except GraphAuthError as exc:
        console.print(
            "[red]Neo4j authentication failed:[/red] "
            f"{exc}\nCheck AICA_NEO4J_USER/AICA_NEO4J_PASSWORD."
        )
        raise typer.Exit(code=1) from exc
    except GraphQueryError as exc:
        console.print(f"[red]Neo4j query failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    summary = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    summary.add_column("Metric", style="dim", min_width=24)
    summary.add_column("Value")
    summary.add_row("Mode", result.mode.title())
    summary.add_row("Base ref", result.base_ref)
    summary.add_row("Changed files", str(len(result.changed_files)))
    summary.add_row("Deleted files", str(len(result.deleted_files)))

    summary.add_row("", "")
    summary.add_row("AST: Functions", str(result.ast_summary.get("functions", 0)))
    summary.add_row("AST: Imports", str(result.ast_summary.get("imports", 0)))
    summary.add_row("AST: Components", str(result.ast_summary.get("components", 0)))
    summary.add_row("AST: Calls", str(result.ast_summary.get("calls", 0)))

    summary.add_row("", "")
    summary.add_row("Graph: Nodes deleted", str(result.graph_summary.nodes_deleted))
    summary.add_row("Graph: Nodes created", str(result.graph_summary.nodes_created))
    summary.add_row("Graph: Edges created", str(result.graph_summary.edges_created))
    summary.add_row("Duration", f"{result.duration_seconds:.2f}s")

    console.print(Panel(summary, title="[bold]Repository Sync Results[/bold]", border_style="cyan"))

    if verbose:
        details = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
        details.add_column("Category", style="dim", min_width=20)
        details.add_column("Files")
        details.add_row("Changed", "\n".join(result.changed_files) or "—")
        details.add_row("Deleted", "\n".join(result.deleted_files) or "—")
        if result.mode == "full" and not full:
            details.add_row("Fallback", "Automatic full reindex triggered by change threshold")
        elif full:
            details.add_row("Fallback", "Forced full reindex via --full")
        console.print(Panel(details, title="[bold]Changed Files[/bold]", border_style="cyan"))

    log.info(
        "cli.sync_repo.done",
        changed=len(result.changed_files),
        deleted=len(result.deleted_files),
        mode=result.mode,
        duration_seconds=round(result.duration_seconds, 3),
    )


@app.command(name="summarize-repo")
def summarize_repo(
    path: Annotated[
        Path | None,
        typer.Option("--path", help="Path to the repository to summarise."),
    ] = None,
) -> None:
    """Generate repo_summary.json from existing .repo_intelligence/ artifacts."""
    settings = get_settings()
    target = (path or settings.workspace_dir).resolve()
    log.info("cli.summarize_repo.start", path=str(target))

    artifact_dir = target / ".repo_intelligence"
    if not artifact_dir.is_dir():
        console.print(
            f"[red]Error:[/red] No .repo_intelligence/ directory found at {target}.\n"
            "Run [bold]aica scan-repo[/bold] first to generate the artifact files."
        )
        raise typer.Exit(code=1)

    summary = RepoSummaryGenerator().generate(target)

    summary_table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    summary_table.add_column("Property", style="dim", min_width=20)
    summary_table.add_column("Value")
    summary_table.add_row("Framework", summary.get("framework") or "—")
    summary_table.add_row("Language", summary.get("language") or "—")
    summary_table.add_row("Routes", str(summary.get("routes_count", 0)))
    summary_table.add_row("Components", str(summary.get("components_count", 0)))
    summary_table.add_row("Services", str(summary.get("services_count", 0)))
    summary_table.add_row("Database / ORM", summary.get("database") or "—")
    console.print(Panel(summary_table, title="[bold]Repo Summary[/bold]", border_style="cyan"))

    out_path = artifact_dir / "repo_summary.json"
    log.info("cli.summarize_repo.done", output=str(out_path))
    console.print(f"[dim]Summary saved to:[/dim] [green]{out_path}[/green]")


@app.command(name="build-graph")
def build_graph(
    path: Annotated[
        Path | None,
        typer.Option("--path", help="Path to the repository to build graph from."),
    ] = None,
) -> None:
    """Build Neo4j dependency graph from AST and scanner artifacts.

    This command loads all AST JSONs (imports, functions, calls, hooks, components, types)
    and scanner JSONs (routes, services, stores) from .repo_intelligence/ and writes them
    into a Neo4j graph database.

    Note: This adds to existing graph data. To start fresh, clear the database first via
    Neo4j Browser or Cypher: MATCH (n) DETACH DELETE n
    """
    settings = get_settings()
    target = (path or settings.workspace_dir).resolve()
    log.info("cli.build_graph.start", path=str(target))

    artifact_dir = target / ".repo_intelligence"
    if not artifact_dir.is_dir():
        console.print(
            f"[red]Error:[/red] No .repo_intelligence/ directory found at {target}.\n"
            "Run [bold]aica scan-repo[/bold] first to generate the artifact files."
        )
        raise typer.Exit(code=1)

    try:
        summary = build_dependency_graph(target)
    except Exception as e:
        console.print(f"[red]Error building graph:[/red] {e}")
        log.error("cli.build_graph.error", error=str(e))
        raise typer.Exit(code=1)

    # Build results table
    results_table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    results_table.add_column("Category", style="dim", min_width=20)
    results_table.add_column("Count", justify="right")

    # Node counts
    results_table.add_row("Files", str(summary.files))
    results_table.add_row("Functions", str(summary.functions))
    results_table.add_row("Components", str(summary.components))
    results_table.add_row("Types", str(summary.types))
    results_table.add_row("Hooks", str(summary.hooks))
    results_table.add_row("Routes", str(summary.routes))
    results_table.add_row("Services", str(summary.services))
    results_table.add_row("Stores", str(summary.stores))

    # Calculated totals
    total_nodes = (
        summary.files + summary.functions + summary.components + summary.types +
        summary.hooks + summary.routes + summary.services + summary.stores
    )
    results_table.add_row("[bold]Total Nodes[/bold]", f"[bold]{total_nodes}[/bold]")

    # Edge counts
    results_table.add_row("", "")  # Spacer
    results_table.add_row("Import Edges", str(summary.import_edges))
    results_table.add_row("Call Edges", str(summary.call_edges))
    results_table.add_row("Hook Usage Edges", str(summary.hook_edges))

    total_edges = summary.import_edges + summary.call_edges + summary.hook_edges
    results_table.add_row("[bold]Total Edges[/bold]", f"[bold]{total_edges}[/bold]")

    console.print(
        Panel(
            results_table,
            title="[bold]Dependency Graph Built[/bold]",
            border_style="cyan",
        )
    )
    log.info(
        "cli.build_graph.done",
        nodes=total_nodes,
        edges=total_edges,
        database=settings.neo4j_database,
    )


@app.command(name="plan-task")
def plan_task(
    task: Annotated[str, typer.Argument(help="Description of the task to plan.")],
) -> None:
    """Generate a structured execution plan for a task."""
    log.info("cli.plan_task.invoked", task=task)
    result = TaskPlanner().plan(task)

    steps_text = "\n".join(
        f"  {i + 1}. {step}" for i, step in enumerate(result["steps"])
    )
    content = (
        f"[bold]Task:[/bold]   {result['task']}\n"
        f"[bold]Status:[/bold] {result['status']}\n\n"
        f"[bold]Steps:[/bold]\n{steps_text}"
    )

    console.print(Panel(content, title="[bold]Task Plan[/bold]", border_style="cyan"))


@app.command(name="run-task")
def run_task(
    command: Annotated[str, typer.Argument(help="Shell command to execute.")],
    cwd: Annotated[
        str | None,
        typer.Option("--cwd", help="Working directory for the command."),
    ] = None,
) -> None:
    """Execute a shell command and display stdout / stderr."""
    log.info("cli.run_task.start", command=command)
    result = ExecutionRunner().run(command, cwd=cwd)
    log.info("cli.run_task.done", success=result.success, returncode=result.returncode)

    exit_color = "green" if result.success else "red"
    console.print(
        Panel(
            f"[{exit_color}]Exit code: {result.returncode}[/{exit_color}]",
            title="[bold]Run Task[/bold]",
            border_style=exit_color,
        )
    )

    if result.stdout:
        console.print(Panel(result.stdout, title="[bold]stdout[/bold]", border_style="green"))
    if result.stderr:
        console.print(Panel(result.stderr, title="[bold]stderr[/bold]", border_style="yellow"))


if __name__ == "__main__":
    app()

