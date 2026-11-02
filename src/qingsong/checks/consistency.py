"""Consistency rules: values that cannot all hold, children looser than their parents, overdue
issues (docs/SPEC.md §10, "Consistency rules in detail")."""

import datetime
import math
from collections.abc import Iterator
from dataclasses import dataclass

from qingsong.checks import Context, relative_file, rule
from qingsong.checks.content import parse_unit, unit_registry
from qingsong.findings import Finding
from qingsong.schema import Issue, Quantity, Requirement, ValueSlot
from qingsong.vault import Vault

relative_tolerance = 1e-9


def same(first: float, second: float) -> bool:
    if math.isinf(first) or math.isinf(second):
        return first == second
    return math.isclose(first, second, rel_tol=relative_tolerance, abs_tol=0.0)


@dataclass(frozen=True)
class Interval:
    """The values a slot allows, in its quantity's unit."""

    low: float
    high: float
    low_open: bool = False
    high_open: bool = False

    def intersection(self, other: "Interval") -> "Interval | None":
        if same(self.low, other.low):
            low, low_open = self.low, self.low_open or other.low_open
        elif self.low > other.low:
            low, low_open = self.low, self.low_open
        else:
            low, low_open = other.low, other.low_open
        if same(self.high, other.high):
            high, high_open = self.high, self.high_open or other.high_open
        elif self.high < other.high:
            high, high_open = self.high, self.high_open
        else:
            high, high_open = other.high, other.high_open
        if same(low, high):
            return None if (low_open or high_open) else Interval(low, high)
        if low > high:
            return None
        return Interval(low, high, low_open, high_open)

    def within(self, other: "Interval") -> bool:
        if same(self.low, other.low):
            low_ok = self.low_open or not other.low_open
        else:
            low_ok = self.low > other.low
        if same(self.high, other.high):
            high_ok = self.high_open or not other.high_open
        else:
            high_ok = self.high < other.high
        return low_ok and high_ok

    def describe(self, unit: str) -> str:
        unit_text = "" if unit in ("", "dimensionless") else f" {unit}"
        if math.isinf(self.low) and math.isinf(self.high):
            return "any value"
        if math.isinf(self.low):
            return f"{'<' if self.high_open else '≤'} {self.high:g}{unit_text}"
        if math.isinf(self.high):
            return f"{'>' if self.low_open else '≥'} {self.low:g}{unit_text}"
        if same(self.low, self.high):
            return f"{self.low:g}{unit_text}"
        left = "(" if self.low_open else "["
        right = ")" if self.high_open else "]"
        return f"{left}{self.low:g}, {self.high:g}{right}{unit_text}"


def convert(number: float, unit: str | None, quantity: Quantity) -> float | None:
    """A number in the slot's unit, expressed in the quantity's unit; None if it cannot be."""
    target = parse_unit(quantity.unit)
    if target is None:
        return None
    if not unit:
        return number if target.dimensionless else None
    source = parse_unit(unit)
    if source is None or source.dimensionality != target.dimensionality:
        return None
    try:
        return float(unit_registry().Quantity(number, source).to(target).magnitude)
    except Exception:  # pint raises several exception types for impossible conversions
        return None


def allowed(slot: ValueSlot, quantity: Quantity) -> Interval | None:
    """The interval a slot allows, or None when it is not comparable."""
    if slot.certainty == "tbd":
        return None

    def at(number: float | None) -> float | None:
        return None if number is None else convert(number, slot.unit, quantity)

    infinity = math.inf
    relation = slot.relation
    if relation == "range":
        low, high = at(slot.minimum), at(slot.maximum)
        if low is None or high is None:
            return None
        return Interval(min(low, high), max(low, high))
    value = at(slot.value)
    if value is None:
        return None
    if relation == "le":
        return Interval(-infinity, value)
    if relation == "lt":
        return Interval(-infinity, value, True, True)
    if relation == "ge":
        return Interval(value, infinity)
    if relation == "gt":
        return Interval(value, infinity, True, True)
    if relation == "approx" and slot.tolerance is None:
        return None
    if slot.tolerance is None:
        return Interval(value, value)
    assert slot.value is not None
    low = at(slot.value - slot.tolerance.minus)
    high = at(slot.value + slot.tolerance.plus)
    if low is None or high is None:
        return None
    return Interval(min(low, high), max(low, high))


def condition_key(slot: ValueSlot, reference: str) -> str:
    text = (slot.condition or {}).get(reference, "")
    return " ".join(text.split()).casefold().rstrip(".;,。；，")


@dataclass(frozen=True)
class Constraint:
    requirement: Requirement
    quantity: Quantity
    condition: str
    interval: Interval
    slots: tuple[str, ...]
    certainties: tuple[str, ...]

    def describe(self) -> str:
        text = self.interval.describe(self.quantity.unit)
        uncertain = sorted({c for c in self.certainties if c != "firm"})
        return f"{text} ({', '.join(uncertain)})" if uncertain else text


