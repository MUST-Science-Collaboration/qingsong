"""Change-control rules: stamps, history, suspect links, approvals, translations, stale evidence."""

import datetime
from collections.abc import Iterator

from qingsong.checks import Context, by_maturity, relative_file, rule
from qingsong.findings import Finding
from qingsong.hashing import (
    approved_text_hash,
    field_value,
    normative_hash_of,
    stamp_of,
    text_hash,
)
from qingsong.operations import translation_fields
from qingsong.schema import Requirement


@rule("change.unrecorded", "every change is recorded (the stamp matches the content)")
def unrecorded(context: Context) -> Iterator[Finding]:
    vault = context.vault
    for record in vault.records.values():
        file = relative_file(vault, record.id)
        if stamp_of(record) != record.stamp:
            yield Finding(
                "change.unrecorded",
                "error",
                "content changed since the last recorded change",
                record=record.id,
                file=file,
                fix=f"qingsong revise {record.id} --class editorial|value|reallocate --summary …",
            )
        elif normative_hash_of(record) != record.normative_hash:
            yield Finding(
                "change.unrecorded",
                "error",
                "normative_hash does not match the content",
                record=record.id,
                file=file,
                fix="bookkeeping fields are written by qingsong only",
            )


@rule("change.history", "history is complete and in order")
def history(context: Context) -> Iterator[Finding]:
    vault = context.vault
    for record in vault.records.values():
        file = relative_file(vault, record.id)
        events = record.history
        if not events:
            yield Finding("change.history", "error", "empty history", record=record.id, file=file)
            continue
        if events[0].event not in ("created", "imported") or events[0].revision != 1:
            yield Finding(
                "change.history",
                "error",
                "history must start with revision 1, created or imported",
                record=record.id,
                file=file,
            )
        revisions = [event.revision for event in events]
        if revisions != list(range(1, len(events) + 1)) or revisions[-1] != record.revision:
            yield Finding(
                "change.history",
                "error",
                f"revisions {revisions} do not run 1…{record.revision} without gaps",
                record=record.id,
                file=file,
            )
        dates = [event.date for event in events]
        if dates != sorted(dates):
            yield Finding(
                "change.history", "error", "history dates go backwards", record=record.id, file=file
            )
        value_changes = sum(1 for event in events if event.change_class == "value")
        if record.normative_revision != 1 + value_changes:
            yield Finding(
                "change.history",
                "error",
                f"normative revision {record.normative_revision} does not equal 1 + "
                f"{value_changes} value changes",
                record=record.id,
                file=file,
            )


@rule("change.suspect_link", "links are reviewed after their target changed")
def suspect_links(context: Context) -> Iterator[Finding]:
    vault = context.vault
    for record in vault.records.values():
        if not isinstance(record, Requirement) or record.lifecycle != "current":
            continue
        file = relative_file(vault, record.id)
        for link in [*record.derives_from, *record.constrained_by]:
            target = vault.records.get(link.id)
            if target is None:
                continue
            if link.normative_revision < target.normative_revision:
                yield Finding(
                    "change.suspect_link",
                    by_maturity(record.maturity, "warning", "warning", "error", "error"),
                    f"{link.id} changed (normative revision {link.normative_revision} → "
                    f"{target.normative_revision}) since this link was confirmed",
                    record=record.id,
                    file=file,
                    fix=f"review, then qingsong confirm {record.id} {link.id}",
                )
            elif link.normative_revision > target.normative_revision:
                yield Finding(
                    "change.suspect_link",
                    "error",
                    f"link records normative revision {link.normative_revision} of {link.id}, "
                    f"which is only at {target.normative_revision}",
                    record=record.id,
                    file=file,
                )


