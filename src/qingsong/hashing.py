"""Stamps and text hashes (docs/SPEC.md §7, §8.2)."""

import hashlib
import json
from pathlib import Path
from typing import Any

from qingsong.schema import RecordBase

stamp_excluded_fields = {"stamp", "history"}
normative_fields: dict[str, tuple[str, ...]] = {
    "requirement": ("values", "level", "verification.method"),
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
