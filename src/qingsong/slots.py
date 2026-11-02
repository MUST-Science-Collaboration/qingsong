"""Moving numbers from a requirement's prose into value slots without changing its meaning
(docs/SPEC.md §5.2, "Converting between the forms").

A move is accepted only when the slot renders the replaced literal the same way, up to a short,
named list of formatting differences, and when no relation word sits just outside the literal.
The rest of the statement is untouched by construction. The approval is re-bound only if it was
current before, and the history event records the normative hash before and after, which is
what `integrity.against` accepts."""

import datetime
import json
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from ruamel.yaml.comments import CommentedMap

from qingsong.hashing import approved_text_hash, field_value, normative_hash_of, text_hash
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

# Formatting differences a move may make. Each is named, so the list stays reviewable. Letter case
# is kept everywhere except in relation words and TBC/TBD: units differ by case (mm, Mm).
relation_phrases = [
    (r"no less than|not less than|no fewer than|at least|不小于|不少于|不低于|至少", "≥"),
    (r"no more than|not more than|no greater than|at most|up to|不大于|不多于|不超过|至多", "≤"),
    (r"more than|greater than|超过|大于|多于", ">"),
    (r"less than|fewer than|小于|少于|低于", "<"),
]
unit_aliases = [
    (r"µ", "μ"),
    (r"(?<![A-Za-z])degC(?![A-Za-z])", "°C"),
    (r"(?<![A-Za-z])um(?![A-Za-z])", "μm"),
    (r"(?<![A-Za-z])percent(?![A-Za-z])", "%"),
    (r"(?<![A-Za-z])deg(?![A-Za-z])", "°"),
]
# Characters that glue a literal to a larger expression: a number next to them is part of it. A
# full stop or comma glues only when a digit sits on its other side (a decimal point, a list).
glue_characters = set("−-+±×/^~_⁰¹²³⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉")


def glued(text: str, start: int, end: int) -> str | None:
    """The character that ties the span to a larger expression, if any."""

    def ties(character: str, beyond: str) -> bool:
        return (
            (character.isascii() and character.isalnum())
            or character in glue_characters
            or (character in ".," and beyond.isdigit())
        )

    if start > 0 and ties(text[start - 1], text[start - 2] if start > 1 else ""):
        return text[start - 1]
    if end < len(text) and ties(text[end], text[end + 1] if end + 1 < len(text) else ""):
        return text[end]
    return None


def display(text: str) -> str:
    """Rendered slot text as a reader sees it: Markdown escapes removed."""
    return re.sub(r"\\(.)", r"\1", text)


def normalized(text: str) -> str:
    """The comparison form of a literal or a rendered slot."""
    for pattern, sign in relation_phrases:
        text = re.sub(pattern, sign, text, flags=re.IGNORECASE)
    text = text.replace("<=", "≤").replace(">=", "≥").replace("+/-", "±").replace("~", "≈")
    text = text.replace("（", "(").replace("）", ")")
    text = re.sub(r"(?i)(?<![A-Za-z])tbc(?![A-Za-z])|待确认", "TBC", text)
    text = re.sub(r"(?i)(?<![A-Za-z])tbd(?![A-Za-z])|待定", "TBD", text)
    for pattern, canonical in unit_aliases:
        text = re.sub(pattern, canonical, text)
    # Thousands separators, read before spaces are removed: "5, 100" stays two numbers.
    text = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", text)
    # Spaces are removed except between two digits: "1 0" stays apart from "10".
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"(?<!\d) | (?!\d)", "", text)
    # A unit written after both the value and the tolerance: "140μm±2μm" reads as "140±2μm".
    text = re.sub(r"(\d)([^\d±+/()\[\]−\- ]+)±([\d.]+)\2(?![^\W\d_])", r"\1±\3\2", text)
    # A unit just after the brackets of a provisional value: "[20000]mm" reads as "[20000mm]".
    text = re.sub(r"\[([^\[\]]+)\]([^\d\s\[\]()±,.;:，。；：]+)", r"[\1\2]", text)
    # A tolerance group in parentheses before an attached unit: "(20±0.5)%" reads as "20±0.5%".
    text = re.sub(r"\(([\d.]+±[\d.]+)\)", r"\1", text)
    return text


