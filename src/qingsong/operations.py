"""Recorded changes: adopt, new, revise, supersede, withdraw, approve, confirm, renumber, init
(docs/SPEC.md §8, §9, §11). Every operation validates the result, rewrites the stamp, writes the
file atomically and reads it back to verify the stamp."""

import datetime
import io
import os
import re
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.error import YAMLError
from ruamel.yaml.scalarstring import LiteralScalarString

from qingsong import gitutil, ids
from qingsong.hashing import (
    approved_text_hash,
    field_value,
    normative_hash_of,
    stamp_of,
    text_hash,
)
from qingsong.schema import RecordBase, maturity_order, plain, record_folders
from qingsong.vault import (
    Vault,
    describe_validation_error,
    load,
    record_adapter,
    round_trip_yaml,
)

bookkeeping_fields = ("revision", "normative_revision", "normative_hash", "history", "stamp")
translated_types = ("requirement", "figure")
minimum_reason_length = 10


class OperationError(Exception):
    pass


def today_date(today: datetime.date | None) -> datetime.date:
    return today or datetime.date.today()


def require_person(vault: Vault, person: str) -> None:
    if not vault.people or person not in vault.people.people:
        raise OperationError(f"{person!r} is not listed in people.yaml")


def require_record(vault: Vault, record_id: str) -> RecordBase:
    if record_id not in vault.records:
        raise OperationError(f"no record {record_id} (or it does not load; run qingsong check)")
    return vault.records[record_id]


def require_current(record: RecordBase) -> None:
    if record.lifecycle != "current":
        raise OperationError(f"{record.id} is {record.lifecycle}; it can no longer be changed")


def require_recorded(record: RecordBase) -> None:
    if stamp_of(record) != record.stamp:
        raise OperationError(
            f"{record.id} has unrecorded changes; record them first with qingsong revise"
        )


def validate(data: dict[str, Any]) -> RecordBase:
    try:
        return record_adapter.validate_python(plain(data))
    except ValidationError as error:
        raise OperationError(describe_validation_error(error)) from error


def languages_of(vault: Vault) -> tuple[str, str]:
    assert vault.config is not None
    return vault.config.languages.reference, vault.config.languages.second


def translation_fields(vault: Vault, record_type: str) -> list[str]:
    if record_type not in translated_types or vault.config is None:
        return []
    if record_type == "figure":
        return ["title", "caption"]
    return list(vault.config.languages.bilingual_fields)


