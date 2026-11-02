"""Review items (docs/SPEC.md §5.6): raising issues from findings, proposals and decisions.

The demo's ISS-0001 already holds proposal 1, so proposals made here are number 2."""

import datetime
from pathlib import Path

import pytest
from conftest import edit_yaml, requirement_file

from qingsong import checks, operations, review
from qingsong.operations import OperationError
from qingsong.vault import load

day = datetime.date(2026, 11, 2)


def two_shalls(root: Path) -> None:
    def change(data):
        data["statement"]["en"] = "The read noise shall be {read_noise}. It shall be read slowly."

    edit_yaml(requirement_file(root, "INS-DET-REQ-001"), change)
    operations.revise(root, "INS-DET-REQ-001", "editorial", "two shalls", "alice", today=day)


def writing_findings(root: Path):
    return [f for f in checks.run(load(root)) if f.rule == "content.writing"]


def test_raise_from_checks_tracks_each_finding_once(demo):
    two_shalls(demo)
    raised = review.raise_from_checks(demo, "bob", {"content.writing"}, today=day)
    assert [issue.id for issue in raised] == ["ISS-0002"]
    issue = load(demo).records["ISS-0002"]
    assert issue.kind == "wording" and issue.rule == "content.writing"
    assert issue.records == ["INS-DET-REQ-001"]
    assert all(finding.issue == "ISS-0002" for finding in writing_findings(demo))
    assert review.raise_from_checks(demo, "bob", {"content.writing"}, today=day) == []


def test_accepting_a_bilingual_fix_revises_the_record_and_closes_the_issue(demo):
    two_shalls(demo)
    review.raise_from_checks(demo, "bob", {"content.writing"}, today=day)
    fixed = {
        "en": "The read noise in the slow readout mode shall be {read_noise}.",
        "zh": "慢读出模式下的读出噪声应为{read_noise}。",
    }
    change = {"record": "INS-DET-REQ-001", "field": "statement", "text": fixed}
    review.propose(demo, "ISS-0002", "bob", {"en": "one shall"}, [change], today=day)
    with pytest.raises(OperationError, match="not an approver"):
        review.accept(demo, "ISS-0002", 1, "bob", today=day)
    review.accept(demo, "ISS-0002", 1, "alice", via="test-agent", today=day)
    vault = load(demo)
    record = vault.records["INS-DET-REQ-001"]
    assert record.statement == fixed
    assert record.translation["statement"].status == "reviewed"
    assert record.translation["statement"].by == "alice"
    assert record.history[-1].summary.startswith("ISS-0002 proposal 1")
    issue = vault.records["ISS-0002"]
    assert issue.status == "closed" and issue.outcome == "fixed"
    assert issue.proposals[0].status == "accepted"
    assert writing_findings(demo) == []
    assert not [f for f in checks.run(vault) if f.severity == "error"]


def test_a_fix_in_one_language_leaves_the_translation_to_update(demo):
    two_shalls(demo)
    review.raise_from_checks(demo, "bob", {"content.writing"}, today=day)
    change = {
        "record": "INS-DET-REQ-001",
        "field": "statement",
        "text": {"en": "The read noise in the slow mode shall be {read_noise}."},
    }
    review.propose(demo, "ISS-0002", "bob", {"en": "English only"}, [change], today=day)
    review.accept(demo, "ISS-0002", 1, "alice", today=day)
    findings = checks.run(load(demo))
    assert any(f.rule == "change.translation" and "statement" in f.message for f in findings)


def test_keeping_the_text_turns_the_finding_into_a_note_until_the_text_changes(demo):
    two_shalls(demo)
    review.raise_from_checks(demo, "bob", {"content.writing"}, today=day)
    review.propose(demo, "ISS-0002", "bob", {"en": "a compound test step"}, [], today=day)
    review.accept(demo, "ISS-0002", 1, "alice", today=day)
    issue = load(demo).records["ISS-0002"]
    assert issue.outcome == "accepted_as_written" and "INS-DET-REQ-001" in issue.accepted
    notes = writing_findings(demo)
    assert notes and all(f.severity == "info" and f.issue == "ISS-0002" for f in notes)

    def reword(data):
        data["rationale"]["en"] = "A different rationale."

    edit_yaml(requirement_file(demo, "INS-DET-REQ-001"), reword)
    operations.revise(demo, "INS-DET-REQ-001", "editorial", "reworded", "alice", today=day)
    assert any(f.severity == "warning" for f in writing_findings(demo))