def protected_spans(text: str) -> list[tuple[int, int]]:
    """References, links, footnotes, code and mathematics: never rewritten by a move."""
    from qingsong.checks.content import markdown_link, math_or_code

    return [
        (match.start(), match.end())
        for pattern in (reference_pattern, markdown_link, math_or_code)
        for match in pattern.finditer(text)
    ]


def overlaps(first: tuple[int, int], second: tuple[int, int]) -> bool:
    return first[0] < second[1] and second[0] < first[1]


text_fields = ("title", "statement", "rationale", "notes", "suggestions", "verification")


def slot_values(
    root: Path,
    record_id: str,
    slots: dict[str, Any],
    person: str,
    via: str | None = None,
    today: datetime.date | None = None,
    dry_run: bool = False,
) -> tuple[Requirement, list[tuple[str, str, str]], list[str]]:
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

    dumped = json.dumps(
        {name: field_value(record, name) for name in text_fields}, ensure_ascii=False
    )
    for name in parsed:
        if "{" + name + "}" in dumped:
            problems.append(f"{name}: {{{name}}} already appears in the record's text")
    new_statement = dict(record.statement)
    warnings: list[str] = []
    for language in languages:
        text = record.statement[language]
        spans: dict[str, tuple[int, int]] = {}
        for name, slot in parsed.items():
            literal = literals[name][language]
            count = text.count(literal) if literal.strip() else 0
            if count != 1:
                problems.append(
                    f"{name} ({language}): {literal!r} occurs {count} times; it must occur once"
                )
                continue
            start = text.index(literal)
            span = (start, start + len(literal))
            if any(overlaps(span, other) for other in protected_spans(text)):
                problems.append(
                    f"{name} ({language}): {literal!r} is part of a reference, link, code or "
                    "mathematics"
                )
                continue
            clash = next((other for other, taken in spans.items() if overlaps(span, taken)), None)
            if clash:
                problems.append(f"{name} ({language}): {literal!r} overlaps the text of {clash}")
                continue
            tie = glued(text, span[0], span[1])
            if tie:
                problems.append(
                    f"{name} ({language}): {literal!r} is glued to {tie!r}; it is part of a "
                    "larger expression"
                )
                continue
            word = neighbour_problem(text, span[0], span[1], language)
            if word:
                problems.append(
                    f"{name} ({language}): {word!r} sits next to {literal!r}; include it in "
                    "the replaced text so that the slot says what the sentence says"
                )
                continue
            rendered = display(format_slot(slot, language))
            if normalized(literal) != normalized(rendered):
                problems.append(
                    f"{name} ({language}): {literal!r} would read {rendered!r}; a move must "
                    "keep the meaning, so correct the slot, or change the wording by a proposal"
                )
                continue
            spans[name] = span
            for field in ("rationale", "notes", "suggestions"):
                other = getattr(record, field) or {}
                if literal in other.get(language, ""):
                    warnings.append(f"{literal!r} also appears in the {field}; it stays in prose")
            criteria = record.verification.criteria if record.verification else {}
            if literal in criteria.get(language, ""):
                warnings.append(f"{literal!r} also appears in the verification criteria")
        if problems:
            continue
        rewritten = text
        for name, (start, end) in sorted(spans.items(), key=lambda item: -item[1][0]):
            rewritten = rewritten[:start] + "{" + name + "}" + rewritten[end:]
        if any(rewritten.count("{" + name + "}") != 1 for name in parsed):
            problems.append(f"({language}): a slot would not appear exactly once after the move")
        new_statement[language] = rewritten
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
        state = translation.get("statement")
        if (
            state is not None
            and origin in new_statement
            and state.get("source_hash") == text_hash(old.statement.get(origin, ""))
        ):
            # Only a translation that was current follows the new text; a stale one stays stale.
            state["source_hash"] = text_hash(new_statement[origin])
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
        return record, comparisons, warnings
    written = edit(vault, record_id, change)
    assert isinstance(written, Requirement)
    return written, comparisons, warnings
