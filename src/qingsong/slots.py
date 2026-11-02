"""Moving numbers from a requirement's prose into value slots without changing its meaning
(docs/SPEC.md §5.2, "Converting between the forms").

A move is accepted only when the slot renders the replaced literal the same way, up to a short,
named list of formatting differences, and when no relation word sits just outside the literal.
The rest of the statement is untouched by construction. The approval is re-bound only if it was
current before, and the history event records the normative hash before and after, which is
what `integrity.against` accepts."""

import datetime
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from ruamel.yaml.comments import CommentedMap

from qingsong.hashing import approved_text_hash, normative_hash_of, text_hash
from qingsong.ids import reference_pattern
from qingsong.operations import (
    OperationError,
    edit,
    history_event,
    languages_of,
    require_current,
    require_person,
    require_record,
    require_recorded,
    today_date,
    validate,
)
from qingsong.render.text import format_slot
from qingsong.schema import Requirement, ValueSlot
from qingsong.vault import load
from qingsong.wording import neighbour_problem

slot_name = re.compile(r"^[a-z][a-z0-9_]*$")

# Formatting differences a move may make. Each is named, so the list stays reviewable.
relation_phrases = [
    (r"no less than|not less than|at least|不小于|不少于|不低于|至少", "≥"),
    (r"no more than|not more than|at most|up to|不大于|不多于|不超过|至多", "≤"),
    (r"more than|greater than|超过|大于|多于", ">"),
    (r"less than|fewer than|小于|少于|低于", "<"),
]
unit_aliases = [("µ", "μ"), ("um", "μm"), ("percent", "%"), ("deg", "°")]


def display(text: str) -> str:
    """Rendered slot text as a reader sees it: Markdown escapes removed."""
    return re.sub(r"\\(.)", r"\1", text)


def normalized(text: str) -> str:
    """The comparison form of a literal or a rendered slot."""
    text = text.casefold()
    for pattern, sign in relation_phrases:
        text = re.sub(pattern, sign, text)
    text = text.replace("<=", "≤").replace(">=", "≥").replace("+/-", "±").replace("~", "≈")
    text = (
        text.replace("（", "(").replace("）", ")").replace("待确认", "tbc").replace("待定", "tbd")
    )
    for alias, canonical in unit_aliases:
        text = text.replace(alias, canonical)
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", text)
    # A unit written after both the value and the tolerance: "140μm±2μm" reads as "140±2μm".
    text = re.sub(r"(\d)([^\d±+/()\[\]−-]+)±([\d.]+)\2", r"\1±\3\2", text)
    # A unit just after the brackets of a provisional value: "[20000]mm" reads as "[20000mm]".
    text = re.sub(r"\[([^\[\]]+)\]([^\d\s\[\]()±,.;:，。；：]+)", r"[\1\2]", text)
    # A tolerance group in parentheses before an attached unit: "(20±0.5)%" reads as "20±0.5%".
    text = re.sub(r"\(([\d.]+±[\d.]+)\)", r"\1", text)
    return text


def inside_reference(text: str, start: int, end: int) -> bool:
    return any(
        match.start() < end and start < match.end() for match in reference_pattern.finditer(text)
    )


