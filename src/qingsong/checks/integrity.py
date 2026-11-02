"""Integrity rules: identifiers, paths, references, and comparison with an earlier version."""

import json
from collections.abc import Iterator
from io import StringIO
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from qingsong import gitutil, ids
from qingsong.checks import Context, relative_file, rule
from qingsong.findings import Finding
from qingsong.hashing import file_sha256
from qingsong.schema import Document, Section, plain, record_folders
from qingsong.vault import Vault, expected_path
from qingsong.walk import text_references


@rule("integrity.duplicate_id", "an ID is defined by one file only")
def duplicate_ids(context: Context) -> Iterator[Finding]:
    vault = context.vault
    for record_id, path in vault.duplicates:
        first = relative_file(vault, record_id)
        yield Finding(
            "integrity.duplicate_id",
            "error",
            f"also defined in {first}",
            record=record_id,
            file=vault.relative(path),
            fix="give one of the records a new ID",
        )


@rule("integrity.id_syntax", "every ID follows the pattern of its record type")
def id_syntax(context: Context) -> Iterator[Finding]:
    for record in context.vault.records.values():
        file = relative_file(context.vault, record.id)
        if not ids.id_matches(record.type, record.id):
            yield Finding(
                "integrity.id_syntax",
                "error",
                f"{record.id!r} is not a valid {record.type} ID",
                record=record.id,
                file=file,
            )
        elif record.type == "verification":
            embedded = ids.id_patterns["verification"].match(record.id).group("requirement")
            if embedded != record.requirement:
                yield Finding(
                    "integrity.id_syntax",
                    "error",
                    f"the ID names {embedded} but the record verifies {record.requirement}",
                    record=record.id,
                    file=file,
                )


@rule("integrity.path_mismatch", "each file is stored where its ID says")
def path_mismatch(context: Context) -> Iterator[Finding]:
    vault = context.vault
    for record in vault.records.values():
        if not ids.id_matches(record.type, record.id):
            continue
        expected = expected_path(vault, record)
        if vault.files[record.id].resolve() != expected.resolve():
            yield Finding(
                "integrity.path_mismatch",
                "error",
                f"stored at {relative_file(vault, record.id)}",
                record=record.id,
                fix=f"move it to {vault.relative(expected)}",
            )


def section_keys(document: Document) -> set[str]:
    keys: set[str] = set()

    def visit(blocks: list) -> None:
        for block in blocks:
            if block.section is not None:
                section: Section = block.section
                keys.add(section.key)
                visit(section.blocks)

    visit(document.outline)
    return keys