def test_a_stale_proposal_is_refused(demo):
    change = {"record": "INS-DET-REQ-001", "field": "notes", "text": {"en": "Shorter note."}}
    review.propose(demo, "ISS-0001", "bob", {"en": "shorter"}, [change], today=day)

    def reword(data):
        data["notes"]["en"] = "Edited meanwhile."

    edit_yaml(requirement_file(demo, "INS-DET-REQ-001"), reword)
    operations.revise(demo, "INS-DET-REQ-001", "editorial", "meanwhile", "alice", today=day)
    with pytest.raises(OperationError, match="out of date"):
        review.accept(demo, "ISS-0001", 2, "alice", today=day)


def test_accepting_a_change_to_an_agreed_requirement_approves_the_new_text(demo):
    change = {
        "record": "INS-SYS-REQ-001",
        "field": "rationale",
        "text": {"en": "A clearer reason.", "zh": "更清楚的理由。"},
    }
    review.propose(demo, "ISS-0001", "bob", {"en": "clearer"}, [change], today=day)
    review.accept(demo, "ISS-0001", 2, "alice", today=day)
    vault = load(demo)
    record = vault.records["INS-SYS-REQ-001"]
    assert record.maturity == "agreed" and record.approval.ref == "ISS-0001 P2"
    assert not [f for f in checks.run(vault) if f.rule == "change.approval"]


def test_a_failed_acceptance_restores_every_record(demo, monkeypatch):
    changes = [
        {"record": "INS-DET-REQ-001", "field": "notes", "text": {"en": "First."}},
        {"record": "INS-OPT-REQ-001", "field": "rationale", "text": {"en": "Second."}},
    ]
    review.propose(demo, "ISS-0001", "bob", {"en": "two records"}, changes, today=day)
    before = {
        record_id: requirement_file(demo, record_id).read_text()
        for record_id in ("INS-DET-REQ-001", "INS-OPT-REQ-001")
    }
    original_revise = review.revise
    calls = []

    def failing_revise(*arguments, **options):
        calls.append(arguments[1])
        if len(calls) == 2:
            raise OperationError("simulated failure")
        return original_revise(*arguments, **options)

    monkeypatch.setattr(review, "revise", failing_revise)
    with pytest.raises(OperationError, match="simulated"):
        review.accept(demo, "ISS-0001", 2, "alice", today=day)
    for record_id, text in before.items():
        assert requirement_file(demo, record_id).read_text() == text
    assert load(demo).records["ISS-0001"].status == "open"


def test_reject_and_close(demo):
    change = {"record": "INS-DET-REQ-001", "field": "notes", "text": {"en": "Other note."}}
    review.propose(demo, "ISS-0001", "bob", {"en": "other"}, [change], today=day)
    review.reject(demo, "ISS-0001", 2, "bob", {"en": "withdrawn by its author"}, today=day)
    with pytest.raises(OperationError, match="already rejected"):
        review.accept(demo, "ISS-0001", 2, "alice", today=day)
    with pytest.raises(OperationError, match="not an approver"):
        review.close(demo, "ISS-0001", "answered", {"en": "done"}, "bob", today=day)
    review.close(demo, "ISS-0001", "answered", {"en": "characterized"}, "alice", today=day)
    issue = load(demo).records["ISS-0001"]
    assert issue.status == "closed" and issue.outcome == "answered"


def test_proposals_are_checked_when_made(demo):
    def propose(change):
        review.propose(demo, "ISS-0001", "bob", {"en": "x"}, [change], today=day)

    with pytest.raises(OperationError, match="no record"):
        propose({"record": "INS-DET-REQ-099", "field": "statement", "text": {"en": "x"}})
    with pytest.raises(OperationError, match="cannot be changed"):
        propose({"record": "INS-DET-REQ-001", "field": "level", "text": {"en": "x"}})
    with pytest.raises(OperationError, match="text must give"):
        propose({"record": "INS-DET-REQ-001", "field": "statement", "text": {"fr": "x"}})


