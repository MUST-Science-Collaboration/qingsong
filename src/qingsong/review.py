"""Review items (docs/SPEC.md §5.6): issues raised from check findings, proposed fixes, and the
approver's decisions. Every change goes through the recorded operations of `operations`."""

import datetime
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ruamel.yaml.comments import CommentedMap

from qingsong import checks, ids
from qingsong.findings import Finding
from qingsong.hashing import field_text_hashes, review_hash, text_hash
from qingsong.operations import (
    OperationError,
    allocate_number,
    approve,
    edit,
    finish,
    history_event,
    languages_of,
    load_round_trip,
    require_current,
    require_person,
    require_record,
    require_recorded,
    revise,
    serialize,
    today_date,
    translation_fields,
    write_atomically,
)
from qingsong.schema import Issue, Proposal, RecordBase
from qingsong.vault import Vault, load

kind_of_rule = {
    "content.writing": "wording",
    "structure.justification": "tbj",
    "content.open_values": "provisional",
    "content.values": "provisional",
    "change.translation": "translation",
}
proposal_fields = (
    "title",
    "statement",
    "rationale",
    "notes",
    "suggestions",
    "verification.criteria",
)
kind_labels = {
    "tbd": {"en": "TBD", "zh": "待定"},
    "tbc": {"en": "TBC", "zh": "待确认"},
    "provisional": {"en": "Provisional", "zh": "暂定"},
    "tbj": {"en": "No parent (TBJ)", "zh": "缺少上级需求"},
    "wording": {"en": "Wording", "zh": "表述"},
    "translation": {"en": "Translation", "zh": "译文"},
    "question": {"en": "Question", "zh": "问题"},
    "conflict": {"en": "Conflict", "zh": "冲突"},
}


def require_issue(vault: Vault, issue_id: str, open_only: bool = True) -> Issue:
    record = require_record(vault, issue_id)
    if not isinstance(record, Issue):
        raise OperationError(f"{issue_id} is not an issue")
    if open_only and record.status != "open":
        raise OperationError(f"{issue_id} is closed")
    return record


def require_approver(vault: Vault, person: str) -> None:
    require_person(vault, person)
    if not vault.is_approver(person):
        raise OperationError(f"{person} is not an approver (people.yaml)")


def write_new_issue(vault: Vault, data: dict[str, Any], number: int) -> RecordBase:
    record_id = ids.format_id("issue", None, number)
    content = CommentedMap()
    content["id"] = record_id
    for key, value in data.items():
        content[key] = value
    path = vault.root / ids.relative_path("issue", record_id)
    return finish(path, content, exclusive=True)


def issue_skeleton(
    kind: str,
    title: dict[str, str],
    description: dict[str, str],
    records: list[str],
    person: str,
    today: datetime.date,
    rule: str | None = None,
    owner: str | None = None,
    due: str | None = None,
    via: str | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "type": "issue",
        "title": title,
        "lifecycle": "current",
        "kind": kind,
        "status": "open",
        "description": description,
    }
    if owner:
        data["owner"] = owner
    if due:
        data["due"] = due
    data["records"] = records
    if rule:
        data["rule"] = rule
    data.update(
        {
            "revision": 1,
            "normative_revision": 1,
            "normative_hash": "0" * 16,
            "history": [history_event(1, today, person, "created", "raised", via=via)],
        }
    )
    return data


# raising --------------------------------------------------------------------------------------
def untracked_findings(vault: Vault, rules: set[str] | None = None) -> list[Finding]:
    """Warnings on records that no open issue tracks and no acceptance covers."""
    return [
        finding
        for finding in checks.run(vault)
        if finding.record
        and finding.severity == "warning"
        and finding.issue is None
        and (rules is None or finding.rule in rules)
        and finding.record in vault.records
    ]