def references(vault: Vault) -> Iterator[tuple[str, str, str, str | None]]:
    """Yield (record ID, field, target, expected kind) for every reference held in a record."""
    for record in vault.records.values():
        for event in record.history:
            yield record.id, "history.by", event.by, "person"
            if event.decision:
                yield record.id, "history.decision", event.decision, "decision"
        for successor in record.superseded_by:
            yield record.id, "superseded_by", successor, record.type
        for path, target, key in text_references(record):
            yield record.id, path, target if key is None else f"{target}#{key}", "text"
        kind = record.type
        if kind == "requirement":
            yield record.id, "allocated_to", record.allocated_to, "node"
            for link in record.derives_from:
                yield record.id, "derives_from", link.id, "requirement"
            for link in record.constrained_by:
                yield record.id, "constrained_by", link.id, "condition"
            if record.justified_by:
                yield record.id, "justified_by", record.justified_by, "decision"
            if record.interface:
                yield record.id, "interface", record.interface, "interface"
            for issue in record.issues:
                yield record.id, "issues", issue, "issue"
            for citation in record.sources:
                yield record.id, "sources", citation.source, "source"
            for variant in record.variants:
                yield record.id, "variants.source", variant.source, "source"
            if record.approval:
                yield record.id, "approval.by", record.approval.by, "person"
            for name, state in record.translation.items():
                if state.by:
                    yield record.id, f"translation.{name}.by", state.by, "person"
        if kind in ("requirement", "condition", "interface"):
            for name, slot in record.values.items():
                if slot.quantity:
                    yield record.id, f"values.{name}.quantity", slot.quantity, "quantity"
                if slot.issue:
                    yield record.id, f"values.{name}.issue", slot.issue, "issue"
        if kind == "condition":
            yield record.id, "node", record.node, "node"
            for citation in record.sources:
                yield record.id, "sources", citation.source, "source"
        if kind == "issue":
            if record.owner:
                yield record.id, "owner", record.owner, "person"
            for target in record.records:
                yield record.id, "records", target, None
        if kind == "decision":
            yield record.id, "by", record.by, "person"
            for target in record.records:
                yield record.id, "records", target, None
        if kind == "interface":
            yield record.id, "owner_end", record.owner_end, "node"
            yield record.id, "other_end", record.other_end, "node"
        if kind == "verification":
            yield record.id, "requirement", record.requirement, "requirement"
            for evidence in record.evidence:
                if evidence.kind == "source":
                    yield record.id, "evidence", evidence.reference, "source"
        if kind == "waiver":
            yield record.id, "requirement", record.requirement, "requirement"
            yield record.id, "approver", record.approver, "person"
        if kind == "baseline":
            for target in record.records:
                yield record.id, "records", target, None
        if kind == "document":
            yield from document_references(record)


def document_references(document: Document) -> Iterator[tuple[str, str, str, str | None]]:
    for role in document.front.roles:
        yield document.id, "front.roles", role.person, "person"
    for source in document.front.reference_documents:
        yield document.id, "front.reference_documents", source, "source"
    for term in document.front.acronyms:
        yield document.id, "front.acronyms", term, "term"

    def visit(blocks: list, where: str) -> Iterator[tuple[str, str, str, str | None]]:
        for block in blocks:
            if block.requirement:
                yield document.id, where, block.requirement, "requirement"
            if block.figure:
                yield document.id, where, block.figure, "figure"
            if block.definitions:
                for term in block.definitions.terms:
                    yield document.id, where, term, "term"
            if block.section:
                yield from visit(block.section.blocks, f"{where}/{block.section.key}")

    yield from visit(document.outline, "outline")


@rule(
    "integrity.unresolved_reference",
    "every referenced record, node, person, quantity and term exists",
)
def unresolved_references(context: Context) -> Iterator[Finding]:
    vault = context.vault
    people = set(vault.people.people) if vault.people else set()
    terms = set(vault.glossary.terms) if vault.glossary else set()
    for record_id, field, target, kind in references(vault):
        problem = None
        if kind == "person":
            problem = None if target in people else f"person {target!r} is not in people.yaml"
        elif kind == "node":
            problem = None if target in vault.nodes else f"node {target!r} is not in the tree"
        elif kind == "term":
            problem = None if target in terms else f"term {target!r} is not in glossary.yaml"
        elif kind == "text":
            base, _, key = target.partition("#")
            if base not in vault.records:
                problem = f"text reference [[{target}]] points to no record"
            elif key:
                document = vault.records[base]
                if not isinstance(document, Document) or key not in section_keys(document):
                    problem = f"text reference [[{target}]]: no section {key!r} in {base}"
        else:
            other = vault.records.get(target)
            if other is None:
                problem = f"{field} points to {target}, which does not exist"
            elif kind and other.type != kind:
                problem = f"{field} points to {target}, a {other.type}, not a {kind}"
        if problem:
            yield Finding(
                "integrity.unresolved_reference",
                "error",
                problem,
                record=record_id,
                file=relative_file(vault, record_id),
            )


def records_at(root: Path, ref: str) -> dict[str, dict]:
    result: dict[str, dict] = {}
    loader = YAML(typ="safe", pure=True)
    for folder in record_folders.values():
        for name in gitutil.files_at(root, ref, folder):
            if not name.endswith(".yaml"):
                continue
            text = gitutil.read_at(root, ref, name)
            try:
                data = plain(loader.load(StringIO(text or "")))
            except YAMLError:
                continue
            if isinstance(data, dict) and isinstance(data.get("id"), str):
                result[data["id"]] = data
    return result


