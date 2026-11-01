"""Command-line interface (docs/SPEC.md §11). Every command accepts --vault and --json."""

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from pydantic import TypeAdapter

from qingsong import __version__, checks, operations
from qingsong.operations import OperationError
from qingsong.schema import Record, record_classes
from qingsong.vault import Vault, VaultNotFoundError, find_root, load
from qingsong.walk import localized_texts

app = typer.Typer(no_args_is_help=True, add_completion=False)

VaultOption = Annotated[
    Path | None, typer.Option("--vault", help="Vault root; default: nearest qingsong.toml.")
]
JsonOption = Annotated[bool, typer.Option("--json", help="Machine-readable output.")]
PersonOption = Annotated[
    str, typer.Option("--by", help="Person ID (people.yaml) making the change.")
]
ViaOption = Annotated[
    str | None, typer.Option("--via", help="Agent acting for the person, if any.")
]


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


def vault_root(vault: Path | None) -> Path:
    try:
        return (
            find_root(vault)
            if vault is None or not (vault / "qingsong.toml").exists()
            else vault.resolve()
        )
    except VaultNotFoundError as error:
        typer.echo(f"error: {error}", err=True)
        raise typer.Exit(2) from error


def emit(data: Any, as_json: bool, text: str) -> None:
    typer.echo(json.dumps(data, ensure_ascii=False, indent=2, default=str) if as_json else text)


def fail(error: Exception, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps({"error": str(error)}, ensure_ascii=False))
    else:
        typer.echo(f"error: {error}", err=True)
    raise typer.Exit(2)


def done(record: Any, as_json: bool, verb: str) -> None:
    emit(
        {
            "id": record.id,
            "revision": record.revision,
            "normative_revision": record.normative_revision,
            "stamp": record.stamp,
        },
        as_json,
        f"{verb} {record.id} (revision {record.revision})",
    )


