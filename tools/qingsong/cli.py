"""
Command-line interface for Qingsong.

This module provides the main CLI entry point using Typer.
All commands are thin wrappers over the Core API.
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax

from . import __version__, PROJECT_ROOT
from .core import QingsongCore
from .models import ItemType

# Create Typer app
app = typer.Typer(
    name="qingsong",
    help="Qingsong: Project Management Engine for MUST Telescope",
    add_completion=False,
)

# Subcommands
meta_app = typer.Typer(help="Metadata operations")
cache_app = typer.Typer(help="Cache operations")

app.add_typer(meta_app, name="meta")
app.add_typer(cache_app, name="cache")

# Console for rich output
console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"Qingsong version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True,
        help="Show version and exit"
    ),
):
    """Qingsong: Project Management Engine for MUST Telescope"""
    pass


# =============================================================================
# Meta commands
# =============================================================================

@meta_app.command("validate")
def meta_validate():
    """Validate metadata files."""
    console.print("[bold]Validating metadata...[/bold]")

    try:
        from .load_meta import validate_metadata

        errors = validate_metadata()

        if errors:
            console.print("[red]Metadata validation FAILED[/red]")
            for error in errors:
                console.print(f"  [red]✗[/red] {error}")
            raise typer.Exit(1)
        else:
            console.print("[green]✓ Metadata validation PASSED[/green]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@meta_app.command("show")
def meta_show():
    """Show loaded metadata summary."""
    try:
        from .load_meta import load_metadata

        metadata = load_metadata()

        console.print(Panel.fit(
            f"[bold]Project:[/bold] {metadata.project_name}\n"
            f"[bold]ID:[/bold] {metadata.project_id}\n"
            f"[bold]Systems:[/bold] {len(metadata.systems)}\n"
            f"[bold]People:[/bold] {len(metadata.people)}\n"
            f"[bold]System Paths:[/bold] {len(metadata.valid_system_paths)}\n"
            f"[bold]L3 Codes:[/bold] {len(metadata.valid_l3_codes)}",
            title="Metadata Summary"
        ))

        # Systems table
        table = Table(title="Systems (L1/L2)")
        table.add_column("L1", style="cyan")
        table.add_column("L2", style="green")
        table.add_column("Name")
        table.add_column("Owner")

        for sys_id, system in metadata.systems.items():
            for sub_id, subsystem in system.subsystems.items():
                table.add_row(sys_id, sub_id, subsystem.name, subsystem.owner)

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


# =============================================================================
# Validation commands
# =============================================================================

@app.command("validate")
def validate():
    """Validate all items in the repository."""
    console.print("[bold]Validating all items...[/bold]")

    try:
        core = QingsongCore.load()
        result = core.validate()

        if result.valid:
            console.print(f"[green]✓ Validation PASSED[/green]")
            console.print(f"  Items validated: {result.item_count}")
            console.print(f"  Warnings: {len(result.warnings)}")

            if result.warnings:
                console.print("\n[yellow]Warnings:[/yellow]")
                for warn in result.warnings:
                    console.print(f"  [yellow]⚠[/yellow] {warn}")
        else:
            console.print(f"[red]✗ Validation FAILED[/red]")
            console.print(f"  Items validated: {result.item_count}")
            console.print(f"  Errors: {len(result.errors)}")
            console.print(f"  Warnings: {len(result.warnings)}")

            console.print("\n[red]Errors:[/red]")
            for error in result.errors:
                console.print(f"  [red]✗[/red] {error}")

            if result.warnings:
                console.print("\n[yellow]Warnings:[/yellow]")
                for warn in result.warnings:
                    console.print(f"  [yellow]⚠[/yellow] {warn}")

            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


# =============================================================================
# Cache commands
# =============================================================================

@cache_app.command("build")
def cache_build():
    """Build SQLite cache from items."""
    console.print("[bold]Building SQLite cache...[/bold]")

    try:
        core = QingsongCore.load()
        cache_path = core.build_cache()

        stats = core.get_cache_stats()

        console.print(f"[green]✓ Cache built successfully[/green]")
        console.print(f"  Path: {cache_path}")
        console.print(f"  Items: {stats.get('item_count', 'N/A')}")
        console.print(f"  Links: {stats.get('link_count', 'N/A')}")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@cache_app.command("stats")
def cache_stats():
    """Show cache statistics."""
    try:
        core = QingsongCore.load()
        stats = core.get_cache_stats()

        if not stats.get("exists"):
            console.print("[yellow]Cache not found. Run 'qingsong cache build' first.[/yellow]")
            raise typer.Exit(1)

        console.print(Panel.fit(
            f"[bold]Path:[/bold] {stats.get('path')}\n"
            f"[bold]Built at:[/bold] {stats.get('built_at', 'N/A')}\n"
            f"[bold]Items:[/bold] {stats.get('item_count', 'N/A')}\n"
            f"[bold]Links:[/bold] {stats.get('link_count', 'N/A')}",
            title="Cache Statistics"
        ))

        if "items_by_type" in stats:
            table = Table(title="Items by Type")
            table.add_column("Type", style="cyan")
            table.add_column("Count", justify="right")
            for t, c in stats["items_by_type"].items():
                table.add_row(t, str(c))
            console.print(table)

        if "items_by_system" in stats:
            table = Table(title="Items by System")
            table.add_column("System", style="green")
            table.add_column("Count", justify="right")
            for s, c in stats["items_by_system"].items():
                table.add_row(s, str(c))
            console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


# =============================================================================
# Query command
# =============================================================================

@app.command("query")
def query(
    sql: str = typer.Argument(..., help="SQL query to execute"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, csv, json"),
):
    """Execute SQL query on the cache."""
    try:
        core = QingsongCore.load()
        results = core.query(sql)

        if not results:
            console.print("[yellow]No results[/yellow]")
            return

        if format == "json":
            import json
            console.print(json.dumps(results, indent=2, default=str))
        elif format == "csv":
            import csv
            import io
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
            console.print(output.getvalue())
        else:
            # Table format
            table = Table()
            for col in results[0].keys():
                table.add_column(col)
            for row in results:
                table.add_row(*[str(v) for v in row.values()])
            console.print(table)

    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


# =============================================================================
# New item command
# =============================================================================

@app.command("new")
def new_item(
    item_type: str = typer.Argument(..., help="Item type: req, rsk, ifc, doc, dat, note"),
    title: str = typer.Option(..., "--title", "-t", help="Item title"),
    system: str = typer.Option(..., "--system", "-s", help="System path (e.g., FPS/FID)"),
    owner: str = typer.Option("ps001", "--owner", "-o", help="Owner person ID"),
    text: str = typer.Option("TBD", "--text", help="Item description"),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Category path"),
    l3: Optional[str] = typer.Option(None, "--l3", help="L3 task code"),
):
    """Create a new item."""
    try:
        # Map short type names
        type_map = {
            "req": ItemType.REQ,
            "rsk": ItemType.RSK,
            "ifc": ItemType.IFC,
            "doc": ItemType.DOC,
            "dat": ItemType.DAT,
            "note": ItemType.NOTE,
        }

        if item_type.lower() not in type_map:
            console.print(f"[red]Invalid type: {item_type}. Use: req, rsk, ifc, doc, dat, note[/red]")
            raise typer.Exit(1)

        core = QingsongCore.load()

        # Create the item
        item = core.create_item(
            item_type=type_map[item_type.lower()],
            system_path=system,
            title=title,
            text=text,
            owner=owner,
            category_path=category,
            l3=l3,
        )

        console.print(f"[green]✓ Created item: {item.id_full}[/green]")
        console.print(f"  Type: {item.type.value}")
        console.print(f"  Title: {item.title}")
        console.print(f"  System: {item.system_path}")
        console.print(f"  Status: {item.status.value}")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


# =============================================================================
# List commands
# =============================================================================

@app.command("list")
def list_items(
    item_type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by type"),
    system: Optional[str] = typer.Option(None, "--system", "-s", help="Filter by system"),
    status: Optional[str] = typer.Option(None, "--status", help="Filter by status"),
    owner: Optional[str] = typer.Option(None, "--owner", "-o", help="Filter by owner"),
    limit: int = typer.Option(50, "--limit", "-n", help="Maximum items to show"),
):
    """List items in the repository."""
    try:
        core = QingsongCore.load()
        items = list(core.items.values())

        # Apply filters
        if item_type:
            type_map = {"req": "REQ", "rsk": "RSK", "ifc": "IFC", "doc": "DOC", "dat": "DAT", "note": "NOTE"}
            t = type_map.get(item_type.lower(), item_type.upper())
            items = [i for i in items if i.type.value == t]

        if system:
            items = [i for i in items if i.system_path == system]

        if status:
            items = [i for i in items if i.status.value == status]

        if owner:
            items = [i for i in items if i.owner == owner]

        # Sort by ID
        items.sort(key=lambda x: x.id_full)

        # Limit
        total = len(items)
        items = items[:limit]

        # Display table
        table = Table(title=f"Items ({len(items)} of {total})")
        table.add_column("ID", style="cyan")
        table.add_column("Type")
        table.add_column("Title")
        table.add_column("System", style="green")
        table.add_column("Status")
        table.add_column("Owner")

        for item in items:
            status_style = "green" if item.status.value == "active" else "yellow"
            table.add_row(
                item.id_full,
                item.type.value,
                item.title[:40] + "..." if len(item.title) > 40 else item.title,
                item.system_path,
                f"[{status_style}]{item.status.value}[/{status_style}]",
                item.owner,
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command("show")
def show_item(
    item_id: str = typer.Argument(..., help="Item ID to show"),
):
    """Show details of a specific item."""
    try:
        core = QingsongCore.load()
        item = core.get_item(item_id)

        if not item:
            console.print(f"[red]Item not found: {item_id}[/red]")
            raise typer.Exit(1)

        # Display item details
        console.print(Panel.fit(
            f"[bold cyan]{item.id_full}[/bold cyan]\n\n"
            f"[bold]Title:[/bold] {item.title}\n"
            f"[bold]Type:[/bold] {item.type.value}\n"
            f"[bold]System:[/bold] {item.system_path}\n"
            f"[bold]Status:[/bold] {item.status.value}\n"
            f"[bold]Owner:[/bold] {item.owner}\n"
            f"[bold]Created:[/bold] {item.created_at}\n"
            f"[bold]Updated:[/bold] {item.updated_at}",
            title="Item Details"
        ))

        console.print("\n[bold]Description:[/bold]")
        console.print(item.text)

        # Show links
        if item.links:
            console.print("\n[bold]Links:[/bold]")
            for link in item.links:
                console.print(f"  → {link.link_type}: {link.target_id}")

        # Show linked items
        linked = core.get_linked_items(item_id)
        if linked["incoming"]:
            console.print("\n[bold]Incoming Links:[/bold]")
            for other in linked["incoming"]:
                console.print(f"  ← {other.id_full}: {other.title[:40]}")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


# =============================================================================
# Graph command
# =============================================================================

@app.command("graph")
def graph_cmd(
    item_id: Optional[str] = typer.Argument(None, help="Center item ID (optional)"),
    output: Path = typer.Option(Path("graph.html"), "--output", "-o", help="Output HTML file"),
    depth: int = typer.Option(2, "--depth", "-d", help="Neighborhood depth"),
):
    """Generate graph visualization."""
    try:
        from .graph import build_graph, get_neighborhood, export_graph_html, get_graph_stats

        core = QingsongCore.load()

        if item_id:
            console.print(f"[bold]Building neighborhood graph for {item_id}...[/bold]")
            G = get_neighborhood(core, item_id, depth=depth)
            title = f"Neighborhood of {item_id}"
        else:
            console.print("[bold]Building full graph...[/bold]")
            G = build_graph(core)
            title = "Qingsong Item Graph"

        stats = get_graph_stats(G)
        console.print(f"  Nodes: {stats['node_count']}")
        console.print(f"  Edges: {stats['edge_count']}")

        export_graph_html(G, output, title=title)
        console.print(f"[green]✓ Graph exported to {output}[/green]")

    except ImportError:
        console.print("[red]networkx is required for graph functionality[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


# =============================================================================
# Export command
# =============================================================================

@app.command("export")
def export_cmd(
    export_type: str = typer.Argument(..., help="Export type: requirements, risks, interfaces, summary"),
    output: Path = typer.Option(Path("export.md"), "--output", "-o", help="Output file"),
    system: Optional[str] = typer.Option(None, "--system", "-s", help="Filter by system"),
):
    """Export documents."""
    try:
        from .export import (
            export_requirements_markdown,
            export_risk_register_markdown,
            export_interface_list_markdown,
            export_summary_markdown,
        )

        core = QingsongCore.load()

        export_funcs = {
            "requirements": export_requirements_markdown,
            "risks": export_risk_register_markdown,
            "interfaces": export_interface_list_markdown,
            "summary": export_summary_markdown,
        }

        if export_type not in export_funcs:
            console.print(f"[red]Invalid export type: {export_type}[/red]")
            console.print(f"Valid types: {', '.join(export_funcs.keys())}")
            raise typer.Exit(1)

        func = export_funcs[export_type]
        if export_type == "summary":
            content = func(core, output_path=output)
        else:
            content = func(core, system_path=system, output_path=output)

        console.print(f"[green]✓ Exported to {output}[/green]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


# =============================================================================
# UI command
# =============================================================================

@app.command("ui")
def ui():
    """Launch Streamlit UI."""
    console.print("[bold]Launching Qingsong UI...[/bold]")

    try:
        ui_path = Path(__file__).parent / "ui" / "app_streamlit.py"
        if not ui_path.exists():
            console.print(f"[red]UI file not found: {ui_path}[/red]")
            raise typer.Exit(1)

        # Run streamlit
        subprocess.run([
            sys.executable, "-m", "streamlit", "run",
            str(ui_path),
            "--server.headless", "true",
        ])

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


# =============================================================================
# Summary command
# =============================================================================

@app.command("summary")
def summary():
    """Show repository summary."""
    try:
        core = QingsongCore.load()
        summary = core.summary()

        console.print(Panel.fit(
            f"[bold]Total Items:[/bold] {summary['total_items']}\n"
            f"[bold]Staged Changes:[/bold] {summary['staged_changes']}",
            title="Repository Summary"
        ))

        # Items by type
        table = Table(title="Items by Type")
        table.add_column("Type", style="cyan")
        table.add_column("Count", justify="right")
        for t, c in summary["items_by_type"].items():
            table.add_row(t, str(c))
        console.print(table)

        # Items by status
        table = Table(title="Items by Status")
        table.add_column("Status", style="green")
        table.add_column("Count", justify="right")
        for s, c in summary["items_by_status"].items():
            table.add_row(s, str(c))
        console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()