def nodes_at(root: Path, ref: str) -> set[str]:
    references_found: set[str] = set()
    loader = YAML(typ="safe", pure=True)
    for name in gitutil.files_at(root, ref, "tree"):
        try:
            data = plain(loader.load(StringIO(gitutil.read_at(root, ref, name) or "")))
        except YAMLError:
            continue
        if not isinstance(data, dict):
            continue
        system = data.get("node") if data.get("parent") else None
        collect_node_references(data, system, 1 if system else 0, references_found)
    return references_found


def collect_node_references(node: dict, system: str | None, depth: int, found: set[str]) -> None:
    code = node.get("node")
    found.add(code if depth <= 1 else f"{system}-{code}")
    for child in node.get("children") or []:
        collect_node_references(child, system, depth + 1, found)


lifecycle_rank = {"current": 0, "superseded": 1, "withdrawn": 1}


@rule(
    "integrity.against",
    "compared with an earlier version: nothing removed, retyped, rewritten or reversed",
)
def against_reference(context: Context) -> Iterator[Finding]:
    vault, ref = context.vault, context.against
    if not ref:
        return
    if not gitutil.ref_exists(vault.root, ref):
        yield Finding(
            "integrity.against",
            "error",
            f"git reference {ref!r} not found",
            fix="fetch it, or pass another --against",
        )
        return
    earlier = records_at(vault.root, ref)
    for record_id, data in earlier.items():
        record = vault.records.get(record_id)
        if record is None:
            loaded_elsewhere = any(record_id == duplicate for duplicate, _ in vault.duplicates)
            if not loaded_elsewhere and not any(f.record == record_id for f in vault.load_findings):
                yield Finding(
                    "integrity.against",
                    "error",
                    f"{record_id} existed at {ref} and is gone",
                    record=record_id,
                    fix="records are never deleted: restore the file and withdraw the record",
                )
            continue
        if data.get("type") != record.type:
            yield Finding(
                "integrity.against",
                "error",
                f"was a {data.get('type')} at {ref}, now a {record.type}",
                record=record_id,
            )
        old_history = data.get("history") or []
        new_history = [event.model_dump(mode="json", exclude_none=True) for event in record.history]
        if [plain_event(event) for event in old_history] != [
            plain_event(event) for event in new_history[: len(old_history)]
        ]:
            yield Finding(
                "integrity.against",
                "error",
                f"history entries recorded at {ref} were changed",
                record=record_id,
                fix="history is append-only",
            )
        if (
            data.get("normative_hash") != record.normative_hash
            and data.get("normative_revision") == record.normative_revision
            and not slotted_since(record, data.get("normative_hash"), data.get("revision"))
        ):
            yield Finding(
                "integrity.against",
                "error",
                f"values, level or verification methods differ from {ref} but the normative "
                "revision did not change",
                record=record_id,
                fix="record the change as a 'value' change (qingsong revise --class value)",
            )
        if isinstance(record, Document):
            yield from changed_releases(record, data.get("releases") or [], ref)
        if lifecycle_rank.get(str(data.get("lifecycle")), 0) > lifecycle_rank[record.lifecycle]:
            yield Finding(
                "integrity.against",
                "error",
                f"lifecycle went back from {data.get('lifecycle')} to {record.lifecycle}",
                record=record_id,
            )
    for reference in sorted(nodes_at(vault.root, ref) - set(vault.nodes)):
        yield Finding(
            "integrity.against",
            "error",
            f"node {reference} existed at {ref} and is gone",
            file="tree",
            fix="nodes are retired (status: retired), never removed or moved",
        )


