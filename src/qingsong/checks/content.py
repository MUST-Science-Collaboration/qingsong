"""Content rules: languages, writing rules (INCOSE-derived), references, open values, value slots,
completeness and evidence."""

import functools
import re
from collections.abc import Iterator

from qingsong.checks import Context, by_maturity, relative_file, rule
from qingsong.findings import Finding
from qingsong.hashing import field_value
from qingsong.ids import any_double_bracket, reference_pattern
from qingsong.schema import Issue, Quantity, Requirement
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
math_or_code = re.compile(r"\$[^$\n]+\$|`[^`\n]+`")
markdown_link = re.compile(r"\[[^\[\]]*\]\([^)]*\)|\[\^[^\]]*\]")
open_value_pattern = re.compile(
    r"\[[^\[\]]+\]|(?<![A-Za-z0-9])(?:TBD|TBC)(?![A-Za-z0-9])|待定|待确认"
)
slot_pattern = re.compile(r"\{([a-z][a-z0-9_]*)\}")
shall_pattern = re.compile(r"\bshall\b", re.IGNORECASE)
number_pattern = re.compile(r"(?<![\w.-])\d+(?:[.,]\d+)?(?![\w-])")


def prose(text: str) -> str:
    """Text with references, mathematics, code, links and footnotes removed."""
    for pattern in (reference_pattern, math_or_code, markdown_link):
        text = pattern.sub(" ", text)
    return text


def requirements(context: Context) -> Iterator[Requirement]:
    for record in context.vault.records.values():
        if isinstance(record, Requirement) and record.lifecycle == "current":
            yield record


