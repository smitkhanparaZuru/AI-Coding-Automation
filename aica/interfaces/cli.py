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
from aica.repo_intelligence import CodeIndexer
from aica.repo_intelligence.scanner import scan_repository
from aica.repo_intelligence.scanner.summarizer import RepoSummaryGenerator
from aica.repo_intelligence.scanner.writers import OutputWriter

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


@app.command(name="scan-repo")
def scan_repo(
    path: Annotated[
        Path | None,
        typer.Option("--path", help="Path to the repository to scan."),
    ] = None,
) -> None:
    """Scan a repository, generate all intelligence files, and display a summary."""
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
    OutputWriter().write(data, target, "structure.json")

    summary = RepoSummaryGenerator.from_scan_data(data)
    OutputWriter().write(summary, target, "repo_summary.json")

    routes_count = len(data.get("routes", []))
    components_count = len(data.get("components", []))
    services_count = len(data.get("services", []))
    database = summary.get("database") or "\u2014"

    log.info(
        "cli.scan_repo.done",
        routes=routes_count,
        components=components_count,
        services=services_count,
        database=database,
    )

    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    table.add_column("Metric", style="dim", min_width=25)
    table.add_column("Value")
    table.add_row("Routes detected", str(routes_count))
    table.add_row("Components detected", str(components_count))
    table.add_row("Services detected", str(services_count))
    table.add_row("Database", database)

    console.print(Panel(table, title="[bold]Repository scan complete[/bold]", border_style="cyan"))


@app.command(name="index-code")
def index_code(
    path: Annotated[
        Path | None,
        typer.Option("--path", help="Path to the codebase to index."),
    ] = None,
) -> None:
    """Index Python source files and persist the result to .aica/index.json."""
    settings = get_settings()
    target = (path or settings.workspace_dir).resolve()
    log.info("cli.index_code.start", path=str(target))

    index = CodeIndexer().index(target)
    summary = index["summary"]
    log.info("cli.index_code.done", files=summary["files"], lines=summary["lines"])
    index_path = Path(index["path"]) / ".aica" / "index.json"

    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    table.add_column("Metric", style="dim", min_width=20)
    table.add_column("Count")
    table.add_row("Files", str(summary["files"]))
    table.add_row("Lines", str(summary["lines"]))
    table.add_row("Classes", str(summary["classes"]))
    table.add_row("Functions", str(summary["functions"]))

    console.print(Panel(table, title="[bold]Code Index Summary[/bold]", border_style="cyan"))
    console.print(f"[dim]Index saved to:[/dim] [green]{index_path}[/green]")


@app.command(name="scan-next")
def scan_next(
    path: Annotated[
        Path | None,
        typer.Option("--path", help="Path to the Next.js repository to scan."),
    ] = None,
) -> None:
    """Deep-scan a Next.js App Router repo and write .repo_intelligence/structure.json."""
    settings = get_settings()
    target = (path or settings.workspace_dir).resolve()
    log.info("cli.scan_next.start", path=str(target))

    data = scan_repository(str(target))

    if "error" in data:
        console.print(f"[red]Error:[/red] {data['error']}")
        raise typer.Exit(code=1)

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

    routes_path = OutputWriter().write(routes, target, "routes.json")
    log.info("cli.scan_next.routes", output=str(routes_path))
    console.print(f"[dim]Routes saved to:[/dim] [green]{routes_path}[/green]")

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

    comp_path = OutputWriter().write(components, target, "components.json")
    log.info("cli.scan_next.components", output=str(comp_path))
    console.print(f"[dim]Components saved to:[/dim] [green]{comp_path}[/green]")

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

    svc_path = OutputWriter().write(services, target, "services.json")
    log.info("cli.scan_next.services", output=str(svc_path))
    console.print(f"[dim]Services saved to:[/dim] [green]{svc_path}[/green]")

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

    db_path = OutputWriter().write(database, target, "database.json")
    log.info("cli.scan_next.database", output=str(db_path))
    console.print(f"[dim]Database saved to:[/dim] [green]{db_path}[/green]")

    # Packages table
    packages: dict = data.get("packages", {})
    pkg_table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    pkg_table.add_column("Category", style="dim", min_width=16)
    pkg_table.add_column("Packages")
    pkg_table.add_row("framework", packages.get("framework") or "—")
    for category in ("ui", "database", "auth", "state"):
        items: list = packages.get(category, [])
        pkg_table.add_row(category, ", ".join(items) if items else "—")
    console.print(Panel(pkg_table, title="[bold]Packages[/bold]", border_style="cyan"))

    pkg_path = OutputWriter().write(packages, target, "packages.json")
    log.info("cli.scan_next.packages", output=str(pkg_path))
    console.print(f"[dim]Packages saved to:[/dim] [green]{pkg_path}[/green]")

    out_path = OutputWriter().write(data, target, "structure.json")
    log.info("cli.scan_next.done", output=str(out_path))
    console.print(f"[dim]Output saved to:[/dim] [green]{out_path}[/green]")

    # Repo summary — derived from in-memory scan data
    summary = RepoSummaryGenerator.from_scan_data(data)
    summary_path = OutputWriter().write(summary, target, "repo_summary.json")
    log.info("cli.scan_next.summary", output=str(summary_path))
    console.print(f"[dim]Summary saved to:[/dim] [green]{summary_path}[/green]")


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
            "Run [bold]aica scan-next[/bold] first to generate the artifact files."
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

