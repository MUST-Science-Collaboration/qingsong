"""Stamps and text hashes (docs/SPEC.md §7, §8.2)."""

import hashlib
import json
from pathlib import Path
from typing import Any

from qingsong.schema import Proposal, RecordBase

stamp_excluded_fields = {"stamp", "history"}
normative_fields: dict[str, tuple[str, ...]] = {
    "requirement": ("values", "level", "verification.methods"),
    "condition": ("values",),
    "interface": ("owner_end", "other_end", "values"),
    "quantity": ("dimension", "unit"),
}


def short_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def canonical_json(data: Any) -> bytes:
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def stamp_of(record: RecordBase) -> str:
    content = record.model_dump(mode="json", exclude=stamp_excluded_fields, exclude_none=True)
    return short_hash(canonical_json(content))


def text_hash(text: str) -> str:
    return short_hash(text.strip().encode())


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def field_value(record: RecordBase, dotted: str) -> Any:
    value: Any = record.model_dump(mode="json", exclude_none=True)
    for part in dotted.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def normative_hash_of(record: RecordBase) -> str:
    """Hash of the fields whose change can never be editorial (values, level, verification method…)."""
    fields = normative_fields.get(record.type, ())
    return short_hash(canonical_json({name: field_value(record, name) for name in fields}))


review_fields = (
    "title",
    "statement",
    "values",
    "rationale",
    "notes",
    "suggestions",
    "verification.criteria",
)


def review_hash(record: RecordBase) -> str:
    """Hash of a record's prose and values in every language: what an issue accepted as written
    covers (docs/SPEC.md §5.6)."""
    return short_hash(canonical_json({name: field_value(record, name) for name in review_fields}))


def proposal_hash(proposal: Proposal) -> str:
    """Hash of what a reviewer reads of a proposal: its summary, change class and changes. A
    decisions file carries it, so that a proposal edited after the review page was made is not
    decided unread (docs/SPEC.md §5.6)."""
    content = proposal.model_dump(
        mode="json", include={"summary", "change_class", "changes"}, exclude_none=True
    )
    return short_hash(canonical_json(content))


def field_text_hashes(record: RecordBase, dotted: str) -> dict[str, str]:
    """Hash of each language's text of one field; the base of a proposed change."""
    value = field_value(record, dotted)
    if not isinstance(value, dict):
        return {}
    return {language: text_hash(text) for language, text in value.items()}


def approved_text_hash(record: RecordBase, language: str) -> str:
    """Hash of the approved wording: statement and verification criteria in the reference language."""
    statement = field_value(record, "statement") or {}
    criteria = field_value(record, "verification.criteria") or {}
    return short_hash(
        canonical_json({"statement": statement.get(language), "criteria": criteria.get(language)})
    )