@rule(
    "content.languages",
    "texts use the configured languages, are not empty, and exist in the origin language",
)
def languages(context: Context) -> Iterator[Finding]:
    vault = context.vault
    if vault.config is None:
        return
    allowed = {vault.config.languages.reference, vault.config.languages.second}
    for info in vault.nodes.values():
        if info.node.text_origin and info.node.text_origin not in allowed:
            yield Finding(
                "content.languages",
                "error",
                f"node {info.reference} has text_origin {info.node.text_origin!r}",
                file=info.file,
                fix=f"use one of {sorted(allowed)}",
            )
    for record in vault.records.values():
        file = relative_file(vault, record.id)
        origin = getattr(record, "text_origin", vault.config.languages.reference)
        if origin not in allowed:
            yield Finding(
                "content.languages",
                "error",
                f"text_origin {origin!r} is not configured",
                record=record.id,
                file=file,
                fix=f"use one of {sorted(allowed)}",
            )
        for path, texts in localized_texts(record):
            unknown = set(texts) - allowed
            if unknown:
                yield Finding(
                    "content.languages",
                    "error",
                    f"{path}: unknown language {sorted(unknown)}",
                    record=record.id,
                    file=file,
                )
            empty = [language for language, text in texts.items() if not text.strip()]
            if empty or not texts:
                yield Finding(
                    "content.languages",
                    "error",
                    f"{path}: empty text {('in ' + str(empty)) if empty else ''}".strip(),
                    record=record.id,
                    file=file,
                )
        for name in ("title", "statement", "caption"):
            value = getattr(record, name, None)
            if isinstance(value, dict) and value and origin in allowed and origin not in value:
                yield Finding(
                    "content.languages",
                    "error",
                    f"{name} lacks its origin language ({origin})",
                    record=record.id,
                    file=file,
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
            if not isinstance(value, dict):
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
            count = len(shall_pattern.findall(prose(english)))
            if count != 1:
                yield Finding(
                    "content.writing",
                    "info" if record.maturity == "concept" else "warning",
                    f"the statement has {count} 'shall' (one requirement per statement is "
                    "preferred)",
                    record=record.id,
                    file=file,
                )
        for language, terms in vague_terms.items():
            lowered = prose(record.statement.get(language, "")).lower()
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


@rule("content.references", "[[…]] references are well formed")
def reference_syntax(context: Context) -> Iterator[Finding]:
    vault = context.vault
    for record in vault.records.values():
        for path, texts in localized_texts(record):
            for text in texts.values():
                for doubled in re.findall(
                    r"(?:Sections?|第)\s*\[\[[A-Za-z0-9._-]+#[A-Za-z0-9_-]+\]\]", text
                ):
                    yield Finding(
                        "content.references",
                        "warning",
                        f"{path}: {doubled}: a section reference already reads "
                        "'Section 4.1' / '第4.1节'",
                        record=record.id,
                        file=relative_file(vault, record.id),
                        fix="drop the word before the reference",
                    )
                for candidate in any_double_bracket.findall(text):
                    if not reference_pattern.fullmatch(candidate):
                        yield Finding(
                            "content.references",
                            "warning",
                            f"{path}: {candidate} is not a valid reference",
                            record=record.id,
                            file=relative_file(vault, record.id),
                            fix="write [[ID]] or [[DOCUMENT#section]] without spaces",
                        )


def tracking_issues(context: Context, record: Requirement) -> list[str]:
    return [*record.issues, *(slot.issue for slot in record.values.values() if slot.issue)]


@rule("content.open_values", "provisional, TBD and TBC values are tracked by an open issue")
def open_values(context: Context) -> Iterator[Finding]:
    vault = context.vault
    for record in requirements(context):
        file = relative_file(vault, record.id)
        found = sorted(
            set(
                open_value_pattern.findall(
                    " ".join(prose(text) for text in record.statement.values())
                )
            )
        )
        issues = tracking_issues(context, record)
        if found and not issues:
            yield Finding(
                "content.open_values",
                by_maturity(record.maturity, "info", "warning", "error", "error"),
                f"open values in the statement ({', '.join(found[:4])}) but no issue tracks them",
                record=record.id,
                file=file,
                fix="list the issue in `issues`, or give the value slot an issue",
            )
        if record.maturity in ("agreed", "baselined"):
            for issue_id in issues:
                issue = vault.records.get(issue_id)
                if isinstance(issue, Issue) and (
                    issue.status != "open" or not issue.owner or not issue.due
                ):
                    yield Finding(
                        "content.open_values",
                        "error",
                        f"{issue_id} must be open, with an owner and a due point, while it "
                        "tracks an open value",
                        record=record.id,
                        file=file,
                    )
        if record.maturity == "baselined":
            for name, slot in record.values.items():
                if slot.certainty == "tbd":
                    yield Finding(
                        "content.open_values",
                        "error",
                        f"value {name} is TBD in a baselined requirement",
                        record=record.id,
                        file=file,
                    )


@functools.cache
def unit_registry():
    import pint

    return pint.UnitRegistry()


def parse_unit(text: str):
    try:
        return unit_registry().Unit(text)
    except Exception:  # pint raises several exception types for bad units
        return None


@rule(
    "content.values", "value slots are used, tracked, and have valid units matching their quantity"
)
def values(context: Context) -> Iterator[Finding]:
    vault = context.vault
    for record in vault.records.values():
        file = relative_file(vault, record.id)
        if isinstance(record, Quantity):
            unit = parse_unit(record.unit)
            if unit is None:
                yield Finding(
                    "content.values",
                    "error",
                    f"unknown unit {record.unit!r}",
                    record=record.id,
                    file=file,
                )
            elif str(unit.dimensionality) != record.dimension and not (
                record.dimension in ("[]", "dimensionless") and unit.dimensionless
            ):
                yield Finding(
                    "content.values",
                    "error",
                    f"unit {record.unit} has dimension {unit.dimensionality}, "
                    f"not {record.dimension}",
                    record=record.id,
                    file=file,
                )
            continue
        if record.type not in ("requirement", "condition", "interface"):
            continue
        statement = getattr(record, "statement", None) or {}
        for language, text in statement.items():
            used = set(slot_pattern.findall(prose(text)))
            for name in sorted(used - set(record.values)):
                yield Finding(
                    "content.values",
                    "error",
                    f"the {language} statement uses {{{name}}}, which is not a value slot",
                    record=record.id,
                    file=file,
                )
            missing = set(record.values) - used
            if missing:
                yield Finding(
                    "content.values",
                    "error",
                    f"the {language} statement does not show {sorted(missing)}",
                    record=record.id,
                    file=file,
                )
        for name, slot in record.values.items():
            if slot.certainty != "firm" and not slot.issue:
                yield Finding(
                    "content.values",
                    "error",
                    f"{name} is {slot.certainty} without an issue",
                    record=record.id,
                    file=file,
                )
            if not slot.unit:
                continue
            unit = parse_unit(slot.unit)
            if unit is None:
                yield Finding(
                    "content.values",
                    "error",
                    f"{name}: unknown unit {slot.unit!r}",
                    record=record.id,
                    file=file,
                )
                continue
            quantity = vault.records.get(slot.quantity) if slot.quantity else None
            expected = parse_unit(quantity.unit) if isinstance(quantity, Quantity) else None
            if expected is not None and unit.dimensionality != expected.dimensionality:
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
        severity = by_maturity(record.maturity, "info", "warning", "error", "error")
        if record.rationale is None and record.maturity != "concept":
            yield Finding(
                "content.completeness", severity, "no rationale", record=record.id, file=file
            )
        if record.verification is None and record.maturity != "concept":
            yield Finding(
                "content.completeness",
                severity,
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
            english = slot_pattern.sub(" ", prose(record.statement.get("en", "")))
            if number_pattern.search(english):
                yield Finding(
                    "content.completeness",
                    "info",
                    "numbers written in the statement rather than in value slots",
                    record=record.id,
                    file=file,
                )


@rule("content.evidence", "a 'compliant' verification names evidence")
def evidence(context: Context) -> Iterator[Finding]:
    vault = context.vault
    for record in vault.records.values():
        if (
            record.type == "verification"
            and record.status in ("compliant", "partially_compliant")
            and not record.evidence
        ):
            yield Finding(
                "content.evidence",
                "error",
                f"{record.status} without evidence",
                record=record.id,
                file=relative_file(vault, record.id),
                fix="add the report, analysis or file that shows compliance",
            )
