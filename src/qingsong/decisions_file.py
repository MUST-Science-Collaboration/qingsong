"""Decisions files (docs/SPEC.md §5.6): one reviewer's decisions on proposed fixes, saved from the
review page and applied all or nothing through `review.reject` and `review.accept`."""

import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError

from qingsong import gitutil, review
from qingsong.hashing import proposal_hash
from qingsong.operations import (
    OperationError,
    load_round_trip,
    require_current,
    require_person,
    require_recorded,
    today_date,
    write_atomically,
)
from qingsong.schema import Proposal, RecordBase, StrictModel, plain
from qingsong.vault import Vault, load

reviews_folder = "reviews"
main_branch = "main"
default_rejection_reason = "rejected in review"


class ReviewDecision(StrictModel):
    issue: str
    proposal: int = Field(ge=1)
    decision: Literal["accept", "reject"]
    note: str = ""
    proposal_hash: str
    decision_record: str | None = None


class DecisionsFile(StrictModel):
    format: Literal["qingsong-decisions/1"]
    project: str
    decided_by: str
    saved: datetime.datetime | None = None
    decisions: list[ReviewDecision] = Field(min_length=1)


@dataclass
class AppliedDecision:
    decision: ReviewDecision
    written: list[RecordBase]


@dataclass
class Applied:
    decided_by: str
    branch: str | None
    started_branch: bool
    kept: Path
    applied: list[AppliedDecision] = field(default_factory=list)


def read_decisions(path: Path) -> DecisionsFile:
    if not path.is_file():
        raise OperationError(f"no decisions file at {path}")
    data = plain(load_round_trip(path))
    try:
        return DecisionsFile.model_validate(data)
    except ValidationError as error:
        details = "; ".join(
            f"{'.'.join(str(part) for part in problem['loc'])}: {problem['msg']}"
            for problem in error.errors()
        )
        raise OperationError(f"{path.name} is not a decisions file ({details})") from error


def problems_with(vault: Vault, decisions: DecisionsFile) -> list[str]:
    """Every reason the file cannot be applied, found without writing anything."""
    problems = []
    project = vault.config.project.code
    if decisions.project != project:
        problems.append(f"the file is for project {decisions.project}, this vault is {project}")
    person = decisions.decided_by
    try:
        require_person(vault, person)
    except OperationError as error:
        problems.append(str(error))
    is_approver = vault.is_approver(person)
    if not is_approver and any(entry.decision == "accept" for entry in decisions.decisions):
        problems.append(f"{person} is not an approver (people.yaml); only approvers accept")
    decided: set[tuple[str, int]] = set()
    accepted: dict[str, int] = {}
    changed_by: dict[tuple[str, str], str] = {}
    for entry in decisions.decisions:
        label = f"{entry.issue} proposal {entry.proposal}"
        if (entry.issue, entry.proposal) in decided:
            problems.append(f"{label} is decided twice")
            continue
        decided.add((entry.issue, entry.proposal))
        if entry.decision == "accept":
            if entry.issue in accepted:
                problems.append(
                    f"{entry.issue}: proposals {accepted[entry.issue]} and {entry.proposal} are "
                    "both accepted; accept one"
                )
                continue
            accepted[entry.issue] = entry.proposal
        try:
            issue = review.require_issue(vault, entry.issue)
            proposal = review.find_proposal(issue, entry.proposal)
        except OperationError as error:
            problems.append(str(error))
            continue
        if proposal_hash(proposal) != entry.proposal_hash:
            problems.append(
                f"{label} has changed since the review page was made; render the page again "
                "and read it before deciding"
            )
            continue
        if entry.decision == "reject":
            if not is_approver and person != proposal.by:
                problems.append(
                    f"{label}: a proposal is rejected by an approver or withdrawn by its author"
                )
            continue
        stale = review.stale_changes(vault, proposal)
        if stale:
            problems.append(f"{label} is out of date ({'; '.join(stale)}); propose again")
        problems.extend(
            f"{label}: {problem}" for problem in target_problems(vault, entry, proposal)
        )
        for change in proposal.changes:
            target = (change.record, change.field)
            if target in changed_by and changed_by[target] != label:
                problems.append(
                    f"{changed_by[target]} and {label} both change {change.record} "
                    f"{change.field}; accept one, then propose the other again"
                )
            changed_by.setdefault(target, label)
    return problems