@app.command()
def check(
    vault: VaultOption = None,
    against: Annotated[
        str | None, typer.Option(help="Git reference to compare with, e.g. origin/main.")
    ] = None,
    rule: Annotated[list[str] | None, typer.Option(help="Run only these rules.")] = None,
    as_json: JsonOption = False,
) -> None:
    """Run the consistency checks; exit 1 if any error is found."""
    root = vault_root(vault)
    findings = checks.run(load(root), against=against, selected=set(rule) if rule else None)
    errors = sum(1 for finding in findings if finding.severity == "error")
    warnings = sum(1 for finding in findings if finding.severity == "warning")
    if as_json:
        typer.echo(
            json.dumps(
                {
                    "errors": errors,
                    "warnings": warnings,
                    "findings": [finding.as_dict() for finding in findings],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        for finding in findings:
            typer.echo(finding.line())
        typer.echo(
            f"{errors} errors, {warnings} warnings, {len(findings) - errors - warnings} notes"
        )
    raise typer.Exit(1 if errors else 0)


@app.command()
def rules(as_json: JsonOption = False) -> None:
    """List the check rules."""
    summaries = checks.all_rule_summaries()
    emit(
        summaries,
        as_json,
        "\n".join(f"{rule_id:34s} {text}" for rule_id, text in summaries.items()),
    )


@app.command()
def init(
    path: Path,
    code: Annotated[str, typer.Option(help="Project code, e.g. DEMO.")],
    name: Annotated[str, typer.Option(help="Project name in English.")],
    as_json: JsonOption = False,
) -> None:
    """Create an empty vault."""
    try:
        created = operations.init_vault(path, code, name)
    except OperationError as error:
        fail(error, as_json)
    emit({"vault": str(created)}, as_json, f"created vault {created}")


new_app = typer.Typer(no_args_is_help=True, help="Create a record with a newly allocated ID.")
app.add_typer(new_app, name="new")


@new_app.command("requirement")
def new_requirement(
    namespace: Annotated[str, typer.Option(help="Namespace, e.g. INS-DET or DEMO-SRV.")],
    title: Annotated[str, typer.Option(help="Title in the reference language.")],
    statement: Annotated[str, typer.Option(help="Statement in the reference language.")],
    by: PersonOption,
    level: Annotated[str | None, typer.Option(help="Level; default from the namespace.")] = None,
    via: ViaOption = None,
    vault: VaultOption = None,
    as_json: JsonOption = False,
) -> None:
    """Allocate the next requirement ID in a namespace and write a concept requirement."""
    try:
        record = operations.new_requirement(
            vault_root(vault), namespace, title, statement, by, level=level, via=via
        )
    except OperationError as error:
        fail(error, as_json)
    done(record, as_json, "created")


@app.command()
def adopt(
    file: Path,
    summary: Annotated[str, typer.Option(help="Why the record was written (e.g. its source).")],
    by: PersonOption,
    event: Annotated[str, typer.Option(help="created or imported.")] = "imported",
    translation: Annotated[
        str, typer.Option(help="Status of the second-language text: machine or reviewed.")
    ] = "machine",
    via: ViaOption = None,
    vault: VaultOption = None,
    as_json: JsonOption = False,
) -> None:
    """Take a hand-written record file into the record (adds history and stamp)."""
    try:
        record = operations.adopt(
            vault_root(vault),
            file.resolve(),
            by,
            summary,
            event=event,
            translation=translation,
            via=via,
        )
    except OperationError as error:
        fail(error, as_json)
    done(record, as_json, "adopted")


@app.command()
def revise(
    record_id: Annotated[str, typer.Argument(metavar="ID")],
    change_class: Annotated[str, typer.Option("--class", help="editorial, value or reallocate.")],
    summary: Annotated[str, typer.Option(help="What changed and why.")],
    by: PersonOption,
    decision: Annotated[
        str | None, typer.Option(help="Decision record, required for baselined.")
    ] = None,
    translation: Annotated[str, typer.Option(help="unchanged, updated or reviewed.")] = "unchanged",
    to_draft: Annotated[
        bool, typer.Option("--to-draft", help="Promote a concept requirement to draft.")
    ] = False,
    via: ViaOption = None,
    vault: VaultOption = None,
    as_json: JsonOption = False,
) -> None:
    """Record a change made to a record file."""
    if change_class not in ("editorial", "value", "reallocate"):
        fail(OperationError("--class must be editorial, value or reallocate"), as_json)
    if translation not in ("unchanged", "updated", "reviewed"):
        fail(OperationError("--translation must be unchanged, updated or reviewed"), as_json)
    try:
        record = operations.revise(
            vault_root(vault),
            record_id,
            change_class,
            summary,
            by,
            decision=decision,
            translation=translation,
            to_draft=to_draft,
            via=via,
        )
    except OperationError as error:
        fail(error, as_json)
    done(record, as_json, "revised")


@app.command()
def supersede(
    record_id: Annotated[str, typer.Argument(metavar="ID")],
    successors: Annotated[
        list[str], typer.Option("--with", help="Successor ID (repeat for a split).")
    ],
    summary: Annotated[str, typer.Option(help="Why.")],
    by: PersonOption,
    decision: Annotated[str | None, typer.Option(help="Decision record.")] = None,
    via: ViaOption = None,
    vault: VaultOption = None,
    as_json: JsonOption = False,
) -> None:
    """Mark a record as superseded by one or more successors."""
    try:
        record = operations.supersede(
            vault_root(vault), record_id, successors, summary, by, decision=decision, via=via
        )
    except OperationError as error:
        fail(error, as_json)
    done(record, as_json, "superseded")


@app.command()
def withdraw(
    record_id: Annotated[str, typer.Argument(metavar="ID")],
    reason: Annotated[str, typer.Option(help="Why the record is no longer needed.")],
    by: PersonOption,
    decision: Annotated[str | None, typer.Option(help="Decision record.")] = None,
    via: ViaOption = None,
    vault: VaultOption = None,
    as_json: JsonOption = False,
) -> None:
    """Withdraw a record; its ID is retired for good."""
    try:
        record = operations.withdraw(
            vault_root(vault), record_id, reason, by, decision=decision, via=via
        )
    except OperationError as error:
        fail(error, as_json)
    done(record, as_json, "withdrew")


@app.command()
def approve(
    record_id: Annotated[str, typer.Argument(metavar="ID")],
    to: Annotated[str, typer.Option(help="agreed, or draft to reopen.")],
    by: PersonOption,
    ref: Annotated[str, typer.Option(help="Pull request or meeting where the approval was given.")],
    via: ViaOption = None,
    vault: VaultOption = None,
    as_json: JsonOption = False,
) -> None:
    """Record an approver's maturity decision."""
    try:
        record = operations.approve(vault_root(vault), record_id, to, by, ref, via=via)
    except OperationError as error:
        fail(error, as_json)
    done(record, as_json, "approved")


@app.command()
def confirm(
    child: str,
    parent: str,
    by: PersonOption,
    via: ViaOption = None,
    vault: VaultOption = None,
    as_json: JsonOption = False,
) -> None:
    """Clear a suspect link after reviewing the child against its changed parent."""
    try:
        record = operations.confirm(vault_root(vault), child, parent, by, via=via)
    except OperationError as error:
        fail(error, as_json)
    done(record, as_json, "confirmed")


@app.command()
def renumber(
    old: str,
    new: str,
    by: PersonOption,
    unmerged: Annotated[
        bool, typer.Option("--unmerged", help="Required: the record is not yet on main.")
    ] = False,
    via: ViaOption = None,
    vault: VaultOption = None,
    as_json: JsonOption = False,
) -> None:
    """Move a record that has not reached main to a free number, rewriting references."""
    if not unmerged:
        fail(
            OperationError("renumbering is only for records not yet on main; pass --unmerged"),
            as_json,
        )
    try:
        record = operations.renumber(vault_root(vault), old, new, by, via=via)
    except OperationError as error:
        fail(error, as_json)
    done(record, as_json, "renumbered to")


def loaded(vault: Path | None) -> Vault:
    return load(vault_root(vault))


@app.command()
def show(
    record_id: Annotated[str, typer.Argument(metavar="ID")],
    vault: VaultOption = None,
    as_json: JsonOption = False,
) -> None:
    """Show one record."""
    records = loaded(vault).records
    if record_id not in records:
        fail(OperationError(f"no record {record_id}"), as_json)
    data = records[record_id].model_dump(mode="json", exclude_none=True)
    lines = [
        f"{key}: {json.dumps(value, ensure_ascii=False)}"
        for key, value in data.items()
        if key != "history"
    ]
    lines.append(f"history: {len(data['history'])} events")
    emit(data, as_json, "\n".join(lines))


@app.command("list")
def list_records(
    record_type: Annotated[str | None, typer.Option("--type", help="Record type.")] = None,
    node: Annotated[str | None, typer.Option(help="Allocated node reference.")] = None,
    maturity: Annotated[str | None, typer.Option(help="Maturity.")] = None,
    vault: VaultOption = None,
    as_json: JsonOption = False,
) -> None:
    """List records, optionally filtered."""
    rows = []
    for record in sorted(loaded(vault).records.values(), key=lambda item: item.id):
        if record_type and record.type != record_type:
            continue
        if node and getattr(record, "allocated_to", None) != node:
            continue
        if maturity and getattr(record, "maturity", None) != maturity:
            continue
        title = record.title.get("en") or next(iter(record.title.values()), "")
        rows.append(
            {
                "id": record.id,
                "type": record.type,
                "lifecycle": record.lifecycle,
                "maturity": getattr(record, "maturity", None),
                "title": title,
            }
        )
    text = "\n".join(
        f"{row['id']:28s} {row['type']:12s} {row['maturity'] or '':9s} {row['title']}"
        for row in rows
    )
    emit(rows, as_json, text or "no records")


@app.command()
def find(text: str, vault: VaultOption = None, as_json: JsonOption = False) -> None:
    """Find records whose ID, aliases or texts contain TEXT (any language)."""
    needle = text.lower()
    hits = []
    for record in sorted(loaded(vault).records.values(), key=lambda item: item.id):
        places = [f"alias {alias.id}" for alias in record.aliases if needle in alias.id.lower()]
        if needle in record.id.lower():
            places.append("id")
        for path, texts in localized_texts(record):
            for language, value in texts.items():
                if needle in value.lower():
                    places.append(f"{path}.{language}")
        if places:
            hits.append({"id": record.id, "type": record.type, "where": places})
    emit(
        hits,
        as_json,
        "\n".join(f"{hit['id']:28s} {', '.join(hit['where'][:4])}" for hit in hits)
        or "nothing found",
    )


render_app = typer.Typer(no_args_is_help=True, help="Generate documents from the records.")
app.add_typer(render_app, name="render")


@render_app.command("html")
def render_html(
    output: Annotated[Path, typer.Argument(help="Folder for the site (replaced if it exists).")],
    vault: VaultOption = None,
    as_json: JsonOption = False,
) -> None:
    """Generate the static HTML site; open OUTPUT/index.html in a browser."""
    from qingsong.render.html import render_site

    index = render_site(loaded(vault), output.resolve())
    emit({"index": str(index)}, as_json, f"wrote {index}")


@render_app.command("docx")
def render_word(
    document: Annotated[str, typer.Argument(help="Document ID, e.g. DEMO-INS-DET-RD.")],
    output: Annotated[Path, typer.Argument(help="Path of the .docx file to write.")],
    version: Annotated[
        str | None, typer.Option(help="Version shown on the cover and header.")
    ] = None,
    vault: VaultOption = None,
    as_json: JsonOption = False,
) -> None:
    """Generate a Word document from the records (styles from templates/reference.docx)."""
    from qingsong.render.word import render_docx

    try:
        written = render_docx(loaded(vault), document, output.resolve(), version=version)
    except ValueError as error:
        fail(error, as_json)
    emit({"docx": str(written)}, as_json, f"wrote {written}")


@app.command()
def schema(record_type: Annotated[str | None, typer.Argument(metavar="TYPE")] = None) -> None:
    """Print the JSON Schema of all records, or of one record type."""
    if record_type:
        if record_type not in record_classes:
            typer.echo(
                f"error: unknown type {record_type}; known: {', '.join(record_classes)}", err=True
            )
            raise typer.Exit(2)
        document = record_classes[record_type].model_json_schema()
    else:
        document = TypeAdapter(Record).json_schema()
    typer.echo(json.dumps(document, ensure_ascii=False, indent=2))
