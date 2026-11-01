"""Recorded changes: adopt, new, revise, supersede, withdraw, approve, confirm, renumber
(docs/SPEC.md §8, §9, §11). Every operation validates the result and rewrites the stamp."""

import datetime
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.error import YAMLError

from qingsong import gitutil, ids
from qingsong.hashing import field_value, normative_hash_of, stamp_of, text_hash
from qingsong.schema import RecordBase, maturity_order, plain, record_folders
from qingsong.vault import (
    Vault,
    describe_validation_error,
    load,
    record_adapter,
    round_trip_yaml,
    write_new_record,
)

bookkeeping_fields = ("revision", "normative_revision", "normative_hash", "history", "stamp")
translated_types = {"requirement": "statement", "figure": "caption"}


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


def validate(data: dict[str, Any]) -> RecordBase:
    try:
        return record_adapter.validate_python(plain(data))
    except ValidationError as error:
        raise OperationError(describe_validation_error(error)) from error


def translation_fields(vault: Vault, record_type: str) -> list[str]:
    if record_type not in translated_types or vault.config is None:
        return []
    fields = list(vault.config.languages.bilingual_fields)
    if record_type == "figure":
        fields = ["title", "caption"]
    return fields


def translation_entries(
    vault: Vault,
    record: RecordBase,
    status: str,
    person: str | None,
    today: datetime.date,
    only_missing: dict[str, Any] | None = None,
) -> dict:
    """Translation state for every bilingual field that exists in both languages."""
    assert vault.config is not None
    languages = {vault.config.languages.reference, vault.config.languages.second}
    origin = getattr(record, "text_origin", vault.config.languages.reference)
    entries: dict[str, Any] = dict(only_missing or {})
    for name in translation_fields(vault, record.type):
        value = field_value(record, name)
        if not isinstance(value, dict) or not languages <= set(value):
            continue
        if only_missing is not None and name in only_missing:
            continue
        entry: dict[str, Any] = {"source_hash": text_hash(value[origin]), "status": status}
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
    except YAMLError as error:
        first = str(error).strip().splitlines()
        raise OperationError(
            f"{path.name} is not valid YAML ({' '.join(first[:2])}); "
            "quote texts that start with [ or {"
        ) from error
    if not isinstance(data, CommentedMap):
        raise OperationError(f"{path.name} must hold a mapping")
    return data


def finish(path: Path, data: CommentedMap) -> RecordBase:
    """Validate the edited data, write the new stamp, save."""
    data["stamp"] = "0" * 16
    record = validate(data)
    data["normative_hash"] = normative_hash_of(record)
    record = validate(data)
    data["stamp"] = stamp_of(record)
    with path.open("w", encoding="utf-8") as handle:
        round_trip_yaml().dump(data, handle)
    return validate(data)


def edit(
    vault: Vault, record_id: str, change: Callable[[CommentedMap, RecordBase], None]
) -> RecordBase:
    record = require_record(vault, record_id)
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
    data.setdefault("lifecycle", "current")
    data["revision"] = 1
    data["normative_revision"] = 1
    data["normative_hash"] = "0" * 16
    data["history"] = [history_event(1, today, person, event, summary, via=via)]
    data["stamp"] = "0" * 16
    draft = validate(data)
    if hasattr(draft, "translation") and not data.get("translation"):
        reviewer = person if translation == "reviewed" else None
        entries = translation_entries(vault, draft, translation, reviewer, today)
        if entries:
            data["translation"] = entries
    return finish(path, data)