def slotted_since(record, earlier_hash: object, earlier_revision: object) -> bool:
    """The normative hash changed only by recorded moves of numbers into slots: the `slotted`
    events since the reference lead, hash to hash, from the earlier hash to the current one."""
    if not isinstance(earlier_revision, int):
        return False
    current = earlier_hash
    moved = False
    for event in record.history:
        if event.revision <= earlier_revision or event.event != "slotted":
            continue
        if event.normative_hash_before != current:
            return False
        current, moved = event.normative_hash_after, True
    return moved and current == record.normative_hash


def comparable(value: object) -> object:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def changed_releases(document: Document, earlier: list, ref: str) -> Iterator[Finding]:
    """Release entries are append-only; a release made before qingsong may gain its tag."""
    current = [entry.model_dump(mode="json", exclude_none=True) for entry in document.releases]
    for index, old in enumerate(earlier):
        new = current[index] if index < len(current) else None
        if new is not None and not new.get("made_with_qingsong") and "tag" not in old:
            new = {key: value for key, value in new.items() if key != "tag"}
        if new is None or comparable(old) != comparable(new):
            version = old.get("version") if isinstance(old, dict) else index + 1
            yield Finding(
                "integrity.against",
                "error",
                f"release {version} recorded at {ref} was changed or removed",
                record=document.id,
                fix="release entries are append-only; a correction is a new version",
            )


def plain_event(event: dict) -> dict:
    return {key: str(value) for key, value in event.items() if value is not None}


@rule("integrity.figure_file", "figure images exist next to their record and match their sha256")
def figure_files(context: Context) -> Iterator[Finding]:
    vault = context.vault
    for record in vault.records.values():
        if record.type != "figure":
            continue
        folder = vault.files[record.id].parent
        for image in record.files:
            path = folder / image.path
            if not path.is_file():
                yield Finding(
                    "integrity.figure_file",
                    "error",
                    f"image {image.path} is missing",
                    record=record.id,
                    file=relative_file(vault, record.id),
                )
            elif file_sha256(path) != image.sha256:
                yield Finding(
                    "integrity.figure_file",
                    "error",
                    f"image {image.path} changed since it was recorded",
                    record=record.id,
                    file=relative_file(vault, record.id),
                    fix="update its sha256 and record the change with qingsong revise",
                )


@rule("integrity.proposal", "issues name known rules; proposals name known records and fields")
def proposals(context: Context) -> Iterator[Finding]:
    from qingsong.checks import all_rule_summaries
    from qingsong.schema import Issue

    vault = context.vault
    known_rules = set(all_rule_summaries())
    for record in vault.records.values():
        if not isinstance(record, Issue):
            continue
        file = relative_file(vault, record.id)
        if record.rule and record.rule not in known_rules:
            yield Finding(
                "integrity.proposal",
                "error",
                f"unknown check rule {record.rule}",
                record=record.id,
                file=file,
                fix="see qingsong rules",
            )
        numbers = [proposal.number for proposal in (record.proposals or [])]
        if len(numbers) != len(set(numbers)):
            yield Finding(
                "integrity.proposal",
                "error",
                "proposal numbers repeat",
                record=record.id,
                file=file,
            )
        for proposal in record.proposals or []:
            for change in proposal.changes:
                target = vault.records.get(change.record)
                if target is None:
                    yield Finding(
                        "integrity.proposal",
                        "error",
                        f"proposal {proposal.number} changes unknown record {change.record}",
                        record=record.id,
                        file=file,
                    )
                elif change.field.split(".")[0] not in type(target).model_fields:
                    yield Finding(
                        "integrity.proposal",
                        "error",
                        f"proposal {proposal.number}: {change.record} has no field {change.field}",
                        record=record.id,
                        file=file,
                    )
        if record.status == "closed" and any(
            p.status == "proposed" for p in (record.proposals or [])
        ):
            yield Finding(
                "integrity.proposal",
                "error",
                "a closed issue still has open proposals",
                record=record.id,
                file=file,
                fix="close issues with qingsong issue accept or close",
            )
