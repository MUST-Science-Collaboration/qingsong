"""Decisions files from the review page, applied all or nothing (docs/SPEC.md §5.6)."""

import datetime
from pathlib import Path

import pytest
from conftest import edit_yaml, git, requirement_file

from qingsong import decisions_file, review
from qingsong.hashing import proposal_hash
from qingsong.operations import OperationError
from qingsong.vault import load

day = datetime.date(2026, 11, 2)


def second_proposal(root: Path) -> None:
    change = {"record": "INS-DET-REQ-001", "field": "notes", "text": {"en": "A shorter note."}}
    review.propose(root, "ISS-0001", "bob", {"en": "shorter note"}, [change], today=day)


def hash_of(root: Path, issue_id: str, number: int) -> str:
    issue = load(root).records[issue_id]
    return proposal_hash(next(p for p in issue.proposals if p.number == number))


def decisions_yaml(person: str, entries: list[dict], project: str = "DEMO") -> str:
    lines = [
        "format: qingsong-decisions/1",
        f"project: {project}",
        f"decided_by: {person}",
        'saved: "2026-11-02T07:40:00.000Z"',
        "decisions:",
    ]
    for entry in entries:
        lines.append(f"  - issue: {entry['issue']}")
        lines.append(f"    proposal: {entry['proposal']}")
        lines.append(f"    decision: {entry['decision']}")
        if "note" in entry:
            lines.append(f'    note: "{entry["note"]}"')
        lines.append(f"    proposal_hash: {entry['hash']}")
    return "\n".join(lines) + "\n"


def write_decisions(folder: Path, person: str, entries: list[dict], **options) -> Path:
    path = folder / "decisions.yaml"
    path.write_text(decisions_yaml(person, entries, **options), encoding="utf-8")
    return path


def snapshot(root: Path) -> dict[Path, str]:
    return {path: path.read_text("utf-8") for path in sorted(root.rglob("*.yaml"))}


def test_rejections_go_first_and_the_file_is_kept(demo, tmp_path):
    second_proposal(demo)
    entries = [
        {
            "issue": "ISS-0001",
            "proposal": 2,
            "decision": "accept",
            "hash": hash_of(demo, "ISS-0001", 2),
        },
        {
            "issue": "ISS-0001",
            "proposal": 1,
            "decision": "reject",
            "note": "the value is not ready",
            "hash": hash_of(demo, "ISS-0001", 1),
        },
    ]
    path = write_decisions(tmp_path, "alice", entries)
    result = decisions_file.apply(demo, path, today=day)
    issue = load(demo).records["ISS-0001"]
    assert issue.status == "closed" and issue.outcome == "fixed"
    first, second = issue.proposals
    assert first.status == "rejected" and first.reason == {"en": "the value is not ready"}
    assert second.status == "accepted"
    assert load(demo).records["INS-DET-REQ-001"].notes["en"] == "A shorter note."
    assert [entry.decision.decision for entry in result.applied] == ["reject", "accept"]
    assert result.kept == demo / "reviews" / "2026-11-02_alice.yaml"
    assert result.kept.read_text("utf-8") == path.read_text("utf-8")
    assert result.branch is None and not result.started_branch


def test_a_rejection_without_a_note_gets_a_reason_and_a_second_sitting_a_second_file(
    demo, tmp_path
):
    second_proposal(demo)
    entries = [
        {
            "issue": "ISS-0001",
            "proposal": 2,
            "decision": "reject",
            "hash": hash_of(demo, "ISS-0001", 2),
        }
    ]
    decisions_file.apply(demo, write_decisions(tmp_path, "alice", entries), today=day)
    proposal = load(demo).records["ISS-0001"].proposals[1]
    assert proposal.reason == {"en": "rejected in review"}
    entries = [
        {
            "issue": "ISS-0001",
            "proposal": 1,
            "decision": "reject",
            "hash": hash_of(demo, "ISS-0001", 1),
        }
    ]
    result = decisions_file.apply(demo, write_decisions(tmp_path, "alice", entries), today=day)
    assert result.kept.name == "2026-11-02_alice_2.yaml"


