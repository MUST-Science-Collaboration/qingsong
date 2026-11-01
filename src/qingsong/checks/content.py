"""Content rules: languages, writing rules (INCOSE-derived), open values and value slots."""

import functools
import re
from collections.abc import Iterator

from qingsong.checks import Context, by_maturity, relative_file, rule
from qingsong.findings import Finding
from qingsong.hashing import field_value
from qingsong.ids import reference_pattern
from qingsong.schema import Quantity, Requirement
from qingsong.walk import localized_texts

vague_terms = {
    "en": [
        "adequate",
        "appropriate",
        "as appropriate",
        "etc.",
        "and/or",
        "user-friendly",
        "if possible",
        "as required",
        "as necessary",
        "sufficient",
        "minimize",
        "maximize",
        "approximately",
    ],
    "zh": ["适当", "尽量", "尽可能", "等等", "足够", "合理"],
}
open_value_pattern = re.compile(r"\[[^\[\]]*\d[^\[\]]*\]|\bTBD\b|\bTBC\b|待定|待确认")
slot_pattern = re.compile(r"\{([a-z][a-z0-9_]*)\}")
shall_pattern = re.compile(r"\bshall\b", re.IGNORECASE)
number_pattern = re.compile(r"(?<![\w.-])\d+(?:[.,]\d+)?(?![\w-])")


def requirements(context: Context) -> Iterator[Requirement]:
    for record in context.vault.records.values():
        if isinstance(record, Requirement) and record.lifecycle == "current":
            yield record


@rule("content.languages", "localized texts use the configured languages and are not empty")
def languages(context: Context) -> Iterator[Finding]:
    vault = context.vault
    if vault.config is None:
        return
    allowed = {vault.config.languages.reference, vault.config.languages.second}
    for record in vault.records.values():
        for path, texts in localized_texts(record):
            unknown = set(texts) - allowed
            if unknown:
                yield Finding(
                    "content.languages",
                    "error",
                    f"{path}: unknown language {sorted(unknown)}",
                    record=record.id,
                    file=relative_file(vault, record.id),
                )
            empty = [language for language, text in texts.items() if not text.strip()]
            if empty:
                yield Finding(
                    "content.languages",
                    "error",
                    f"{path}: empty text in {empty}",
                    record=record.id,
                    file=relative_file(vault, record.id),
                )


@rule("content.bilingual", "required fields exist in both languages from draft maturity upward")
def bilingual(context: Context) -> Iterator[Finding]:
    vault = context.vault
    if vault.config is None:
        return
    reference, second = vault.config.languages.reference, vault.config.languages.second
    for record in requirements(context):
        if record.maturity == "concept":
            continue
        for name in vault.config.languages.bilingual_fields:
            value = field_value(record, name)
            if value is None:
                continue
            missing = [language for language in (reference, second) if not value.get(language)]
            if missing:
                yield Finding(
                    "content.bilingual",
                    "error",
                    f"{name} lacks {', '.join(missing)}",
                    record=record.id,
                    file=relative_file(vault, record.id),
                )


@rule("content.writing", "one 'shall' per statement; no vague terms")
def writing(context: Context) -> Iterator[Finding]:
    vault = context.vault
    for record in requirements(context):
        file = relative_file(vault, record.id)
        english = record.statement.get("en")
        if english is not None:
            count = len(shall_pattern.findall(english))
            if count != 1:
                yield Finding(
                    "content.writing",
                    "info" if record.maturity == "concept" else "warning",
                    f"the statement has {count} 'shall' (one requirement per statement is preferred)",
                    record=record.id,
                    file=file,
                )
        for language, terms in vague_terms.items():
            text = record.statement.get(language, "")
            lowered = text.lower()
            found = [
                term
                for term in terms
                if (
                    term in lowered
                    if language == "zh"
                    else re.search(rf"(?<![\w-]){re.escape(term)}(?![\w-])", lowered)
                )
            ]
            if found:
                yield Finding(
                    "content.writing",
                    "warning",
                    f"vague terms in the {language} statement: {found}",
                    record=record.id,
                    file=file,
                )


