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
    require_person,
    today_date,
    write_atomically,
)
from qingsong.schema import RecordBase, StrictModel, plain
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
            accepted.setdefault(entry.issue, entry.proposal)
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
        if entry.decision == "accept":
            stale = review.stale_changes(vault, proposal)
            if stale:
                problems.append(f"{label} is out of date ({'; '.join(stale)}); propose again")
        elif not is_approver and person != proposal.by:
            problems.append(
                f"{label}: a proposal is rejected by an approver or withdrawn by its author"
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
    file_text = path.read_text(encoding="utf-8")
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
    if problems:
        raise OperationError(
            "nothing applied:\n" + "\n".join(f"- {problem}" for problem in problems)
        )
    person = decisions.decided_by
    originals = {
        record_path: record_path.read_text("utf-8") for record_path in vault.files.values()
    }
    kept = kept_path(root, person, today)
    # Rejections first: accepting a proposal closes its issue and rejects the others.
    ordered = sorted(decisions.decisions, key=lambda entry: entry.decision == "accept")
    applied = Applied(person, branch, False, kept)
    try:
        for entry in ordered:
            if entry.decision == "reject":
                reason = {"en": entry.note.strip() or default_rejection_reason}
                written = [
                    review.reject(root, entry.issue, entry.proposal, person, reason, via, today)
                ]
            else:
                written = review.accept(root, entry.issue, entry.proposal, person, None, via, today)
            applied.applied.append(AppliedDecision(entry, written))
        write_atomically(kept, file_text, exclusive=True)
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
        raise
    return applied