def test_every_problem_is_reported_and_nothing_is_written(demo, tmp_path):
    second_proposal(demo)
    good_first, good_second = hash_of(demo, "ISS-0001", 1), hash_of(demo, "ISS-0001", 2)
    entries = [
        {"issue": "ISS-0001", "proposal": 1, "decision": "accept", "hash": good_first},
        {"issue": "ISS-0001", "proposal": 2, "decision": "accept", "hash": good_second},
        {"issue": "ISS-0001", "proposal": 2, "decision": "reject", "hash": good_second},
        {"issue": "ISS-0009", "proposal": 1, "decision": "reject", "hash": good_first},
    ]
    before = snapshot(demo)
    path = write_decisions(tmp_path, "bob", entries, project="OTHER")
    with pytest.raises(OperationError) as raised:
        decisions_file.apply(demo, path, today=day)
    message = str(raised.value)
    assert message.startswith("nothing applied")
    assert "for project OTHER, this vault is DEMO" in message
    assert "bob is not an approver" in message
    assert "proposals 1 and 2 are both accepted" in message
    assert "ISS-0001 proposal 2 is decided twice" in message
    assert "ISS-0009" in message
    assert snapshot(demo) == before
    assert not (demo / "reviews").exists()


def test_a_proposal_changed_after_the_page_was_made_is_refused(demo, tmp_path):
    read_hash = hash_of(demo, "ISS-0001", 1)

    def reword(data):
        data["proposals"][0]["summary"]["en"] = "Something else entirely."

    edit_yaml(demo / "issues" / "ISS-0001.yaml", reword)
    entries = [{"issue": "ISS-0001", "proposal": 1, "decision": "accept", "hash": read_hash}]
    with pytest.raises(OperationError, match="has changed since the review page was made"):
        decisions_file.apply(demo, write_decisions(tmp_path, "alice", entries), today=day)


def test_an_out_of_date_acceptance_is_refused_before_anything_is_written(demo, tmp_path):
    second_proposal(demo)
    entries = [
        {
            "issue": "ISS-0001",
            "proposal": 2,
            "decision": "accept",
            "hash": hash_of(demo, "ISS-0001", 2),
        }
    ]

    def reword(data):
        data["notes"]["en"] = "Edited meanwhile."

    edit_yaml(requirement_file(demo, "INS-DET-REQ-001"), reword)
    with pytest.raises(OperationError, match="out of date"):
        decisions_file.apply(demo, write_decisions(tmp_path, "alice", entries), today=day)


def test_a_failure_while_applying_restores_every_record(demo, tmp_path, monkeypatch):
    second_proposal(demo)
    entries = [
        {
            "issue": "ISS-0001",
            "proposal": 1,
            "decision": "reject",
            "hash": hash_of(demo, "ISS-0001", 1),
        },
        {
            "issue": "ISS-0001",
            "proposal": 2,
            "decision": "accept",
            "hash": hash_of(demo, "ISS-0001", 2),
        },
    ]
    before = snapshot(demo)

    def failing_accept(*arguments, **options):
        raise OperationError("simulated failure")

    monkeypatch.setattr(review, "accept", failing_accept)
    with pytest.raises(OperationError, match="simulated"):
        decisions_file.apply(demo, write_decisions(tmp_path, "alice", entries), today=day)
    assert snapshot(demo) == before
    assert not (demo / "reviews").exists()


def test_on_main_the_decisions_start_a_review_branch(demo_repository, tmp_path):
    root = demo_repository
    git(root, "branch", "review/2026-11-02-alice")
    # The saved file may sit in the vault folder itself; it is not counted as uncommitted work.
    entries = [
        {
            "issue": "ISS-0001",
            "proposal": 1,
            "decision": "reject",
            "hash": hash_of(root, "ISS-0001", 1),
        }
    ]
    path = write_decisions(root, "alice", entries)
    result = decisions_file.apply(root, path, today=day)
    assert result.started_branch and result.branch == "review/2026-11-02-alice-2"
    assert git(root, "symbolic-ref", "--short", "HEAD").strip() == "review/2026-11-02-alice-2"
    assert git(root, "rev-parse", "main") == git(root, "rev-parse", "HEAD")
    assert "issues/ISS-0001.yaml" in git(root, "status", "--porcelain")