def allocate_number(vault: Vault, record_type: str, namespace: str | None) -> int:
    used: set[int] = set()
    for record in vault.records.values():
        if record.type == record_type and ids.namespace_of(record_type, record.id) == namespace:
            number = ids.number_of(record_type, record.id)
            if number is not None:
                used.add(number)
    for record_id, _path in vault.duplicates:
        number = ids.number_of(record_type, record_id)
        if number is not None and ids.namespace_of(record_type, record_id) == namespace:
            used.add(number)
    ref = gitutil.main_ref(vault.root)
    if ref:
        for name in gitutil.files_at(vault.root, ref, record_folders[record_type]):
            stem = Path(name).stem
            if (
                ids.id_matches(record_type, stem)
                and ids.namespace_of(record_type, stem) == namespace
            ):
                used.add(ids.number_of(record_type, stem) or 0)
    return max(used, default=0) + 1


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
    today = today_date(today)
    vault = load(root)
    require_person(vault, person)
    assert vault.config is not None
    namespaces = vault.namespaces()
    if namespace not in namespaces:
        raise OperationError(
            f"unknown namespace {namespace}; known: {', '.join(sorted(namespaces))}"
        )
    allocated = namespaces[namespace]
    if level is None:
        level = expected_level(vault, namespace)
    record_id = ids.format_id(
        "requirement", namespace, allocate_number(vault, "requirement", namespace)
    )
    language = vault.config.languages.reference
    data = CommentedMap()
    data["id"] = record_id
    data["type"] = "requirement"
    data["title"] = {language: title}
    data["lifecycle"] = "current"
    data["statement"] = {language: statement}
    data["level"] = level
    data["allocated_to"] = allocated
    data["maturity"] = "concept"
    data["text_origin"] = text_origin_for(vault, allocated)
    path = root / ids.relative_path("requirement", record_id)
    write_new_record(path, data)
    return adopt(root, path, person, "created", event="created", via=via, today=today)


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
    today = today_date(today)
    vault = load(root)
    require_person(vault, person)
    record = require_record(vault, record_id)
    current_normative = normative_hash_of(record)
    normative_changed = current_normative != record.normative_hash
    unchanged = stamp_of(record) == record.stamp
    if change_class == "editorial" and normative_changed:
        raise OperationError(
            "values, level or verification method changed: this is a 'value' change, not editorial"
        )
    if change_class == "value" and not normative_changed and unchanged:
        raise OperationError("nothing changed since the last recorded state")
    if unchanged and translation == "unchanged" and not to_draft:
        raise OperationError("nothing changed since the last recorded state")
    maturity = getattr(record, "maturity", None)
    if maturity == "baselined" and not decision:
        raise OperationError("a change to a baselined requirement needs --decision")
    if (
        maturity in ("agreed", "baselined")
        and change_class != "editorial"
        and len(summary.split()) < 3
    ):
        raise OperationError("give a summary that states the reason for the change")
    if to_draft and maturity != "concept":
        raise OperationError("--to-draft applies only to concept requirements")
    if change_class == "reallocate" and normative_changed:
        raise OperationError("a reallocation may not change values, level or verification method")

    def change(data: CommentedMap, old: RecordBase) -> None:
        data["revision"] = old.revision + 1
        if change_class == "value":
            data["normative_revision"] = old.normative_revision + 1
        if to_draft:
            data["maturity"] = "draft"
        if translation != "unchanged":
            refreshed = translation_entries(
                vault, old, "reviewed" if translation == "reviewed" else "machine", person, today
            )
            if refreshed:
                existing = data.get("translation") or CommentedMap()
                for name, entry in refreshed.items():
                    existing[name] = entry
                data["translation"] = existing
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

    return edit(vault, record_id, change)


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
    today = today_date(today)
    vault = load(root)
    require_person(vault, person)
    record = require_record(vault, old_id)
    if record.lifecycle != "current":
        raise OperationError(f"{old_id} is already {record.lifecycle}")
    for successor in successors:
        require_record(vault, successor)
        if successor == old_id:
            raise OperationError("a record cannot supersede itself")
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
    today = today_date(today)
    vault = load(root)
    require_person(vault, person)
    record = require_record(vault, record_id)
    if record.lifecycle != "current":
        raise OperationError(f"{record_id} is already {record.lifecycle}")
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
    today = today_date(today)
    vault = load(root)
    require_person(vault, person)
    if not vault.is_approver(person):
        raise OperationError(f"{person} is not an approver (people.yaml)")
    record = require_record(vault, record_id)
    if record.type != "requirement":
        raise OperationError("only requirements carry maturity")
    current = record.maturity
    if to == "agreed" and current not in ("draft", "agreed"):
        raise OperationError(
            f"{record_id} is {current}; only draft or agreed requirements can be approved"
        )
    if to == "draft" and current not in ("agreed", "baselined"):
        raise OperationError(
            f"{record_id} is {current}; only agreed or baselined requirements can be reopened"
        )
    if to not in ("agreed", "draft"):
        raise OperationError("approve --to takes agreed or draft (baselines come with Phase 6)")
    if stamp_of(record) != record.stamp:
        raise OperationError(f"{record_id} has unrecorded changes; run qingsong revise first")

    def change(data: CommentedMap, old: RecordBase) -> None:
        data["maturity"] = to
        data["approval"] = {
            "by": person,
            "date": today,
            "ref": ref,
            "normative_revision": old.normative_revision,
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
    today = today_date(today)
    vault = load(root)
    require_person(vault, person)
    child = require_record(vault, child_id)
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
    today = today_date(today)
    vault = load(root)
    require_person(vault, person)
    record = require_record(vault, old_id)
    if not ids.id_matches(record.type, new_id):
        raise OperationError(f"{new_id} is not a valid {record.type} ID")
    if new_id in vault.records:
        raise OperationError(f"{new_id} already exists")
    ref = gitutil.main_ref(root)
    if ref:
        on_main = {
            Path(name).stem for name in gitutil.files_at(root, ref, record_folders[record.type])
        }
        if old_id in on_main:
            raise OperationError(f"{old_id} is on {ref}; it is permanent and cannot be renumbered")
        if new_id in on_main:
            raise OperationError(f"{new_id} is already used on {ref}")
    pattern = re.compile(rf"(?<![A-Za-z0-9-]){re.escape(old_id)}(?![A-Za-z0-9-])")
    old_path = vault.files[old_id]
    new_path = root / ids.relative_path(record.type, new_id)
    new_path.parent.mkdir(parents=True, exist_ok=True)
    new_path.write_text(pattern.sub(new_id, old_path.read_text(encoding="utf-8")), encoding="utf-8")
    old_path.unlink()
    for other_id, path in vault.files.items():
        if other_id == old_id:
            continue
        text = path.read_text(encoding="utf-8")
        if not pattern.search(text):
            continue
        path.write_text(pattern.sub(new_id, text), encoding="utf-8")
        refreshed = load(root)

        def note(data: CommentedMap, old: RecordBase) -> None:
            data["revision"] = old.revision + 1
            data["history"].append(
                history_event(
                    old.revision + 1,
                    today,
                    person,
                    "renumbered",
                    f"reference {old_id} renumbered to {new_id}",
                    via=via,
                )
            )

        edit(refreshed, other_id, note)
    refreshed = load(root)

    def own(data: CommentedMap, old: RecordBase) -> None:
        data["revision"] = old.revision + 1
        data["history"].append(
            history_event(
                old.revision + 1,
                today,
                person,
                "renumbered",
                f"renumbered from {old_id} before reaching main",
                via=via,
            )
        )

    return edit(refreshed, new_id, own)


default_levels = [
    ("science", "Science requirements", "科学需求"),
    ("survey", "Survey requirements", "巡天需求"),
    ("system", "System requirements", "系统需求"),
    ("element", "System-level requirements of each major system", "各分系统顶层需求"),
    ("subsystem", "Subsystem requirements", "子系统需求"),
    ("component", "Component requirements", "部件需求"),
]


def init_vault(path: Path, code: str, name: str) -> Path:
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
        f'node: {code}\nnames: {{en: "{name}"}}\nkind: product\nstatus: active\n', encoding="utf-8"
    )
    return path
