"""Command-line interface. Commands are added phase by phase (docs/SPEC.md §11)."""

import typer

from qingsong import __version__

app = typer.Typer(no_args_is_help=True, add_completion=False)


def show_version(requested: bool) -> None:
    if requested:
        typer.echo(f"qingsong {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=show_version, is_eager=True, help="Print the version."
    ),
) -> None:
    """Requirements kept as checked, versioned engineering records."""