def raise_from_checks(
    root: Path,
    person: str,
    rules: set[str] | None = None,
    group: bool = False,
    owner: str | None = None,
    via: str | None = None,
    today: datetime.date | None = None,
) -> list[RecordBase]:
    today = today_date(today)
    vault = load(root)
    require_person(vault, person)
    if rules:
        unknown = rules - set(checks.all_rule_summaries())
        if unknown:
            raise OperationError(f"unknown rules: {', '.join(sorted(unknown))}")
    by_rule: dict[str, dict[str, list[str]]] = {}
    for finding in untracked_findings(vault, rules):
        assert finding.record is not None
        by_rule.setdefault(finding.rule, {}).setdefault(finding.record, []).append(finding.message)
    batches: list[tuple[str, list[str], list[str]]] = []
    for rule_id, records in sorted(by_rule.items()):
        if group:
            distinct = {text for texts in records.values() for text in texts}
            messages = (
                [f"{distinct.pop()} ({len(records)} records)"]
                if len(distinct) == 1
                else [f"{record}: {'; '.join(texts)}" for record, texts in records.items()]
            )
            batches.append((rule_id, sorted(records, key=ids.sort_key), messages))
        else:
            for record_id in sorted(records, key=ids.sort_key):
                batches.append((rule_id, [record_id], records[record_id]))
    number = allocate_number(vault, "issue", None)
    written = []
    for rule_id, record_ids, messages in batches:
        kind = kind_of_rule.get(rule_id, "question")
        label = kind_labels[kind]
        if len(record_ids) == 1:
            target = vault.records[record_ids[0]]
            title = {
                "en": f"{label['en']}: {record_ids[0]} ({target.title.get('en', '')})",
                "zh": f"{label['zh']}：{record_ids[0]}（{target.title.get('zh', '')}）",
            }
        else:
            title = {
                "en": f"{label['en']}: {len(record_ids)} records",
                "zh": f"{label['zh']}：{len(record_ids)}条记录",
            }
        description = {
            "en": "Raised from the check `"
            + rule_id
            + "`:\n\n"
            + "\n".join(f"- {message}" for message in messages)
        }
        data = issue_skeleton(
            kind, title, description, record_ids, person, today, rule_id, owner, via=via
        )
        written.append(write_new_issue(vault, data, number))
        number += 1
    return written


def raise_issue(
    root: Path,
    kind: str,
    title: dict[str, str],
    description: dict[str, str],
    records: list[str],
    person: str,
    owner: str | None = None,
    due: str | None = None,
    via: str | None = None,
    rule: str | None = None,
    today: datetime.date | None = None,
) -> RecordBase:
    """An issue written by hand. With `rule`, it tracks that rule's findings on its records,
    for example several records grouped under one proposed fix."""
    today = today_date(today)
    vault = load(root)
    require_person(vault, person)
    if kind not in kind_labels:
        raise OperationError(f"kind must be one of {', '.join(kind_labels)}")
    if rule and rule not in checks.all_rule_summaries():
        raise OperationError(f"unknown rule {rule}")
    for record_id in records:
        require_record(vault, record_id)
    data = issue_skeleton(kind, title, description, records, person, today, rule, owner, due, via)
    return write_new_issue(vault, data, allocate_number(vault, "issue", None))