@rule(
    "change.approval", "agreed and baselined requirements carry a current approval by an approver"
)
def approvals(context: Context) -> Iterator[Finding]:
    vault = context.vault
    reference = vault.config.languages.reference if vault.config else "en"
    for record in vault.records.values():
        if not isinstance(record, Requirement) or record.lifecycle != "current":
            continue
        file = relative_file(vault, record.id)
        if record.maturity in ("agreed", "baselined"):
            if record.approval is None:
                yield Finding(
                    "change.approval",
                    "error",
                    f"{record.maturity} without an approval",
                    record=record.id,
                    file=file,
                    fix="qingsong approve …",
                )
                continue
            if record.approval.normative_revision != record.normative_revision:
                yield Finding(
                    "change.approval",
                    "error",
                    f"approval covers normative revision {record.approval.normative_revision}, "
                    f"the requirement is at {record.normative_revision}",
                    record=record.id,
                    file=file,
                    fix="approve again, or reopen as draft",
                )
            elif record.approval.text_hash != approved_text_hash(record, reference):
                yield Finding(
                    "change.approval",
                    "error",
                    "the approved wording (statement or verification criteria) has changed",
                    record=record.id,
                    file=file,
                    fix="approve again, or reopen as draft",
                )
        if (
            record.approval
            and vault.people
            and record.approval.by in vault.people.people
            and not vault.is_approver(record.approval.by)
        ):
            yield Finding(
                "change.approval",
                "warning",
                f"approved by {record.approval.by}, who is no longer listed as an approver",
                record=record.id,
                file=file,
            )


@rule("change.translation", "translations are tracked, current, and reviewed where required")
def translations(context: Context) -> Iterator[Finding]:
    vault = context.vault
    if vault.config is None:
        return
    languages = {vault.config.languages.reference, vault.config.languages.second}
    for record in vault.records.values():
        if record.type not in ("requirement", "figure") or record.lifecycle != "current":
            continue
        maturity = getattr(record, "maturity", "draft")
        origin = record.text_origin
        if origin not in languages:
            continue
        file = relative_file(vault, record.id)
        for name in translation_fields(vault, record.type):
            value = field_value(record, name)
            if not isinstance(value, dict) or not languages <= set(value):
                continue
            state = record.translation.get(name)
            if state is None:
                yield Finding(
                    "change.translation",
                    by_maturity(maturity, "info", "warning", "error", "error"),
                    f"{name}: translation not tracked",
                    record=record.id,
                    file=file,
                    fix=f"qingsong revise {record.id} --class editorial --translation updated|reviewed",
                )
                continue
            if state.source_hash != text_hash(value[origin]):
                yield Finding(
                    "change.translation",
                    by_maturity(maturity, "warning", "warning", "error", "error"),
                    f"{name}: the {origin} text changed after the translation was made",
                    record=record.id,
                    file=file,
                    fix="update the other language, then revise with --translation updated|reviewed",
                )
            elif (
                origin != vault.config.languages.reference
                and maturity in ("agreed", "baselined")
                and state.status != "reviewed"
            ):
                yield Finding(
                    "change.translation",
                    "error",
                    f"{name}: text written in {origin} needs a reviewed translation at {maturity}",
                    record=record.id,
                    file=file,
                )
            if (
                state.status == "reviewed"
                and state.by
                and vault.people
                and state.by in vault.people.people
            ):
                reads = set(vault.people.people[state.by].languages)
                if not languages <= reads:
                    yield Finding(
                        "change.translation",
                        "error",
                        f"{name}: reviewed by {state.by}, who is not listed as reading "
                        f"{' and '.join(sorted(languages))}",
                        record=record.id,
                        file=file,
                        fix="list the reviewer's languages in people.yaml",
                    )


@rule("change.stale_evidence", "verifications and waivers refer to the current normative revision")
def stale_evidence(context: Context) -> Iterator[Finding]:
    vault = context.vault
    today = datetime.date.today()
    for record in vault.records.values():
        if record.type not in ("verification", "waiver") or record.lifecycle != "current":
            continue
        file = relative_file(vault, record.id)
        target = vault.records.get(record.requirement)
        if (
            target is not None
            and record.requirement_normative_revision != target.normative_revision
        ):
            yield Finding(
                "change.stale_evidence",
                "error",
                f"refers to normative revision {record.requirement_normative_revision} of "
                f"{record.requirement}, now at {target.normative_revision}",
                record=record.id,
                file=file,
            )
        if record.type == "waiver" and record.expires and record.expires < today:
            yield Finding(
                "change.stale_evidence",
                "error",
                f"waiver expired on {record.expires}",
                record=record.id,
                file=file,
            )