@rule("content.open_values", "provisional, TBD and TBC values are tracked by an issue")
def open_values(context: Context) -> Iterator[Finding]:
    vault = context.vault
    for record in requirements(context):
        texts = " ".join(record.statement.values())
        texts = reference_pattern.sub(" ", texts)
        prose_open = open_value_pattern.findall(texts)
        has_issue = bool(record.issues) or any(slot.issue for slot in record.values.values())
        if prose_open and not has_issue:
            yield Finding(
                "content.open_values",
                by_maturity(record.maturity, "info", "warning", "error", "error"),
                f"open values in the statement ({', '.join(sorted(set(prose_open))[:4])}) but no "
                "issue tracks them",
                record=record.id,
                file=relative_file(vault, record.id),
                fix="list the issue in `issues`, or give the value slot an issue",
            )
        if record.maturity == "baselined":
            for name, slot in record.values.items():
                if slot.certainty == "tbd":
                    yield Finding(
                        "content.open_values",
                        "error",
                        f"value {name} is TBD in a baselined requirement",
                        record=record.id,
                        file=relative_file(vault, record.id),
                    )


@functools.cache
def unit_registry():
    import pint

    return pint.UnitRegistry()


@rule(
    "content.values", "value slots are used, tracked, and have valid units matching their quantity"
)
def values(context: Context) -> Iterator[Finding]:
    vault = context.vault
    for record in vault.records.values():
        if record.type not in ("requirement", "condition", "interface"):
            continue
        file = relative_file(vault, record.id)
        statement = getattr(record, "statement", None) or {}
        used = {name for text in statement.values() for name in slot_pattern.findall(text)}
        for language, text in statement.items():
            for name in set(slot_pattern.findall(text)) - set(record.values):
                yield Finding(
                    "content.values",
                    "error",
                    f"the {language} statement uses {{{name}}}, which is not a value slot",
                    record=record.id,
                    file=file,
                )
            if record.values:
                missing = set(record.values) - set(slot_pattern.findall(text))
                if missing:
                    yield Finding(
                        "content.values",
                        "error",
                        f"the {language} statement does not show {sorted(missing)}",
                        record=record.id,
                        file=file,
                    )
        for name, slot in record.values.items():
            if record.type == "requirement" and name not in used and not statement:
                continue
            if slot.certainty != "firm" and not slot.issue:
                yield Finding(
                    "content.values",
                    "error",
                    f"{name} is {slot.certainty} without an issue",
                    record=record.id,
                    file=file,
                )
            if slot.unit:
                try:
                    unit = unit_registry().Unit(slot.unit)
                except Exception:  # pint raises several exception types for bad units
                    yield Finding(
                        "content.values",
                        "error",
                        f"{name}: unknown unit {slot.unit!r}",
                        record=record.id,
                        file=file,
                    )
                    continue
                quantity = vault.records.get(slot.quantity) if slot.quantity else None
                if isinstance(quantity, Quantity):
                    try:
                        expected = unit_registry().Unit(quantity.unit)
                    except Exception:
                        continue
                    if unit.dimensionality != expected.dimensionality:
                        yield Finding(
                            "content.values",
                            "error",
                            f"{name}: unit {slot.unit} does not match {quantity.id} ({quantity.unit})",
                            record=record.id,
                            file=file,
                        )


@rule("content.completeness", "rationale and verification are present according to maturity")
def completeness(context: Context) -> Iterator[Finding]:
    vault = context.vault
    for record in requirements(context):
        file = relative_file(vault, record.id)
        if record.rationale is None and record.maturity != "concept":
            yield Finding(
                "content.completeness",
                by_maturity(record.maturity, "info", "warning", "error", "error"),
                "no rationale",
                record=record.id,
                file=file,
            )
        if record.verification is None and record.maturity != "concept":
            yield Finding(
                "content.completeness",
                by_maturity(record.maturity, "info", "warning", "error", "error"),
                "no verification method",
                record=record.id,
                file=file,
            )
        if record.maturity in ("agreed", "baselined"):
            for name, slot in record.values.items():
                if slot.relation == "eq" and slot.tolerance is None and slot.certainty != "tbd":
                    yield Finding(
                        "content.completeness",
                        "warning",
                        f"{name}: an exact value without tolerance",
                        record=record.id,
                        file=file,
                    )
            english = reference_pattern.sub(" ", record.statement.get("en", ""))
            english = slot_pattern.sub(" ", english)
            if number_pattern.search(english):
                yield Finding(
                    "content.completeness",
                    "info",
                    "numbers written in the statement rather than in value slots",
                    record=record.id,
                    file=file,
                )