def test_on_main_with_uncommitted_changes_nothing_is_applied(demo_repository, tmp_path):
    root = demo_repository

    def reword(data):
        data["notes"]["en"] = "Unfinished edit."

    edit_yaml(requirement_file(root, "INS-DET-REQ-001"), reword)
    entries = [
        {
            "issue": "ISS-0001",
            "proposal": 1,
            "decision": "reject",
            "hash": hash_of(root, "ISS-0001", 1),
        }
    ]
    with pytest.raises(OperationError, match="uncommitted changes"):
        decisions_file.apply(root, write_decisions(tmp_path, "alice", entries), today=day)
    assert git(root, "symbolic-ref", "--short", "HEAD").strip() == "main"
    assert load(root).records["ISS-0001"].proposals[0].status == "proposed"


def test_malformed_files_are_refused(demo, tmp_path):
    path = tmp_path / "decisions.yaml"
    path.write_text("format: qingsong-decisions/1\nproject: DEMO\ndecided_by: alice\n")
    with pytest.raises(OperationError, match="not a decisions file"):
        decisions_file.apply(demo, path, today=day)
    path.write_text(decisions_yaml("alice", []).replace("decisions:\n", "decisions: []\n"))
    with pytest.raises(OperationError, match="not a decisions file"):
        decisions_file.apply(demo, path, today=day)


def test_the_command_applies_a_file(demo, tmp_path):
    from typer.testing import CliRunner

    from qingsong.cli import app

    entries = [
        {
            "issue": "ISS-0001",
            "proposal": 1,
            "decision": "accept",
            "hash": hash_of(demo, "ISS-0001", 1),
        }
    ]
    path = write_decisions(tmp_path, "alice", entries)
    result = CliRunner().invoke(app, ["issue", "apply", str(path), "--vault", str(demo)])
    assert result.exit_code == 0, result.output
    assert "applied 1 decision by alice" in result.output
    assert "accepted ISS-0001 proposal 1: INS-DET-REQ-001 at revision" in result.output
    assert "kept the file as reviews/" in result.output
    again = CliRunner().invoke(app, ["issue", "apply", str(path), "--vault", str(demo)])
    assert again.exit_code != 0 and "nothing applied" in again.output


def test_the_review_page_carries_each_proposal_hash(demo, tmp_path):
    from qingsong.render.html import render_site

    site = render_site(load(demo), tmp_path / "site").parent
    page = (site / "review.html").read_text()
    assert f'data-key="ISS-0001#1" data-hash="{hash_of(demo, "ISS-0001", 1)}"' in page
    assert 'id="save-decisions"' in page and "qingsong issue apply" in page
    script = (site / "static" / "review.js").read_text()
    assert "format: qingsong-decisions/1" in script and "proposal_hash: " in script


def baselined(root: Path, record_id: str) -> None:
    from qingsong.operations import load_round_trip, stamped, write_atomically

    path = requirement_file(root, record_id)
    data = load_round_trip(path)
    data["maturity"] = "baselined"
    write_atomically(path, stamped(data)[1])