def test_a_translation_review_marks_machine_translations_reviewed(demo):
    def machine(data):
        data["translation"]["statement"]["status"] = "machine"
        del data["translation"]["statement"]["by"]
        del data["translation"]["statement"]["date"]

    edit_yaml(requirement_file(demo, "INS-DET-REQ-001"), machine)
    operations.revise(demo, "INS-DET-REQ-001", "editorial", "marked", "alice", today=day)
    operations.revise(
        demo, "INS-DET-REQ-001", "editorial", "reviewed", "alice", translation="reviewed", today=day
    )
    state = load(demo).records["INS-DET-REQ-001"].translation["statement"]
    assert state.status == "reviewed" and state.by == "alice"


def test_a_hand_raised_issue_can_track_a_rule_over_several_records(demo):
    two_shalls(demo)
    issue = review.raise_issue(
        demo,
        "wording",
        {"en": "Compound statements"},
        {"en": "Kept together on purpose."},
        ["INS-DET-REQ-001"],
        "bob",
        rule="content.writing",
        today=day,
    )
    assert all(finding.issue == issue.id for finding in writing_findings(demo))
    with pytest.raises(OperationError, match="unknown rule"):
        review.raise_issue(demo, "wording", {"en": "x"}, {"en": "x"}, [], "bob", rule="x.y")


# regressions from the independent review of 2026-11-02 ------------------------------------------
def test_a_translation_review_keeps_other_reviewers(demo):
    operations.revise(
        demo, "INS-OPT-REQ-001", "editorial", "re-review", "bob", translation="reviewed", today=day
    )
    states = load(demo).records["INS-OPT-REQ-001"].translation.values()
    assert all(state.by == "alice" for state in states)


def test_any_current_acceptance_covers_the_finding(demo):
    two_shalls(demo)
    first = review.raise_issue(
        demo,
        "wording",
        {"en": "a"},
        {"en": "a"},
        ["INS-DET-REQ-001"],
        "bob",
        rule="content.writing",
        today=day,
    )
    second = review.raise_issue(
        demo,
        "wording",
        {"en": "b"},
        {"en": "b"},
        ["INS-DET-REQ-001"],
        "bob",
        rule="content.writing",
        today=day,
    )
    review.propose(demo, second.id, "bob", {"en": "keep"}, [], today=day)
    review.accept(demo, second.id, 1, "alice", today=day)

    def retitle(data):
        data["title"]["en"] = "Read noise, slow mode"

    edit_yaml(requirement_file(demo, "INS-DET-REQ-001"), retitle)
    operations.revise(demo, "INS-DET-REQ-001", "editorial", "retitled", "alice", today=day)
    review.propose(demo, first.id, "bob", {"en": "keep"}, [], today=day)
    review.accept(demo, first.id, 1, "alice", today=day)
    assert all(f.severity == "info" for f in writing_findings(demo))


def test_keeping_the_text_needs_a_rule_and_records(demo):
    with pytest.raises(OperationError, match="would change nothing"):
        review.propose(demo, "ISS-0001", "bob", {"en": "keep"}, [], today=day)


def test_malformed_proposals_are_refused(demo):
    change = {"record": "INS-DET-REQ-001", "field": "notes", "text": {"en": "x"}}
    with pytest.raises(OperationError, match="summary"):
        review.propose(demo, "ISS-0001", "bob", "just a string", [change], today=day)
    with pytest.raises(OperationError, match="mapping"):
        review.propose(demo, "ISS-0001", "bob", {"en": "x"}, ["INS-DET-REQ-001"], today=day)
    with pytest.raises(OperationError, match="twice"):
        review.propose(demo, "ISS-0001", "bob", {"en": "x"}, [change, change], today=day)


@pytest.mark.parametrize("text", ["a\x0bb\nc", "a\rb\nc", "a\x85b\nc", "a\u2028b\nc", "a\tb\nc"])
def test_texts_a_literal_block_cannot_hold_are_left_quoted(text):
    from ruamel.yaml.comments import CommentedMap

    from qingsong.operations import serialize
    from qingsong.vault import round_trip_yaml

    data = CommentedMap(text=text)
    assert round_trip_yaml().load(serialize(data))["text"] == text