def translation_entries(
    vault: Vault,
    record: RecordBase,
    status: str,
    person: str | None,
    today: datetime.date,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Translation state for bilingual fields present in both languages.

    With `existing`, entries whose source hash is still current are kept as they are; only stale
    or missing entries are (re)written. A review (`status` reviewed) also marks current machine
    entries as reviewed by the person; current reviews by others are kept."""
    languages = set(languages_of(vault))
    origin = getattr(record, "text_origin", None)
    entries: dict[str, Any] = dict(existing or {})
    if origin not in languages:
        return entries
    for name in translation_fields(vault, record.type):
        value = field_value(record, name)
        if not isinstance(value, dict) or not languages <= set(value):
            continue
        current_hash = text_hash(value[origin])
        old = entries.get(name)
        current = old is not None and old.get("source_hash") == current_hash
        if (
            existing is not None
            and current
            and (status != "reviewed" or old.get("status") == "reviewed")
        ):
            continue
        entry: dict[str, Any] = {"source_hash": current_hash, "status": status}
        if status == "reviewed":
            entry["by"] = person
            entry["date"] = today
        entries[name] = entry
    return entries


def history_event(
    revision: int,
    today: datetime.date,
    person: str,
    event: str,
    summary: str,
    change_class: str | None = None,
    decision: str | None = None,
    via: str | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {"revision": revision, "date": today, "by": person, "event": event}
    if change_class:
        entry["change_class"] = change_class
    entry["summary"] = summary
    if decision:
        entry["decision"] = decision
    if via:
        entry["via"] = via
    return entry


def load_round_trip(path: Path) -> CommentedMap:
    try:
        with path.open(encoding="utf-8") as handle:
            data = round_trip_yaml().load(handle)
    except (YAMLError, UnicodeDecodeError) as error:
        first = str(error).strip().splitlines()
        raise OperationError(
            f"{path.name} is not valid YAML ({' '.join(first[:2])}); "
            "quote texts that start with [ or {"
        ) from error
    if not isinstance(data, CommentedMap):
        raise OperationError(f"{path.name} must hold a mapping")
    return data


def literal_blocks(value: Any) -> Any:
    """Write new multi-line texts as literal blocks (|-) instead of quoted strings with escapes.
    Texts that a literal block cannot hold exactly (control or separator characters such as tab,
    vertical tab, carriage return, U+0085 and U+2028, trailing spaces, leading indentation or a
    final newline) are left as they are."""
    if isinstance(value, dict):
        for key in list(value):
            value[key] = literal_blocks(value[key])
    elif isinstance(value, list):
        for index, item in enumerate(value):
            value[index] = literal_blocks(item)
    elif (
        type(value) is str
        and "\n" in value
        and all(character == "\n" or character.isprintable() for character in value)
        and not value.endswith("\n")
        and not value.startswith((" ", "\n"))
        and not any(line != line.rstrip() for line in value.split("\n"))
    ):
        return LiteralScalarString(value)
    return value


def serialize(data: CommentedMap) -> str:
    buffer = io.StringIO()
    round_trip_yaml().dump(literal_blocks(data), buffer)
    return buffer.getvalue()


def write_atomically(path: Path, text: str, exclusive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive and path.exists():
        raise OperationError(f"{path.name} already exists; it will not be overwritten")
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def stamped(data: CommentedMap) -> tuple[RecordBase, str]:
    """Write normative hash and stamp into the data; return the record and its serialized text.

    The text is parsed again and must give the same stamp, so that nothing is lost in writing."""
    data["stamp"] = "0" * 16
    record = validate(data)
    data["normative_hash"] = normative_hash_of(record)
    data["stamp"] = stamp_of(validate(data))
    text = serialize(data)
    reread = validate(round_trip_yaml().load(text))
    if stamp_of(reread) != data["stamp"]:
        raise OperationError(
            f"{data.get('id')}: the record does not survive writing as YAML unchanged "
            "(please report this as a qingsong bug)"
        )
    return reread, text


def finish(path: Path, data: CommentedMap, exclusive: bool = False) -> RecordBase:
    record, text = stamped(data)
    write_atomically(path, text, exclusive=exclusive)
    return record


def edit(
    vault: Vault,
    record_id: str,
    change: Callable[[CommentedMap, RecordBase], None],
    allow_unrecorded: bool = False,
) -> RecordBase:
    record = require_record(vault, record_id)
    if not allow_unrecorded:
        require_recorded(record)
    path = vault.files[record_id]
    data = load_round_trip(path)
    change(data, record)
    return finish(path, data)


def adopt(
    root: Path,
    file: Path,
    person: str,
    summary: str,
    event: str = "imported",
    translation: str = "machine",
    via: str | None = None,
    today: datetime.date | None = None,
) -> RecordBase:
    """Take a hand-written record file (without bookkeeping fields) into the record."""
    today = today_date(today)
    vault = load(root)
    require_person(vault, person)
    path = file if file.is_absolute() else (root / file)
    data = load_round_trip(path)
    present = [name for name in bookkeeping_fields if name in data]
    if present:
        raise OperationError(
            f"{path.name} already has {', '.join(present)}; use qingsong revise instead"
        )
    record_id, record_type = data.get("id"), data.get("type")
    if record_type not in record_folders or not isinstance(record_id, str):
        raise OperationError("the file needs an id and a known type")
    if not ids.id_matches(record_type, record_id):
        raise OperationError(f"{record_id} is not a valid {record_type} ID")
    expected = (root / ids.relative_path(record_type, record_id)).resolve()
    if path.resolve() != expected:
        raise OperationError(
            f"{record_id} must be stored at {expected.relative_to(root.resolve())}"
        )
    if record_id in vault.records and vault.files[record_id].resolve() != expected:
        raise OperationError(f"{record_id} already exists")
    if translation not in ("machine", "reviewed"):
        raise OperationError("translation must be machine or reviewed")
    data.setdefault("lifecycle", "current")
    data["revision"] = 1
    data["normative_revision"] = 1
    data["normative_hash"] = "0" * 16
    data["history"] = [history_event(1, today, person, event, summary, via=via)]
    data["stamp"] = "0" * 16
    draft = validate(data)
    if record_type in translated_types and not data.get("translation"):
        reviewer = person if translation == "reviewed" else None
        entries = translation_entries(vault, draft, translation, reviewer, today)
        if entries:
            data["translation"] = entries
    return finish(path, data)


def numbers_in_use(vault: Vault, record_type: str, namespace: str | None) -> set[int]:
    """Numbers used in the working tree (loaded or not) and on every main reference."""
    used: set[int] = set()

    def note(stem: str) -> None:
        if ids.id_matches(record_type, stem) and ids.namespace_of(record_type, stem) == namespace:
            used.add(ids.number_of(record_type, stem) or 0)

    folder = vault.root / record_folders[record_type]
    if folder.exists():
        for path in folder.rglob("*.y*ml"):
            note(path.stem)
    for record in vault.records.values():
        if record.type == record_type:
            note(record.id)
    for record_id, _path in vault.duplicates:
        note(record_id)
    for ref in gitutil.main_refs(vault.root):
        for name in gitutil.files_at(vault.root, ref, record_folders[record_type]):
            note(Path(name).stem)
    return used


def allocate_number(vault: Vault, record_type: str, namespace: str | None) -> int:
    return max(numbers_in_use(vault, record_type, namespace), default=0) + 1


def expected_level(vault: Vault, namespace: str) -> str:
    assert vault.config is not None
    if namespace in vault.config.top_namespaces:
        return vault.config.top_namespaces[namespace]
    if namespace.endswith("-SYS"):
        return "element"
    return "subsystem"


def text_origin_for(vault: Vault, node_reference: str) -> str:
    assert vault.config is not None
    reference: str | None = node_reference
    while reference:
        info = vault.nodes.get(reference)
        if info is None:
            break
        if info.node.text_origin:
            return info.node.text_origin
        reference = info.parent
    return vault.config.languages.default_text_origin


def new_requirement(
    root: Path,
    namespace: str,
    title: str,
    statement: str,
    person: str,
    level: str | None = None,
    via: str | None = None,
    today: datetime.date | None = None,
) -> RecordBase:
    """Allocate the next ID; title and statement are given in the node's origin language."""
    today = today_date(today)
    vault = load(root)
    require_person(vault, person)
    namespaces = vault.namespaces()
    if namespace not in namespaces:
        raise OperationError(
            f"unknown namespace {namespace}; known: {', '.join(sorted(namespaces))}"
        )
    allocated = namespaces[namespace]
    number = allocate_number(vault, "requirement", namespace)
    record_id = ids.format_id("requirement", namespace, number)
    origin = text_origin_for(vault, allocated)
    data = CommentedMap()
    data["id"] = record_id
    data["type"] = "requirement"
    data["title"] = {origin: title}
    data["lifecycle"] = "current"
    data["statement"] = {origin: statement}
    data["level"] = level or expected_level(vault, namespace)
    data["allocated_to"] = allocated
    data["maturity"] = "concept"
    data["text_origin"] = origin
    data["revision"] = 1
    data["normative_revision"] = 1
    data["normative_hash"] = "0" * 16
    data["history"] = [history_event(1, today, person, "created", "created", via=via)]
    path = root / ids.relative_path("requirement", record_id)
    return finish(path, data, exclusive=True)


drafted_types = ("issue", "decision", "waiver", "interface", "condition", "source", "verification")


def draft_identity(vault: Vault, record_type: str, data: CommentedMap, slug: str | None) -> str:
    """The ID a new record of this type receives (docs/SPEC.md §5.3, §6.1)."""
    if record_type == "source":
        if not slug:
            raise OperationError("a source needs --slug, e.g. DEMO-INS-DET-RD-v1.0")
        record_id = f"SRC-{slug}"
        if not ids.id_matches("source", record_id):
            raise OperationError(f"{record_id} is not a valid source ID")
        if (
            record_id in vault.records
            or (vault.root / ids.relative_path("source", record_id)).exists()
        ):
            raise OperationError(f"{record_id} already exists")
        return record_id
    if slug:
        raise OperationError("--slug applies to sources only")
    if record_type == "interface":
        owner = vault.nodes.get(str(data.get("owner_end") or ""))
        if owner is None:
            raise OperationError("an interface draft needs owner_end, a node reference")
        system = owner.system or owner.node.node
        return ids.format_id("interface", system, allocate_number(vault, "interface", system))
    if record_type == "condition":
        node = str(data.get("node") or "")
        if node not in vault.nodes:
            raise OperationError("a condition draft needs node, a node reference")
        return ids.format_id("condition", node, allocate_number(vault, "condition", node))
    if record_type == "verification":
        requirement = str(data.get("requirement") or "")
        if not ids.id_matches("requirement", requirement) or requirement not in vault.records:
            raise OperationError("a verification draft needs requirement, an existing ID")
        prefix = f"VER-{requirement}-"
        used = {
            int(stem[len(prefix) :])
            for stem in (path.stem for path in (vault.root / "verifications").glob("*.yaml"))
            if stem.startswith(prefix) and stem[len(prefix) :].isdigit()
        }
        for ref in gitutil.main_refs(vault.root):
            for name in gitutil.files_at(vault.root, ref, "verifications"):
                stem = Path(name).stem
                if stem.startswith(prefix) and stem[len(prefix) :].isdigit():
                    used.add(int(stem[len(prefix) :]))
        return ids.format_id("verification", requirement, max(used, default=0) + 1)
    return ids.format_id(record_type, None, allocate_number(vault, record_type, None))


def new_from_draft(
    root: Path,
    record_type: str,
    draft: Path,
    person: str,
    slug: str | None = None,
    via: str | None = None,
    today: datetime.date | None = None,
) -> RecordBase:
    """Allocate an ID for a draft file (all fields but the ID and bookkeeping), write the record
    where its ID says, and record its creation. The draft file itself is left untouched."""
    if record_type not in drafted_types:
        raise OperationError(
            f"new --file takes {', '.join(drafted_types)}; requirements use new requirement"
        )
    vault = load(root)
    require_person(vault, person)
    data = load_round_trip(draft)
    present = [name for name in ("id", *bookkeeping_fields) if name in data]
    if present:
        raise OperationError(f"the draft must not contain {', '.join(present)}")
    if data.get("type", record_type) != record_type:
        raise OperationError(f"the draft is a {data.get('type')}, not a {record_type}")
    record_id = draft_identity(vault, record_type, data, slug)
    record = CommentedMap()
    record["id"] = record_id
    record["type"] = record_type
    for key, value in data.items():
        if key != "type":
            record[key] = value
    record.setdefault("lifecycle", "current")
    target = root / ids.relative_path(record_type, record_id)
    write_atomically(target, serialize(record), exclusive=True)
    try:
        return adopt(root, target, person, "created", event="created", via=via, today=today)
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def revise(
    root: Path,
    record_id: str,
    change_class: str,
    summary: str,
    person: str,
    decision: str | None = None,
    translation: str = "unchanged",
    to_draft: bool = False,
    via: str | None = None,
    today: datetime.date | None = None,
) -> RecordBase:
    """Record a change already made to a record's file: bump the revision (and the normative
    revision for a 'value' change), rewrite the stamp, and append a history event. Refuses
    'editorial' when values, the level or the verification methods changed (`normative_hash`), a
    baselined requirement without a decision record, and an agreed one without a reason."""
    today = today_date(today)
    vault = load(root)
    require_person(vault, person)
    record = require_record(vault, record_id)
    require_current(record)
    normative_changed = normative_hash_of(record) != record.normative_hash
    unchanged = stamp_of(record) == record.stamp
    if change_class not in ("editorial", "value", "reallocate"):
        raise OperationError("the class must be editorial, value or reallocate")
    if change_class == "editorial" and normative_changed:
        raise OperationError(
            "values, level or verification methods changed: this is a 'value' change, not editorial"
        )
    if change_class == "reallocate" and normative_changed:
        raise OperationError("a reallocation may not change values, level or verification methods")
    if unchanged and translation == "unchanged" and not to_draft:
        raise OperationError("nothing changed since the last recorded state")
    maturity = getattr(record, "maturity", None)
    if maturity == "baselined" and not decision:
        raise OperationError("a change to a baselined requirement needs --decision")
    if maturity in ("agreed", "baselined") and len(summary.strip()) < minimum_reason_length:
        raise OperationError("give a summary that states the reason for the change")
    if to_draft and maturity != "concept":
        raise OperationError("--to-draft applies only to concept requirements")

    def change(data: CommentedMap, old: RecordBase) -> None:
        data["revision"] = old.revision + 1
        if change_class == "value":
            data["normative_revision"] = old.normative_revision + 1
        if to_draft:
            data["maturity"] = "draft"
        if translation != "unchanged":
            status = "reviewed" if translation == "reviewed" else "machine"
            existing = {
                name: state.model_dump(mode="json", exclude_none=True)
                for name, state in getattr(old, "translation", {}).items()
            }
            refreshed = translation_entries(vault, old, status, person, today, existing=existing)
            if refreshed:
                data["translation"] = refreshed
        data["history"].append(
            history_event(
                old.revision + 1,
                today,
                person,
                "revised",
                summary,
                change_class=change_class,
                decision=decision,
                via=via,
            )
        )

    return edit(vault, record_id, change, allow_unrecorded=True)


def supersede(
    root: Path,
    old_id: str,
    successors: list[str],
    summary: str,
    person: str,
    decision: str | None = None,
    via: str | None = None,
    today: datetime.date | None = None,
) -> RecordBase:
    """Mark a record as superseded by one or more current successors of the same type (several for a
    split). An agreed or baselined requirement needs a decision record."""
    today = today_date(today)
    vault = load(root)
    require_person(vault, person)
    record = require_record(vault, old_id)
    require_current(record)
    if not successors:
        raise OperationError("name at least one successor")
    for successor in successors:
        if successor == old_id:
            raise OperationError("a record cannot supersede itself")
        other = require_record(vault, successor)
        if other.type != record.type:
            raise OperationError(f"{successor} is a {other.type}, not a {record.type}")
        if other.lifecycle != "current":
            raise OperationError(f"{successor} is {other.lifecycle}")
    if maturity_order.get(getattr(record, "maturity", "concept"), 0) >= 2 and not decision:
        raise OperationError("superseding an agreed or baselined requirement needs --decision")

    def change(data: CommentedMap, old: RecordBase) -> None:
        data["lifecycle"] = "superseded"
        data["superseded_by"] = list(successors)
        data["revision"] = old.revision + 1
        data["history"].append(
            history_event(
                old.revision + 1, today, person, "superseded", summary, decision=decision, via=via
            )
        )

    return edit(vault, old_id, change)


def withdraw(
    root: Path,
    record_id: str,
    reason: str,
    person: str,
    decision: str | None = None,
    via: str | None = None,
    today: datetime.date | None = None,
) -> RecordBase:
    """Withdraw a record: it stays in the vault with lifecycle 'withdrawn' and its ID is retired. An
    agreed or baselined requirement needs a decision record."""
    today = today_date(today)
    vault = load(root)
    require_person(vault, person)
    record = require_record(vault, record_id)
    require_current(record)
    if maturity_order.get(getattr(record, "maturity", "concept"), 0) >= 2 and not decision:
        raise OperationError("withdrawing an agreed or baselined requirement needs --decision")

    def change(data: CommentedMap, old: RecordBase) -> None:
        data["lifecycle"] = "withdrawn"
        data["revision"] = old.revision + 1
        data["history"].append(
            history_event(
                old.revision + 1, today, person, "withdrawn", reason, decision=decision, via=via
            )
        )

    return edit(vault, record_id, change)


def approve(
    root: Path,
    record_id: str,
    to: str,
    person: str,
    ref: str,
    via: str | None = None,
    today: datetime.date | None = None,
) -> RecordBase:
    """Record an approver's maturity decision on a requirement: 'agreed' records what was approved
    (normative revision and text hash); 'draft' reopens an agreed or baselined requirement.
    Agents call it only on an approver's instruction."""
    today = today_date(today)
    vault = load(root)
    require_person(vault, person)
    if not vault.is_approver(person):
        raise OperationError(f"{person} is not an approver (people.yaml)")
    record = require_record(vault, record_id)
    require_current(record)
    if record.type != "requirement":
        raise OperationError("only requirements carry maturity")
    current = record.maturity
    if to not in ("agreed", "draft"):
        raise OperationError("approve --to takes agreed or draft (baselines come with Phase 6)")
    if to == "agreed" and current not in ("draft", "agreed"):
        raise OperationError(
            f"{record_id} is {current}; only draft or agreed requirements can be approved"
        )
    if to == "draft" and current not in ("agreed", "baselined"):
        raise OperationError(
            f"{record_id} is {current}; only agreed or baselined requirements can be reopened"
        )
    reference_language = languages_of(vault)[0]

    def change(data: CommentedMap, old: RecordBase) -> None:
        data["maturity"] = to
        if to == "agreed":
            data["approval"] = {
                "by": person,
                "date": today,
                "ref": ref,
                "normative_revision": old.normative_revision,
                "text_hash": approved_text_hash(old, reference_language),
            }
        data["revision"] = old.revision + 1
        summary = f"approved as {to} ({ref})" if to == "agreed" else f"reopened as draft ({ref})"
        data["history"].append(
            history_event(old.revision + 1, today, person, "approved", summary, via=via)
        )

    return edit(vault, record_id, change)


def confirm(
    root: Path,
    child_id: str,
    parent_id: str,
    person: str,
    via: str | None = None,
    today: datetime.date | None = None,
) -> RecordBase:
    """Clear a suspect link: record that the child was reviewed against its parent's current
    normative revision."""
    today = today_date(today)
    vault = load(root)
    require_person(vault, person)
    child = require_record(vault, child_id)
    require_current(child)
    parent = require_record(vault, parent_id)
    links = [
        name
        for name in ("derives_from", "constrained_by")
        if any(link.id == parent_id for link in getattr(child, name, []))
    ]
    if not links:
        raise OperationError(f"{child_id} has no link to {parent_id}")

    def change(data: CommentedMap, old: RecordBase) -> None:
        for name in links:
            for link in data[name]:
                if link["id"] == parent_id:
                    link["normative_revision"] = parent.normative_revision
        data["revision"] = old.revision + 1
        data["history"].append(
            history_event(
                old.revision + 1,
                today,
                person,
                "confirmed",
                f"link to {parent_id} reviewed at its normative revision {parent.normative_revision}",
                via=via,
            )
        )

    return edit(vault, child_id, change)


def renumber(
    root: Path,
    old_id: str,
    new_id: str,
    person: str,
    via: str | None = None,
    today: datetime.date | None = None,
) -> RecordBase:
    """Move a record that has not reached main to a free ID, rewriting every reference.

    All changes are prepared and verified in memory before any file is written."""
    today = today_date(today)
    vault = load(root)
    require_person(vault, person)
    record = require_record(vault, old_id)
    require_recorded(record)
    if not ids.id_matches(record.type, new_id):
        raise OperationError(f"{new_id} is not a valid {record.type} ID")
    if new_id in vault.records:
        raise OperationError(f"{new_id} already exists")
    refs = gitutil.main_refs(root)
    if not refs:
        raise OperationError("no main branch found; cannot verify that the record is unmerged")
    for ref in refs:
        on_main = {
            Path(name).stem for name in gitutil.files_at(root, ref, record_folders[record.type])
        }
        if old_id in on_main:
            raise OperationError(f"{old_id} is on {ref}; it is permanent and cannot be renumbered")
        if new_id in on_main:
            raise OperationError(f"{new_id} is already used on {ref}")
    if vault.load_findings or vault.duplicates:
        raise OperationError("some files do not load; fix them (qingsong check) before renumbering")
    pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(old_id)}(?![0-9])")
    plans: list[tuple[Path, Path, CommentedMap]] = []
    for other_id, path in vault.files.items():
        text = path.read_text(encoding="utf-8")
        if not pattern.search(text):
            continue
        other = vault.records[other_id]
        require_recorded(other)
        data = round_trip_yaml().load(pattern.sub(new_id, text))
        target = root / ids.relative_path(other.type, data["id"])
        rewritten = validate(data)
        origin = getattr(rewritten, "text_origin", None)
        for name, entry in (data.get("translation") or {}).items():
            old_value, new_value = field_value(other, name), field_value(rewritten, name)
            if not (isinstance(old_value, dict) and isinstance(new_value, dict) and origin):
                continue
            if entry.get("source_hash") == text_hash(old_value.get(origin, "")):
                entry["source_hash"] = text_hash(new_value.get(origin, ""))
        summary = (
            f"renumbered from {old_id} before reaching main"
            if other_id == old_id
            else f"reference {old_id} renumbered to {new_id}"
        )
        data["revision"] = other.revision + 1
        data["history"].append(
            history_event(other.revision + 1, today, person, "renumbered", summary, via=via)
        )
        plans.append((path, target, data))
    prepared = [(path, target, stamped(data)[1]) for path, target, data in plans]
    for path, target, _text in prepared:
        if target != path and target.exists():
            raise OperationError(f"{target.name} already exists")
    for path, target, text in prepared:
        write_atomically(target, text)
        if target != path:
            path.unlink()
    return load(root).records[new_id]