def test_accepts_that_change_the_same_field_are_refused_before_writing(demo, tmp_path):
    second_proposal(demo)
    review.raise_issue(
        demo, "question", {"en": "Note"}, {"en": "The note."}, ["INS-DET-REQ-001"], "bob", today=day
    )
    change = {"record": "INS-DET-REQ-001", "field": "notes", "text": {"en": "Another note."}}
    review.propose(demo, "ISS-0002", "bob", {"en": "another note"}, [change], today=day)
    entries = [
        {
            "issue": "ISS-0001",
            "proposal": 2,
            "decision": "accept",
            "hash": hash_of(demo, "ISS-0001", 2),
        },
        {
            "issue": "ISS-0002",
            "proposal": 1,
            "decision": "accept",
            "hash": hash_of(demo, "ISS-0002", 1),
        },
    ]
    before = snapshot(demo)
    with pytest.raises(OperationError, match="nothing applied") as raised:
        decisions_file.apply(demo, write_decisions(tmp_path, "alice", entries), today=day)
    assert "both change INS-DET-REQ-001 notes" in str(raised.value)
    assert snapshot(demo) == before


def test_a_baselined_target_needs_a_decision_record(demo, tmp_path):
    baselined(demo, "INS-DET-REQ-001")
    second_proposal(demo)
    entry = {
        "issue": "ISS-0001",
        "proposal": 2,
        "decision": "accept",
        "hash": hash_of(demo, "ISS-0001", 2),
    }
    with pytest.raises(OperationError, match="nothing applied") as raised:
        decisions_file.apply(demo, write_decisions(tmp_path, "alice", [entry]), today=day)
    assert "INS-DET-REQ-001 is baselined" in str(raised.value)
    path = write_decisions(tmp_path, "alice", [entry])
    path.write_text(path.read_text() + "    decision_record: DEC-0009\n")
    with pytest.raises(OperationError, match="DEC-0009 is not a decision record"):
        decisions_file.apply(demo, path, today=day)
    path.write_text(path.read_text().replace("DEC-0009", "DEC-0001"))
    decisions_file.apply(demo, path, today=day)
    record = load(demo).records["INS-DET-REQ-001"]
    assert record.notes["en"] == "A shorter note." and record.history[-1].decision == "DEC-0001"


def test_unrecorded_changes_in_a_target_are_refused_before_writing(demo, tmp_path):
    second_proposal(demo)

    def touch(data):
        data["rationale"]["en"] = "Edited without recording."

    edit_yaml(requirement_file(demo, "INS-DET-REQ-001"), touch)
    entry = {
        "issue": "ISS-0001",
        "proposal": 2,
        "decision": "accept",
        "hash": hash_of(demo, "ISS-0001", 2),
    }
    with pytest.raises(OperationError, match="nothing applied") as raised:
        decisions_file.apply(demo, write_decisions(tmp_path, "alice", [entry]), today=day)
    assert "INS-DET-REQ-001 has unrecorded changes" in str(raised.value)


def test_the_file_is_kept_byte_for_byte_and_a_chinese_reason_is_chinese(demo, tmp_path):
    entry = {
        "issue": "ISS-0001",
        "proposal": 1,
        "decision": "reject",
        "note": "数值尚未确定",
        "hash": hash_of(demo, "ISS-0001", 1),
    }
    path = tmp_path / "decisions.yaml"
    path.write_bytes(decisions_yaml("alice", [entry]).replace("\n", "\r\n").encode("utf-8"))
    result = decisions_file.apply(demo, path, today=day)
    assert result.kept.read_bytes() == path.read_bytes()
    assert load(demo).records["ISS-0001"].proposals[0].reason == {"zh": "数值尚未确定"}


def test_a_missing_file_is_a_plain_error(demo, tmp_path):
    with pytest.raises(OperationError, match="no decisions file"):
        decisions_file.apply(demo, tmp_path / "missing.yaml", today=day)
    with pytest.raises(OperationError, match="no decisions file"):
        decisions_file.apply(demo, tmp_path, today=day)


def test_a_branch_named_review_is_reported_before_writing(demo_repository, tmp_path):
    root = demo_repository
    git(root, "branch", "review")
    entry = {
        "issue": "ISS-0001",
        "proposal": 1,
        "decision": "reject",
        "hash": hash_of(root, "ISS-0001", 1),
    }
    with pytest.raises(OperationError, match="a branch named review exists"):
        decisions_file.apply(root, write_decisions(tmp_path, "alice", [entry]), today=day)
    assert not (root / "reviews").exists()