# proposals ------------------------------------------------------------------------------------
def checked_changes(vault: Vault, changes: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate proposed changes against the current records and add their base hashes."""
    languages = set(languages_of(vault))
    result = []
    for change in changes:
        record_id, field, text = change.get("record"), change.get("field"), change.get("text")
        if not isinstance(record_id, str) or not isinstance(field, str):
            raise OperationError("each change needs record and field")
        record = require_record(vault, record_id)
        require_current(record)
        if field not in proposal_fields or field.split(".")[0] not in type(record).model_fields:
            raise OperationError(f"{record_id}: {field} cannot be changed by a proposal")
        if field == "verification.criteria" and getattr(record, "verification", None) is None:
            raise OperationError(f"{record_id} has no verification to change")
        if not isinstance(text, dict) or not text or not set(text) <= languages:
            raise OperationError(
                f"{record_id} {field}: text must give one or more of {', '.join(sorted(languages))}"
            )
        if any(not isinstance(value, str) or not value.strip() for value in text.values()):
            raise OperationError(f"{record_id} {field}: empty text")
        current = field_text_hashes(record, field)
        base = {language: current.get(language, "") for language in text}
        result.append({"record": record_id, "field": field, "text": dict(text), "base": base})
    return result


def propose(
    root: Path,
    issue_id: str,
    person: str,
    summary: dict[str, str],
    changes: list[dict[str, Any]],
    change_class: str = "editorial",
    via: str | None = None,
    today: datetime.date | None = None,
) -> RecordBase:
    """Add a proposed fix to an open issue. Without changes, it proposes keeping the text."""
    today = today_date(today)
    vault = load(root)
    require_person(vault, person)
    issue = require_issue(vault, issue_id)
    if change_class not in ("editorial", "value", "reallocate"):
        raise OperationError("the class must be editorial, value or reallocate")
    if not summary or not any(text.strip() for text in summary.values()):
        raise OperationError("a proposal needs a summary")
    checked = checked_changes(vault, changes)
    number = max((proposal.number for proposal in (issue.proposals or [])), default=0) + 1

    def change(data: CommentedMap, old: RecordBase) -> None:
        entry: dict[str, Any] = {"number": number, "date": today, "by": person}
        if via:
            entry["via"] = via
        entry["summary"] = summary
        if change_class != "editorial":
            entry["change_class"] = change_class
        entry["status"] = "proposed"
        if checked:
            entry["changes"] = checked
        data.setdefault("proposals", []).append(entry)
        data["revision"] = old.revision + 1
        what = f"proposal {number}" + ("" if checked else " (keep as written)")
        data["history"].append(
            history_event(old.revision + 1, today, person, "revised", what, via=via)
        )

    return edit(vault, issue_id, change)


def find_proposal(issue: Issue, number: int) -> Proposal:
    for proposal in issue.proposals or []:
        if proposal.number == number:
            if proposal.status != "proposed":
                raise OperationError(f"{issue.id} proposal {number} is already {proposal.status}")
            return proposal
    raise OperationError(f"{issue.id} has no proposal {number}")


def stale_changes(vault: Vault, proposal: Proposal) -> list[str]:
    stale = []
    for change in proposal.changes:
        record = vault.records.get(change.record)
        if record is None:
            stale.append(f"{change.record} no longer exists")
            continue
        current = field_text_hashes(record, change.field)
        for language, base in change.base.items():
            if current.get(language, "") != base:
                stale.append(f"{change.record} {change.field}.{language} changed since")
    return stale


def set_field(data: CommentedMap, field: str, language: str, text: str) -> None:
    """Set one language of a prose field. A new top-level field goes after the prose field that
    precedes it in the reading order, so the file keeps its usual layout."""
    *parents, last = field.split(".")
    target = data
    for name in parents:
        target = target[name]
    if last not in target or target[last] is None:
        if parents:
            target[last] = CommentedMap()
        else:
            order = list(proposal_fields)
            earlier = [name for name in order[: order.index(last)] if name in target]
            position = (list(target).index(earlier[-1]) + 1) if earlier else len(target)
            target.insert(position, last, CommentedMap())
    target[last][language] = text


def close_issue_data(
    data: CommentedMap,
    old: Issue,
    outcome: str,
    resolution: dict[str, str],
    person: str,
    today: datetime.date,
    via: str | None,
    accepted_number: int | None = None,
    accepted_hashes: dict[str, str] | None = None,
) -> None:
    for entry in data.get("proposals", []):
        if entry["number"] == accepted_number:
            entry["status"] = "accepted"
        elif entry["status"] == "proposed":
            entry["status"] = "rejected"
            entry["reason"] = (
                {"en": f"proposal {accepted_number} was accepted instead"}
                if accepted_number
                else {"en": "the issue was closed"}
            )
    data["status"] = "closed"
    data["outcome"] = outcome
    if accepted_hashes:
        data["accepted"] = accepted_hashes
    data["resolution"] = resolution
    data["revision"] = old.revision + 1
    data["history"].append(
        history_event(
            old.revision + 1,
            today,
            person,
            "revised",
            f"closed: {outcome}" + (f" (proposal {accepted_number})" if accepted_number else ""),
            via=via,
        )
    )


def accept(
    root: Path,
    issue_id: str,
    number: int,
    person: str,
    decision: str | None = None,
    via: str | None = None,
    today: datetime.date | None = None,
) -> list[RecordBase]:
    """Apply an accepted proposal and close its issue. Every target is checked before any file
    is written, and written files are restored if a later step fails."""
    today = today_date(today)
    vault = load(root)
    require_approver(vault, person)
    issue = require_issue(vault, issue_id)
    proposal = find_proposal(issue, number)
    stale = stale_changes(vault, proposal)
    if stale:
        raise OperationError(
            f"{issue_id} proposal {number} is out of date ({'; '.join(stale)}); propose again"
        )
    reference, second = languages_of(vault)
    targets: dict[str, list] = {}
    for change in proposal.changes:
        targets.setdefault(change.record, []).append(change)
    for record_id in targets:
        record = require_record(vault, record_id)
        require_current(record)
        require_recorded(record)
        if getattr(record, "maturity", None) == "baselined" and not decision:
            raise OperationError(f"{record_id} is baselined: give --decision")
    summary_text = proposal.summary.get("en") or next(iter(proposal.summary.values()))
    reason = f"{issue_id} proposal {number}: {summary_text}"
    originals = {record_id: vault.files[record_id].read_text("utf-8") for record_id in targets}
    written: list[RecordBase] = []
    try:
        for record_id, changes in targets.items():
            record = vault.records[record_id]
            path = vault.files[record_id]
            data = load_round_trip(path)
            origin = getattr(record, "text_origin", None)
            translated = second if origin == reference else reference
            reviewed_fields = []
            for change in changes:
                for language, text in change.text.items():
                    set_field(data, change.field, language, text)
                if translated in change.text:
                    reviewed_fields.append(change.field)
            if reviewed_fields and origin and "translation" in type(record).model_fields:
                translation = data.setdefault("translation", CommentedMap())
                for field in reviewed_fields:
                    if field not in translation_fields(vault, record.type):
                        continue
                    value = data
                    for name in field.split("."):
                        value = value[name]
                    if origin in value and len(value) > 1:
                        translation[field] = {
                            "source_hash": text_hash(value[origin]),
                            "status": "reviewed",
                            "by": person,
                            "date": today,
                        }
            write_atomically(path, serialize(data))
            written.append(
                revise(
                    root,
                    record_id,
                    proposal.change_class,
                    reason,
                    person,
                    decision=decision,
                    via=via,
                    today=today,
                )
            )
            if getattr(record, "maturity", None) == "agreed":
                written.append(
                    approve(root, record_id, "agreed", person, f"{issue_id} P{number}", via, today)
                )
        vault = load(root)
        accepted_hashes = (
            {}
            if proposal.changes
            else {
                record_id: review_hash(vault.records[record_id])
                for record_id in issue.records
                if record_id in vault.records
            }
        )
        outcome = "fixed" if proposal.changes else "accepted_as_written"
        resolution = {"en": f"Proposal {number} accepted: {summary_text}"}
        if "zh" in proposal.summary:
            resolution["zh"] = f"采纳方案{number}：{proposal.summary['zh']}"
        written.append(
            edit(
                vault,
                issue_id,
                lambda data, old: close_issue_data(
                    data, old, outcome, resolution, person, today, via, number, accepted_hashes
                ),
            )
        )
    except Exception:
        for record_id, text in originals.items():
            write_atomically(vault.files[record_id], text)
        raise
    return written


def reject(
    root: Path,
    issue_id: str,
    number: int,
    person: str,
    reason: dict[str, str],
    via: str | None = None,
    today: datetime.date | None = None,
) -> RecordBase:
    today = today_date(today)
    vault = load(root)
    require_person(vault, person)
    issue = require_issue(vault, issue_id)
    proposal = find_proposal(issue, number)
    if not vault.is_approver(person) and person != proposal.by:
        raise OperationError("a proposal is rejected by an approver or withdrawn by its author")

    def change(data: CommentedMap, old: RecordBase) -> None:
        for entry in data["proposals"]:
            if entry["number"] == number:
                entry["status"] = "rejected"
                entry["reason"] = reason
        data["revision"] = old.revision + 1
        data["history"].append(
            history_event(
                old.revision + 1, today, person, "revised", f"proposal {number} rejected", via=via
            )
        )

    return edit(vault, issue_id, change)


def close(
    root: Path,
    issue_id: str,
    outcome: str,
    resolution: dict[str, str],
    person: str,
    via: str | None = None,
    today: datetime.date | None = None,
) -> RecordBase:
    today = today_date(today)
    vault = load(root)
    require_approver(vault, person)
    require_issue(vault, issue_id)
    if outcome not in ("answered", "withdrawn", "fixed"):
        raise OperationError(
            "close takes --outcome answered, withdrawn or fixed; accept a proposal to keep "
            "the text as written"
        )
    if not resolution or not any(text.strip() for text in resolution.values()):
        raise OperationError("give the resolution")
    return edit(
        vault,
        issue_id,
        lambda data, old: close_issue_data(data, old, outcome, resolution, person, today, via),
    )