default_levels = [
    ("science", "Science requirements", "科学需求"),
    ("survey", "Survey requirements", "巡天需求"),
    ("system", "System requirements", "系统需求"),
    ("element", "System-level requirements of each major system", "各分系统顶层需求"),
    ("subsystem", "Subsystem requirements", "子系统需求"),
    ("component", "Component requirements", "部件需求"),
]


def init_vault(path: Path, code: str, name: str) -> Path:
    """Create an empty vault at PATH: configuration, people, glossary, root tree file and the record
    folders."""
    path = path.resolve()
    if (path / "qingsong.toml").exists():
        raise OperationError(f"{path} is already a vault")
    if not ids.node_code_pattern.match(code) or code in ids.reserved_codes:
        raise OperationError(
            f"project code {code!r} must match [A-Z][A-Z0-9]{{1,5}} and not be reserved"
        )
    path.mkdir(parents=True, exist_ok=True)
    levels = "\n".join(
        f'[[levels]]\nname = "{level}"\nnames = {{ en = "{english}", zh = "{chinese}" }}\n'
        for level, english, chinese in default_levels
    )
    (path / "qingsong.toml").write_text(
        f'[project]\ncode = "{code}"\nnames = {{ en = "{name}" }}\n\n'
        '[languages]\nreference = "en"\nsecond = "zh"\ndefault_text_origin = "en"\n'
        'bilingual_fields = ["title", "statement", "rationale", "verification.criteria"]\n\n'
        f'{levels}\n[top_namespaces]\n{code}-SCI = "science"\n{code}-SRV = "survey"\n'
        f'{code}-SYS = "system"\n',
        encoding="utf-8",
    )
    (path / "people.yaml").write_text("people: {}\n", encoding="utf-8")
    (path / "glossary.yaml").write_text("terms: {}\n", encoding="utf-8")
    (path / "tree").mkdir(exist_ok=True)
    (path / "tree" / f"{code}.yaml").write_text(
        f'node: {code}\nnames: {{en: "{name}"}}\nkind: product\nstatus: active\n',
        encoding="utf-8",
    )
    return path
