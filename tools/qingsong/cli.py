"""
Command-line interface for Qingsong.

This module provides the main CLI entry point using Typer.
All commands are thin wrappers over the Core API.
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax

from . import __version__, get_project_root
from .core import QingsongCore
from .models import ItemType

# Create Typer app
app = typer.Typer(
    name="qingsong",
    help="Qingsong: Project Management Engine for MUST Telescope",
    add_completion=False,
)

# Global state for context
@dataclass
class GlobalState:
    root: Optional[Path] = None

state = GlobalState()

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
    root: Optional[Path] = typer.Option(
        None, "--root", "-r", help="Path to the Qingsong vault/project root"
    ),
):
    """Qingsong: Project Management Engine for MUST Telescope"""
    import os
    if root:
        state.root = root
        os.environ["QINGSONG_ROOT"] = str(root.resolve())


def get_core() -> QingsongCore:
    """Helper to load core with global root state."""
    from .load_meta import clear_cache as clear_meta_cache
    clear_meta_cache()
    return QingsongCore.load(project_root=state.root)

# =============================================================================
# Meta commands
# =============================================================================

@meta_app.command("validate")
def meta_validate():
    """Validate metadata files."""
    console.print("[bold]Validating metadata...[/bold]")

    try:
        core = get_core()
        errors = core.validate_metadata()

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
        core = get_core()
        metadata = core.metadata
        if not metadata:
            console.print("[red]Metadata not loaded.[/red]")
            raise typer.Exit(1)

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
        core = get_core()
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
        core = get_core()
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
        core = get_core()
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
        core = get_core()
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
# Init command
# =============================================================================

@app.command("init")
def init(
    path: Path = typer.Argument(..., help="Path to initialize the new Qingsong project"),
    name: str = typer.Option("My Project", "--name", "-n", help="Project name"),
):
    """Initialize a new Qingsong project structure in the specified directory."""
    try:
        if not path.exists():
            path.mkdir(parents=True)
            
        meta_dir = path / "meta"
        doorstop_dir = path / "doorstop"
        index_dir = path / "index"
        
        # Create directories
        meta_dir.mkdir(exist_ok=True)
        doorstop_dir.mkdir(exist_ok=True)
        index_dir.mkdir(exist_ok=True)
        (meta_dir / "vocab").mkdir(exist_ok=True)
        (meta_dir / "fps").mkdir(exist_ok=True)
        
        # Write default metadata files
        import yaml
        
        # hierarchy.yaml
        hierarchy = {
            "version": "1.0",
            "description": f"Hierarchy for {name}",
            "systems": {
                "SYS": {
                    "name": "Main System",
                    "owner": "pm001",
                    "subsystems": {
                        "SUB": {"name": "Subsystem 1", "owner": "eng001"}
                    }
                }
            },
            "valid_system_paths": ["SYS/SUB"],
            "valid_l3_codes": ["TASK-A", "TASK-B"]
        }
        with open(meta_dir / "hierarchy.yaml", "w") as f:
            yaml.dump(hierarchy, f, sort_keys=False)
            
        # people.yaml
        people = {
            "version": "1.0",
            "description": "Project team",
            "people": {
                "pm001": {"name": "Project Manager", "role": "PM", "active": True, "systems": []},
                "eng001": {"name": "Lead Engineer", "role": "Engineer", "active": True, "systems": ["SYS/SUB"]}
            },
            "valid_person_ids": ["pm001", "eng001"]
        }
        with open(meta_dir / "people.yaml", "w") as f:
            yaml.dump(people, f, sort_keys=False)
            
        # glossary.yaml
        glossary = {
            "version": "1.0",
            "terms": {
                "MUST": {
                    "definition": "MUltiplexed Survey Telescope",
                    "category": "project"
                }
            }
        }
        with open(meta_dir / "glossary.yaml", "w") as f:
            yaml.dump(glossary, f, sort_keys=False)
            
        # link_types.yaml (minimal)
        links = {
            "version": "1.0",
            "link_types": {
                "related_to": {
                    "label": "Related To",
                    "allowed_source_types": ["REQ", "RSK", "IFC", "DOC", "DAT", "NOTE"],
                    "allowed_target_types": ["REQ", "RSK", "IFC", "DOC", "DAT", "NOTE"]
                },
                "derives_from": {
                    "label": "Derives From",
                    "allowed_source_types": ["REQ"],
                    "allowed_target_types": ["REQ"]
                }
            },
            "valid_link_types": ["related_to", "derives_from"],
            "external_prefix": "EXT:"
        }
        with open(meta_dir / "vocab" / "link_types.yaml", "w") as f:
            yaml.dump(links, f, sort_keys=False)
            
        # status.yaml, req_category.yaml, etc. (minimal defaults)
        with open(meta_dir / "vocab" / "status.yaml", "w") as f:
            yaml.dump({"version": "1.0", "valid_values": ["draft", "active"]}, f)
        with open(meta_dir / "vocab" / "req_category.yaml", "w") as f:
            yaml.dump({"version": "1.0", "valid_paths": ["functional"]}, f)
        with open(meta_dir / "vocab" / "risk_category.yaml", "w") as f:
            yaml.dump({"version": "1.0", "valid_paths": ["technical"]}, f)
        with open(meta_dir / "vocab" / "ifc_type.yaml", "w") as f:
            yaml.dump({"version": "1.0", "valid_paths": ["mechanical"]}, f)
            
        console.print(f"[green]✓ Initialized new Qingsong project '{name}' at {path}[/green]")
        console.print("  [dim]Created meta/, doorstop/, and index/ directories.[/dim]")
        console.print("  [dim]Run 'qingsong --root <path> new req ...' to create your first item.[/dim]")
        
    except Exception as e:
        console.print(f"[red]Error initializing project: {e}[/red]")
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

        core = get_core()

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

        # Persist to disk immediately for CLI usage
        core.flush()

        console.print(f"[green]✓ Created item: {item.id_full}[/green]")
        console.print(f"  Type: {item.type.value}")
        console.print(f"  Title: {item.title}")
        console.print(f"  System: {item.system_path}")
        console.print(f"  Status: {item.status.value}")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


# =============================================================================
# Find command
# =============================================================================

@app.command("find")
def find(
    query: Optional[str] = typer.Argument(None, help="Keyword search query"),
    item_type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by type"),
    system: Optional[str] = typer.Option(None, "--system", "-s", help="Filter by system"),
    status: Optional[str] = typer.Option(None, "--status", help="Filter by status"),
    owner: Optional[str] = typer.Option(None, "--owner", "-o", help="Filter by owner"),
    limit: int = typer.Option(50, "--limit", "-n", help="Maximum items to show"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json"),
):
    """Search for items using keywords and filters."""
    try:
        core = get_core()
        results = []

        if query:
            # Use FTS5 search
            results = core.search(query)
        else:
            # Load all and filter manually (or we could use core.query but this is safer for staged items)
            results = [item.model_dump(mode="json") for item in core.items.values()]

        # Apply metadata filters
        if item_type:
            type_map = {"req": "REQ", "rsk": "RSK", "ifc": "IFC", "doc": "DOC", "dat": "DAT", "note": "NOTE"}
            t = type_map.get(item_type.lower(), item_type.upper())
            results = [r for r in results if r["type"] == t]

        if system:
            results = [r for r in results if r["system_path"] == system]

        if status:
            results = [r for r in results if r["status"] == status]

        if owner:
            results = [r for r in results if r["owner"] == owner]

        # Sort by rank (if search) or ID
        if not query:
            results.sort(key=lambda x: x["id_full"])

        # Limit
        total = len(results)
        results = results[:limit]

        if format == "json":
            import json
            console.print(json.dumps(results, indent=2, default=str))
            return

        if not results:
            console.print("[yellow]No items found.[/yellow]")
            return

        # Display table
        table = Table(title=f"Search Results ({len(results)} of {total})")
        table.add_column("ID", style="cyan")
        table.add_column("Type")
        table.add_column("Title")
        table.add_column("System", style="green")
        table.add_column("Status")
        table.add_column("Owner")

        for r in results:
            status_style = "green" if r["status"] == "active" else "yellow"
            table.add_row(
                r["id_full"],
                r["type"],
                r["title"][:40] + "..." if len(r["title"]) > 40 else r["title"],
                r["system_path"],
                f"[{status_style}]{r['status']}[/{status_style}]",
                r["owner"],
            )

        console.print(table)

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
        core = get_core()
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
        core = get_core()
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

        core = get_core()

        if item_id:
            console.print(f"[bold]Building neighborhood graph for {item_id}...[/bold]")
            G = get_neighborhood(core.items, item_id, depth=depth)
            title = f"Neighborhood of {item_id}"
        else:
            console.print("[bold]Building full graph...[/bold]")
            G = build_graph(core.items)
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
    export_type: str = typer.Argument(..., help="Export type: requirements, risks, interfaces, summary, all"),
    output: Path = typer.Option(Path("export.md"), "--output", "-o", help="Output file"),
    format: str = typer.Option("markdown", "--format", "-f", help="Output format: markdown, csv"),
    system: Optional[str] = typer.Option(None, "--system", "-s", help="Filter by system"),
):
    """Export documents in various formats."""
    try:
        from .export import (
            export_requirements_markdown,
            export_risk_register_markdown,
            export_interface_list_markdown,
            export_summary_markdown,
            export_to_csv,
        )

        core = get_core()

        if format == "csv":
            if export_type == "all":
                items = list(core.items.values())
            else:
                type_map = {
                    "requirements": ItemType.REQ,
                    "risks": ItemType.RSK,
                    "interfaces": ItemType.IFC,
                }
                it = type_map.get(export_type)
                if not it:
                    console.print(f"[red]Invalid type for CSV export: {export_type}[/red]")
                    raise typer.Exit(1)
                items = core.get_items_by_type(it)
            
            if system:
                items = [i for i in items if i.system_path == system]
                
            export_to_csv(items, output)
            console.print(f"[green]✓ Exported {len(items)} items to CSV: {output}[/green]")
            return

        # Markdown exports
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

        console.print(f"[green]✓ Exported {export_type} to Markdown: {output}[/green]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


# =============================================================================
# Verification command
# =============================================================================

@app.command("verify")
def verify_cmd():
    """Show requirement verification status summary."""
    try:
        core = get_core()
        summary = core.get_verification_summary()

        if summary["total"] == 0:
            console.print("[yellow]No requirements found to verify.[/yellow]")
            return

        console.print(Panel.fit(
            f"[bold]Total Requirements:[/bold] {summary['total']}\n"
            f"[bold]Verified:[/bold] {summary['verified']} ({summary['percent']:.1f}%)\n"
            f"[bold]Pending:[/bold] {summary['total'] - summary['verified']}",
            title="Verification Dashboard"
        ))

        # By method
        table_m = Table(title="By Verification Method")
        table_m.add_column("Method", style="cyan")
        table_m.add_column("Count", justify="right")
        for m, c in summary["by_method"].items():
            table_m.add_row(m, str(c))
        console.print(table_m)

        # By system
        table_s = Table(title="By System")
        table_s.add_column("System", style="green")
        table_s.add_column("Total")
        table_s.add_column("Verified")
        table_s.add_column("Progress")

        for s, stats in summary["by_system"].items():
            p = (stats["verified"] / stats["total"]) * 100
            progress_bar = "█" * int(p/10) + "░" * (10 - int(p/10))
            table_s.add_row(s, str(stats["total"]), str(stats["verified"]), f"{progress_bar} {p:.1f}%")
        
        console.print(table_s)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


# =============================================================================
# Traceability command
# =============================================================================

@app.command("trace")
def trace(
    direction: str = typer.Option("downward", "--direction", "-d", help="Direction: upward, downward"),
    format: str = typer.Option("table", "--format", "-f", help="Format: table, csv, json"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file"),
):
    """Generate traceability matrix for requirements."""
    try:
        core = get_core()
        matrix = core.get_traceability_matrix(direction=direction)

        if format == "json":
            import json
            content = json.dumps(matrix, indent=2, default=str)
            if output:
                output.write_text(content)
            else:
                console.print(content)
            return

        if format == "csv":
            import csv
            import io
            f = io.StringIO()
            writer = csv.writer(f)
            writer.writerow(["Requirement ID", "Title", "Linked IDs", "Link Types"])
            for row in matrix:
                linked_ids = ", ".join([l["id"] for l in row["links"]])
                link_types = ", ".join([l["type"] for l in row["links"]])
                writer.writerow([row["id"], row["title"], linked_ids, link_types])
            
            content = f.getvalue()
            if output:
                output.write_text(content)
                console.print(f"[green]✓ Exported to {output}[/green]")
            else:
                console.print(content)
            return

        # Table/Markdown
        table = Table(title=f"{direction.capitalize()} Traceability Matrix")
        table.add_column("Requirement", style="cyan")
        table.add_column("Title")
        table.add_column("Links", style="green")

        for row in matrix:
            links_str = "\n".join([f"• {l['id']} ({l['type']})" for l in row['links']])
            if not links_str:
                links_str = "[red]NO LINKS[/red]"
            table.add_row(row["id"], row["title"][:40], links_str)

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


# =============================================================================
# Migration command
# =============================================================================

@app.command("migrate")
def migrate(
    item_id: str = typer.Argument(..., help="Item ID to migrate"),
    new_system: str = typer.Option(..., "--system", "-s", help="New system path (e.g., SPS/DET)"),
    new_l3: Optional[str] = typer.Option(None, "--l3", help="New L3 task code"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would change without writing to disk"),
):
    """Migrate an item to a new system/folder and update all links."""
    try:
        core = get_core()
        
        # Check if item exists
        item = core.get_item(item_id)
        if not item:
            console.print(f"[red]Item not found: {item_id}[/red]")
            raise typer.Exit(1)
            
        console.print(f"[bold]Migrating {item_id} to {new_system}{'/' + new_l3 if new_l3 else ''}...[/bold]")
        
        # Perform migration (staged)
        migrated = core.migrate_item(item_id, new_system, new_l3)
        
        console.print(f"[green]✓ Item staged for migration: {item_id} → {migrated.id_full}[/green]")
        
        # List other items being updated
        affected_links = [cid for cid, change in core.staged_changes.items() 
                         if change.action == "update" and cid != migrated.id_full]
        
        if affected_links:
            console.print(f"  [bold]{len(affected_links)} incoming links updated:[/bold]")
            for cid in affected_links:
                console.print(f"    - {cid}")
        
        if dry_run:
            console.print("\n[yellow]Dry run: discarding changes.[/yellow]")
            core.discard_changes()
        else:
            count = core.flush()
            console.print(f"\n[bold green]✓ Migration complete. {count} files updated/deleted.[/bold green]")
            
            # Rebuild cache to reflect new IDs
            console.print("[bold]Rebuilding cache...[/bold]")
            core.build_cache()

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
        core = get_core()
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