def slot_values(
    root: Path,
    record_id: str,
    slots: dict[str, Any],
    person: str,
    via: str | None = None,
    today: datetime.date | None = None,
    dry_run: bool = False,
) -> tuple[Requirement, list[tuple[str, str, str]]]:
    """Move numbers into slots. Returns the record and, per language, the statement before and
    after. Refuses, with every reason, unless each move provably keeps the meaning."""
    today = today_date(today)
    vault = load(root)
    require_person(vault, person)
    record = require_record(vault, record_id)
    if not isinstance(record, Requirement):
        raise OperationError(f"{record_id} is not a requirement")
    require_current(record)
    require_recorded(record)
    if not isinstance(slots, dict) or not slots:
        raise OperationError("give at least one slot, as a mapping from slot name to its fields")
    reference, second = languages_of(vault)
    languages = [language for language in (reference, second) if language in record.statement]
    problems: list[str] = []
    parsed: dict[str, ValueSlot] = {}
    literals: dict[str, dict[str, str]] = {}
    for name, fields in slots.items():
        if not slot_name.match(str(name)):
            problems.append(f"{name}: a slot name is lower case, e.g. core_diameter")
            continue
        if name in record.values:
            problems.append(f"{name}: the requirement already has this slot")
            continue
        if not isinstance(fields, dict) or not isinstance(fields.get("replaces"), dict):
            problems.append(f"{name}: give replaces: {{en: …, zh: …}}, the text it replaces")
            continue
        literals[name] = {str(key): str(value) for key, value in fields["replaces"].items()}
        try:
            parsed[name] = ValueSlot.model_validate(
                {key: value for key, value in fields.items() if key != "replaces"}
            )
        except ValidationError as error:
            problems.append(f"{name}: {error.errors()[0]['msg']}")
            continue
        missing = [language for language in languages if language not in literals[name]]
        if missing:
            problems.append(f"{name}: give the replaced text in {', '.join(missing)} as well")
    if problems:
        raise OperationError("cannot move the values:\n  " + "\n  ".join(problems))

    new_statement = dict(record.statement)
    for language in languages:
        text = record.statement[language]
        for name, slot in parsed.items():
            literal = literals[name][language]
            count = text.count(literal)
            if not literal.strip() or count != 1:
                problems.append(
                    f"{name} ({language}): {literal!r} occurs {count} times; it must occur once"
                )
                continue
            start = text.index(literal)
            end = start + len(literal)
            if inside_reference(text, start, end):
                problems.append(f"{name} ({language}): {literal!r} is part of a reference")
                continue
            word = neighbour_problem(text, start, end, language)
            if word:
                problems.append(
                    f"{name} ({language}): {word!r} sits next to {literal!r}; include it in "
                    "the replaced text so that the relation is checked"
                )
                continue
            rendered = display(format_slot(slot, language))
            if normalized(literal) != normalized(rendered):
                problems.append(
                    f"{name} ({language}): {literal!r} would read {rendered!r}; a move must "
                    "keep the meaning, so correct the slot, or change the wording by a proposal"
                )
                continue
        if not problems:
            for name in parsed:
                new_statement[language] = new_statement[language].replace(
                    literals[name][language], "{" + name + "}", 1
                )
    if problems:
        raise OperationError("cannot move the values:\n  " + "\n  ".join(problems))

    approval_was_current = record.approval is not None and (
        record.approval.normative_revision == record.normative_revision
        and record.approval.text_hash == approved_text_hash(record, reference)
    )
    hash_before = record.normative_hash
    names = ", ".join(parsed)

    def change(data: CommentedMap, old: Any) -> None:
        data["statement"] = new_statement
        values = data.setdefault("values", CommentedMap())
        for name, slot in parsed.items():
            values[name] = slot.model_dump(mode="json", exclude_none=True)
        origin = old.text_origin
        translation = data.get("translation") or {}
        if "statement" in translation and origin in new_statement:
            translation["statement"]["source_hash"] = text_hash(new_statement[origin])
        draft = validate(data)
        assert isinstance(draft, Requirement)
        hash_after = normative_hash_of(draft)
        if approval_was_current:
            data["approval"]["text_hash"] = approved_text_hash(draft, reference)
        data["revision"] = old.revision + 1
        event = history_event(
            old.revision + 1,
            today,
            person,
            "slotted",
            f"values moved into slots ({names}); the meaning is unchanged"
            + ("; approval re-bound to the new text" if approval_was_current else ""),
            change_class="editorial",
            via=via,
        )
        event["normative_hash_before"] = hash_before
        event["normative_hash_after"] = hash_after
        data["history"].append(event)

    comparisons = [
        (language, record.statement[language], new_statement[language]) for language in languages
    ]
    if dry_run:
        return record, comparisons
    written = edit(vault, record_id, change)
    assert isinstance(written, Requirement)
    return written, comparisons