def constraints(vault: Vault) -> Iterator[Constraint | tuple[Requirement, str, str]]:
    """Per current requirement and (quantity, condition): the combined interval of its slots.
    A requirement whose own slots on one quantity allow no value is yielded as a problem tuple."""
    reference = vault.config.languages.reference if vault.config else "en"
    for record in vault.records.values():
        if not isinstance(record, Requirement) or record.lifecycle != "current":
            continue
        groups: dict[tuple[str, str], list[tuple[str, ValueSlot, Interval]]] = {}
        for name, slot in sorted(record.values.items()):
            quantity = vault.records.get(slot.quantity or "")
            if not isinstance(quantity, Quantity):
                continue
            interval = allowed(slot, quantity)
            if interval is None:
                continue
            key = (quantity.id, condition_key(slot, reference))
            groups.setdefault(key, []).append((name, slot, interval))
        for (quantity_id, condition), members in groups.items():
            quantity = vault.records[quantity_id]
            assert isinstance(quantity, Quantity)
            combined: Interval | None = members[0][2]
            for _, _, interval in members[1:]:
                combined = combined.intersection(interval) if combined else None
            if combined is None:
                yield record, quantity_id, ", ".join(name for name, _, _ in members)
                continue
            yield Constraint(
                record,
                quantity,
                condition,
                combined,
                tuple(name for name, _, _ in members),
                tuple(slot.certainty for _, slot, _ in members),
            )


def related_nodes(vault: Vault, first: str, second: str) -> bool:
    """The same node, or one an ancestor of the other."""

    def ancestors(reference: str) -> set[str]:
        found: set[str] = set()
        current: str | None = reference
        while current and current not in found:
            found.add(current)
            info = vault.nodes.get(current)
            current = info.parent if info else None
        return found

    return first in ancestors(second) or second in ancestors(first)


def condition_label(condition: str) -> str:
    return f" ({condition})" if condition else ""


@rule("consistency.conflict", "requirements on one quantity leave a value that meets them all")
def conflicts(context: Context) -> Iterator[Finding]:
    vault = context.vault
    groups: dict[tuple[str, str], list[Constraint]] = {}
    for item in constraints(vault):
        if isinstance(item, tuple):
            record, quantity_id, names = item
            yield Finding(
                "consistency.conflict",
                "warning",
                f"its own slots {names} on {quantity_id} allow no common value",
                record=record.id,
                file=relative_file(vault, record.id),
            )
            continue
        groups.setdefault((item.quantity.id, item.condition), []).append(item)
    for (quantity_id, condition), members in groups.items():
        members.sort(key=lambda constraint: constraint.requirement.id)
        for index, first in enumerate(members):
            for second in members[index + 1 :]:
                if first.requirement.id == second.requirement.id:
                    continue
                if not related_nodes(
                    vault, first.requirement.allocated_to, second.requirement.allocated_to
                ):
                    continue
                if first.interval.intersection(second.interval) is not None:
                    continue
                for this, other in ((first, second), (second, first)):
                    yield Finding(
                        "consistency.conflict",
                        "warning",
                        f"{quantity_id}{condition_label(condition)}: {this.describe()} here, "
                        f"{other.describe()} in {other.requirement.id}; no value meets both",
                        record=this.requirement.id,
                        file=relative_file(vault, this.requirement.id),
                        fix="change one of them, or raise a conflict issue for the owners",
                    )


@rule("consistency.child_looser", "a child allows no values its parent excludes (same quantity)")
def child_looser(context: Context) -> Iterator[Finding]:
    vault = context.vault
    by_requirement: dict[str, dict[tuple[str, str], Constraint]] = {}
    for item in constraints(vault):
        if isinstance(item, Constraint):
            key = (item.quantity.id, item.condition)
            by_requirement.setdefault(item.requirement.id, {})[key] = item
    for child_id, child_constraints in sorted(by_requirement.items()):
        child = vault.records[child_id]
        assert isinstance(child, Requirement)
        for link in child.derives_from:
            parent_constraints = by_requirement.get(link.id, {})
            for key, constraint in sorted(child_constraints.items()):
                parent = parent_constraints.get(key)
                if parent is None:
                    continue
                environmental = bool(constraint.quantity.environmental)
                inner, outer = (
                    (parent.interval, constraint.interval)
                    if environmental
                    else (constraint.interval, parent.interval)
                )
                if inner.within(outer):
                    continue
                quantity_id, condition = key
                expectation = (
                    "must cover the parent's range" if environmental else "must lie inside it"
                )
                yield Finding(
                    "consistency.child_looser",
                    "warning",
                    f"{quantity_id}{condition_label(condition)}: {constraint.describe()} here, "
                    f"{parent.describe()} in the parent {link.id}; the child {expectation}",
                    record=child_id,
                    file=relative_file(vault, child_id),
                    fix="tighten the child, or record why the parent is not binding here",
                )


@rule("consistency.issue_due", "open issues are not past their due date")
def issue_due(context: Context) -> Iterator[Finding]:
    vault = context.vault
    today = datetime.date.today()
    for record in vault.records.values():
        if not isinstance(record, Issue) or record.status != "open" or not record.due:
            continue
        try:
            due = datetime.date.fromisoformat(record.due.strip())
        except ValueError:
            continue
        if due < today:
            yield Finding(
                "consistency.issue_due",
                "warning",
                f"due {due.isoformat()}, which has passed",
                record=record.id,
                file=relative_file(vault, record.id),
                fix="close the issue, or set a new due date with a reason in the closure plan",
            )