def target_problems(vault: Vault, entry: ReviewDecision, proposal: Proposal) -> list[str]:
    """What `review.accept` would refuse in the records it writes."""
    problems = []
    issue = vault.records[entry.issue]
    try:
        require_recorded(issue)
    except OperationError as error:
        problems.append(str(error))
    if entry.decision_record:
        record = vault.records.get(entry.decision_record)
        if record is None or record.type != "decision":
            problems.append(f"{entry.decision_record} is not a decision record")
    for record_id in dict.fromkeys(change.record for change in proposal.changes):
        record = vault.records.get(record_id)
        if record is None:
            continue  # reported as out of date
        for guard in (require_current, require_recorded):
            try:
                guard(record)
            except OperationError as error:
                problems.append(str(error))
        if getattr(record, "maturity", None) == "baselined" and not entry.decision_record:
            problems.append(
                f"{record_id} is baselined: the decision needs a decision_record (DEC-…)"
            )
    return problems


def kept_path(root: Path, person: str, today: datetime.date) -> Path:
    folder = root / reviews_folder
    candidate = folder / f"{today.isoformat()}_{person}.yaml"
    number = 2
    while candidate.exists():
        candidate = folder / f"{today.isoformat()}_{person}_{number}.yaml"
        number += 1
    return candidate


def review_branch_name(root: Path, person: str, today: datetime.date) -> str:
    name = f"review/{today.isoformat()}-{person}"
    candidate, number = name, 2
    while gitutil.branch_exists(root, candidate):
        candidate = f"{name}-{number}"
        number += 1
    return candidate


def language_of(text: str) -> str:
    return "zh" if any("\u3400" <= character <= "\u9fff" for character in text) else "en"


def apply(
    root: Path,
    path: Path,
    via: str | None = None,
    today: datetime.date | None = None,
) -> Applied:
    """Apply a decisions file: check every decision, then apply them all or none. On the main
    branch the changes move to a new review branch. Nothing is committed."""
    today = today_date(today)
    decisions = read_decisions(path)
    file_bytes = path.read_bytes()
    vault = load(root)
    problems = problems_with(vault, decisions)
    branch = gitutil.current_branch(root) if gitutil.is_repository(root) else None
    new_branch = None
    if branch == main_branch:
        if [other for other in gitutil.uncommitted_paths(root) if other != path.resolve()]:
            problems.append(
                "the vault is on the main branch with uncommitted changes; commit or move them "
                "first, so that the decisions start a clean review branch"
            )
        new_branch = review_branch_name(root, decisions.decided_by, today)
        if gitutil.branch_exists(root, "review"):
            problems.append(
                "a branch named review exists, so git cannot start review/…; rename it first"
            )
    if problems:
        raise OperationError(
            "nothing applied:\n" + "\n".join(f"- {problem}" for problem in problems)
        )
    person = decisions.decided_by
    originals = {
        record_path: record_path.read_text("utf-8") for record_path in vault.files.values()
    }
    kept = kept_path(root, person, today)
    folder_existed = kept.parent.exists()
    # Rejections first: accepting a proposal closes its issue and rejects the others.
    ordered = sorted(decisions.decisions, key=lambda entry: entry.decision == "accept")
    applied = Applied(person, branch, False, kept)
    try:
        for entry in ordered:
            if entry.decision == "reject":
                note = entry.note.strip() or default_rejection_reason
                reason = {language_of(note): note}
                written = [
                    review.reject(root, entry.issue, entry.proposal, person, reason, via, today)
                ]
            else:
                written = review.accept(
                    root, entry.issue, entry.proposal, person, entry.decision_record, via, today
                )
            applied.applied.append(AppliedDecision(entry, written))
        kept.parent.mkdir(parents=True, exist_ok=True)
        with kept.open("xb") as handle:  # exactly as saved, line endings included
            handle.write(file_bytes)
        if new_branch:
            try:
                gitutil.switch_to_new_branch(root, new_branch)
            except gitutil.GitError as error:
                raise OperationError(f"could not start the branch {new_branch}: {error}") from error
            applied.branch, applied.started_branch = new_branch, True
    except BaseException:
        for record_path, text in originals.items():
            if record_path.read_text("utf-8") != text:
                write_atomically(record_path, text)
        kept.unlink(missing_ok=True)
        if not folder_existed and kept.parent.exists() and not any(kept.parent.iterdir()):
            kept.parent.rmdir()
        raise
    return applied
