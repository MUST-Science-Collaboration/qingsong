"""JSON export of the record, with an index of value slots (docs/SPEC.md §12.3)."""

import math
from typing import Any

from qingsong import __version__
from qingsong.checks.consistency import Interval, allowed, convert
from qingsong.checks.content import requirement_form
from qingsong.ids import sort_key
from qingsong.schema import Quantity, Requirement, ValueSlot
from qingsong.vault import Vault

export_format = "qingsong-export"
format_version = 1


def bound(number: float) -> float | None:
    return None if math.isinf(number) else number


def interval_entry(interval: Interval | None) -> dict[str, Any] | None:
    if interval is None:
        return None
    return {
        "low": bound(interval.low),
        "high": bound(interval.high),
        "low_open": interval.low_open,
        "high_open": interval.high_open,
    }


def canonical_entry(slot: ValueSlot, quantity: Quantity | None) -> dict[str, Any] | None:
    if quantity is None:
        return None

    def converted(number: float | None) -> float | None:
        return None if number is None else convert(number, slot.unit, quantity)

    return {
        "unit": quantity.unit,
        "value": converted(slot.value),
        "minimum": converted(slot.minimum),
        "maximum": converted(slot.maximum),
    }


def value_entries(vault: Vault) -> list[dict[str, Any]]:
    entries = []
    requirements = [
        record
        for record in vault.records.values()
        if isinstance(record, Requirement) and record.lifecycle == "current"
    ]
    for requirement in sorted(requirements, key=lambda record: sort_key(record.id)):
        for name, slot in sorted(requirement.values.items()):
            found = vault.records.get(slot.quantity or "")
            quantity = found if isinstance(found, Quantity) else None
            entry = {"requirement": requirement.id, "slot": name}
            entry.update(slot.model_dump(mode="json"))
            entry.update(
                {
                    "maturity": requirement.maturity,
                    "allocated_to": requirement.allocated_to,
                    "level": requirement.level,
                    "revision": requirement.revision,
                    "normative_revision": requirement.normative_revision,
                    "canonical": canonical_entry(slot, quantity),
                    "interval": interval_entry(allowed(slot, quantity) if quantity else None),
                }
            )
            entries.append(entry)
    return entries


def node_entries(vault: Vault) -> list[dict[str, Any]]:
    return [
        {
            "reference": reference,
            "code": info.node.node,
            "names": dict(info.node.names),
            "kind": info.node.kind,
            "status": info.node.status,
            "structural_code": info.node.structural_code,
            "system": info.system,
            "parent": info.parent,
            "depth": info.depth,
        }
        for reference, info in sorted(vault.nodes.items())
    ]


def export_vault(vault: Vault, commit: str | None, dirty: bool | None) -> dict[str, Any]:
    records = sorted(vault.records.values(), key=lambda record: sort_key(record.id))
    return {
        "format": export_format,
        "format_version": format_version,
        "engine": __version__,
        "project": vault.config.project.code if vault.config else None,
        "commit": commit,
        "dirty": dirty,
        "records": [record.model_dump(mode="json", exclude_none=True) for record in records],
        "nodes": node_entries(vault),
        "values": value_entries(vault),
        "forms": {
            record.id: requirement_form(record)
            for record in records
            if isinstance(record, Requirement) and record.lifecycle == "current"
        },
    }
