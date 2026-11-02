"""Recorded changes (docs/SPEC.md §6, §8, §9)."""

import datetime

import pytest
from conftest import edit_yaml, git, requirement_file

from qingsong import checks, operations
from qingsong.operations import OperationError
from qingsong.vault import load

day = datetime.date(2026, 11, 2)
commit = ("-c", "user.name=T", "-c", "user.email=t@example.org", "commit", "-q")


def rules_fired(root, against=None):
    return {
        finding.rule
        for finding in checks.run(load(root), against=against)
        if finding.severity in ("error", "warning")
    }


def raise_sn(root, value=6):
    edit_yaml(
        requirement_file(root, "DEMO-SRV-REQ-001"),
        lambda data: data["values"]["sn"].__setitem__("value", value),
    )


def test_new_requirement_takes_the_next_number(demo):
    record = operations.new_requirement(
        demo, "INS-DET", "Gain", "The gain shall be stable.", "alice"
    )
    assert record.id == "INS-DET-REQ-002"
    assert record.maturity == "concept" and record.level == "subsystem"
    assert record.allocated_to == "INS-DET"
    assert rules_fired(demo) <= {"structure.justification"}


def test_new_requirement_counts_numbers_on_main(demo_repository):
    root = demo_repository
    git(root, "checkout", "-q", "-b", "work")
    git(root, "checkout", "-q", "main")
    operations.new_requirement(root, "INS-DET", "Gain", "The gain shall be stable.", "alice")
    git(root, "add", "-A")
    git(root, *commit, "-m", "add 002 on main")
    git(root, "checkout", "-q", "work")
    record = operations.new_requirement(
        root, "INS-DET", "Bias", "The bias shall be stable.", "alice"
    )
    assert record.id == "INS-DET-REQ-003"


def test_text_origin_follows_the_node(demo):
    record = operations.new_requirement(
        demo, "INS-OPT", "Ghosts", "Ghost images shall be faint.", "alice"
    )
    assert record.text_origin == "zh"


def test_editorial_class_refuses_a_value_change(demo):
    raise_sn(demo)
    with pytest.raises(OperationError, match="'value' change"):
        operations.revise(demo, "DEMO-SRV-REQ-001", "editorial", "typo", "alice", today=day)


def test_value_change_makes_children_suspect_until_confirmed(demo):
    raise_sn(demo)
    record = operations.revise(
        demo, "DEMO-SRV-REQ-001", "value", "raise the S/N target", "alice", today=day
    )
    assert record.normative_revision == 2 and record.revision == 2
    findings = checks.run(load(demo))
    suspect = {
        finding.record: finding.severity
        for finding in findings
        if finding.rule == "change.suspect_link"
    }
    assert suspect == {
        "DEMO-SYS-REQ-001": "warning",
        "INS-SYS-REQ-001": "error",
        "INS-DET-REQ-001": "warning",
    }
    for child in suspect:
        operations.confirm(demo, child, "DEMO-SRV-REQ-001", "alice", today=day)
    assert "change.suspect_link" not in rules_fired(demo)


def test_wording_change_is_editorial_and_leaves_children_alone(demo):
    def reword(data):
        data["statement"]["en"] = data["statement"]["en"].replace("faintest", "dimmest")

    edit_yaml(requirement_file(demo, "DEMO-SRV-REQ-001"), reword)
    operations.revise(demo, "DEMO-SRV-REQ-001", "editorial", "wording", "alice", today=day)
    fired = rules_fired(demo)
    assert "change.suspect_link" not in fired
    assert "change.translation" in fired


def test_nothing_to_record(demo):
    with pytest.raises(OperationError, match="nothing changed"):
        operations.revise(demo, "DEMO-SRV-REQ-001", "editorial", "no change", "alice", today=day)


def test_translation_refresh_marks_review(demo):
    def change(data):
        data["statement"]["en"] = data["statement"]["en"].replace("faintest", "dimmest")
        data["statement"]["zh"] = data["statement"]["zh"].replace("最暗", "最暗弱")

    edit_yaml(requirement_file(demo, "DEMO-SRV-REQ-001"), change)
    record = operations.revise(
        demo,
        "DEMO-SRV-REQ-001",
        "editorial",
        "wording in both languages",
        "alice",
        translation="reviewed",
        today=day,
    )
    assert record.translation["statement"].status == "reviewed"
    assert rules_fired(demo) == set()


def test_only_approvers_approve(demo):
    with pytest.raises(OperationError, match="not an approver"):
        operations.approve(demo, "INS-DET-REQ-001", "agreed", "bob", "demo#2", today=day)
    record = operations.approve(demo, "INS-DET-REQ-001", "agreed", "alice", "demo#2", today=day)
    assert record.maturity == "agreed" and record.approval.normative_revision == 1


def test_value_change_makes_approval_stale(demo):
    edit_yaml(
        requirement_file(demo, "INS-SYS-REQ-001"),
        lambda data: data["values"]["throughput"].__setitem__("value", 45),
    )
    with pytest.raises(OperationError, match="states the reason"):
        operations.revise(demo, "INS-SYS-REQ-001", "value", "raise", "alice", today=day)
    operations.revise(
        demo,
        "INS-SYS-REQ-001",
        "value",
        "raise throughput after the trade study",
        "alice",
        today=day,
    )
    assert "change.approval" in rules_fired(demo)
    operations.approve(demo, "INS-SYS-REQ-001", "agreed", "alice", "demo#3", today=day)
    assert "change.approval" not in rules_fired(demo)


def test_supersede_and_withdraw(demo):
    successor = operations.new_requirement(
        demo,
        "INS-DET",
        "Read noise (fast mode)",
        "The read noise shall be low in fast mode.",
        "alice",
    )
    record = operations.supersede(
        demo, "INS-DET-REQ-001", [successor.id], "split by readout mode", "alice", today=day
    )
    assert record.lifecycle == "superseded" and record.superseded_by == [successor.id]
    with pytest.raises(OperationError, match="it can no longer be changed"):
        operations.withdraw(demo, "INS-DET-REQ-001", "obsolete", "alice", today=day)
    with pytest.raises(OperationError, match="needs --decision"):
        operations.withdraw(demo, "INS-SYS-REQ-001", "obsolete", "alice", today=day)
    record = operations.withdraw(
        demo, "INS-SYS-REQ-001", "obsolete", "alice", decision="DEC-0001", today=day
    )
    assert record.lifecycle == "withdrawn"
    assert "structure.lifecycle" in rules_fired(demo)


def test_renumber_only_before_main(demo_repository):
    root = demo_repository
    git(root, "checkout", "-q", "-b", "work")
    with pytest.raises(OperationError, match="permanent"):
        operations.renumber(root, "INS-DET-REQ-001", "INS-DET-REQ-005", "alice", today=day)
    record = operations.new_requirement(
        root, "INS-DET", "Gain", "The gain shall be stable.", "alice"
    )
    edit_yaml(
        requirement_file(root, "INS-OPT-REQ-001"),
        lambda data: data["rationale"].__setitem__("en", f"See [[{record.id}]]."),
    )
    operations.revise(root, "INS-OPT-REQ-001", "editorial", "cross-reference", "alice", today=day)
    renumbered = operations.renumber(root, record.id, "INS-DET-REQ-007", "alice", today=day)
    assert renumbered.id == "INS-DET-REQ-007"
    assert "[[INS-DET-REQ-007]]" in requirement_file(root, "INS-OPT-REQ-001").read_text()
    assert not requirement_file(root, record.id).exists()
    assert rules_fired(root) <= {"structure.justification", "change.translation"}


def test_adopt_refuses_wrong_place_and_stamped_files(demo):
    path = demo / "requirements" / "INS" / "INS-DET-REQ-004.yaml"
    path.write_text(
        requirement_file(demo, "INS-DET-REQ-001")
        .read_text()
        .replace("INS-DET-REQ-001", "INS-DET-REQ-004")
    )
    with pytest.raises(OperationError, match="already has"):
        operations.adopt(demo, path, "alice", "copy")
    wrong = demo / "requirements" / "DEMO" / "INS-DET-REQ-005.yaml"
    wrong.write_text("id: INS-DET-REQ-005\ntype: requirement\n")
    with pytest.raises(OperationError, match="must be stored at"):
        operations.adopt(demo, wrong, "alice", "misplaced")


def test_unknown_person_is_refused(demo):
    with pytest.raises(OperationError, match="not listed"):
        operations.new_requirement(demo, "INS-DET", "Gain", "The gain shall be stable.", "mallory")


def test_against_detects_history_rewrite_and_reversal(demo_repository):
    root = demo_repository
    edit_yaml(
        requirement_file(root, "INS-DET-REQ-001"),
        lambda data: data["history"][0].__setitem__("summary", "rewritten"),
    )
    edit_yaml(
        requirement_file(root, "INS-OPT-REQ-001"),
        lambda data: data.__setitem__("lifecycle", "current"),
    )
    messages = [
        finding.message
        for finding in checks.run(load(root), against="main")
        if finding.rule == "integrity.against"
    ]
    assert any("history entries" in message for message in messages)


def test_against_detects_removed_node(demo_repository):
    root = demo_repository
    path = root / "tree" / "INS.yaml"
    path.write_text(
        path.read_text().replace(
            "  - node: AIT\n    structural_code: IN.09\n"
            '    names: {en: "Integration and test", zh: "集成与测试"}\n'
            "    kind: work\n    status: active\n",
            "",
        )
    )
    messages = [
        finding.message
        for finding in checks.run(load(root), against="main")
        if finding.rule == "integrity.against"
    ]
    assert any("INS-AIT" in message for message in messages)


def test_other_operations_refuse_unrecorded_edits(demo):
    edit_yaml(
        requirement_file(demo, "INS-DET-REQ-001"),
        lambda data: data["values"]["read_noise"].__setitem__("value", 30),
    )
    with pytest.raises(OperationError, match="unrecorded changes"):
        operations.confirm(demo, "INS-DET-REQ-001", "DEMO-SRV-REQ-001", "alice", today=day)
    with pytest.raises(OperationError, match="unrecorded changes"):
        operations.withdraw(demo, "INS-DET-REQ-001", "obsolete", "alice", today=day)


def test_new_never_overwrites_a_file_that_does_not_load(demo):
    broken = requirement_file(demo, "INS-DET-REQ-002")
    broken.write_text("id: INS-DET-REQ-002\nrevision: x\n")
    record = operations.new_requirement(
        demo, "INS-DET", "Gain", "The gain shall be stable.", "alice"
    )
    assert record.id == "INS-DET-REQ-003"
    assert broken.read_text() == "id: INS-DET-REQ-002\nrevision: x\n"


def test_new_writes_the_text_in_the_origin_language(demo):
    record = operations.new_requirement(demo, "INS-OPT", "鬼像", "鬼像应足够暗。", "alice")
    assert record.text_origin == "zh" and record.statement == {"zh": "鬼像应足够暗。"}


def test_approval_binds_the_approved_wording(demo):
    def reword(data):
        data["statement"]["en"] = data["statement"]["en"].replace("at least", "no less than")

    edit_yaml(requirement_file(demo, "INS-SYS-REQ-001"), reword)
    operations.revise(
        demo, "INS-SYS-REQ-001", "editorial", "clearer wording of the limit", "alice", today=day
    )
    messages = [f.message for f in checks.run(load(demo)) if f.rule == "change.approval"]
    assert any("approved wording" in message for message in messages)


def test_against_catches_a_value_change_without_a_normative_revision(demo_repository):
    root = demo_repository
    path = requirement_file(root, "INS-DET-REQ-001")
    data = operations.load_round_trip(path)
    data["values"]["read_noise"]["value"] = 30
    _record, text = operations.stamped(data)
    path.write_text(text)
    messages = [
        f.message for f in checks.run(load(root), against="main") if f.rule == "integrity.against"
    ]
    assert any("normative revision did not change" in message for message in messages)


def test_renumber_rewrites_verification_ids_and_keeps_translations(demo_repository):
    root = demo_repository
    git(root, "checkout", "-q", "-b", "work")
    record = operations.new_requirement(
        root, "INS-DET", "Gain", "The gain shall be stable.", "alice"
    )
    folder = root / "verifications"
    folder.mkdir()
    verification = folder / f"VER-{record.id}-01.yaml"
    verification.write_text(
        f"id: VER-{record.id}-01\ntype: verification\ntitle: {{en: Gain test}}\n"
        f"requirement: {record.id}\nrequirement_normative_revision: 1\nmethods: [test]\n",
        encoding="utf-8",
    )
    verification.write_text(
        verification.read_text().replace("methods: [test]", "method: test\nstatus: planned")
    )
    operations.adopt(root, verification, "alice", "plan")
    edit_yaml(
        requirement_file(root, "INS-OPT-REQ-001"),
        lambda data: data["rationale"].__setitem__("zh", f"见[[{record.id}]]。"),
    )
    operations.revise(
        root,
        "INS-OPT-REQ-001",
        "editorial",
        "cross-reference",
        "alice",
        translation="reviewed",
        today=day,
    )
    operations.renumber(root, record.id, "INS-DET-REQ-007", "alice", today=day)
    assert (folder / "VER-INS-DET-REQ-007-01.yaml").exists()
    assert not verification.exists()
    fired = rules_fired(root)
    assert "change.translation" not in fired and "integrity.id_syntax" not in fired


def test_missing_git_does_not_crash(demo, monkeypatch):
    monkeypatch.setenv("PATH", "")
    record = operations.new_requirement(
        demo, "INS-DET", "Gain", "The gain shall be stable.", "alice"
    )
    assert record.id == "INS-DET-REQ-002"
    findings = checks.run(load(demo), against="main")
    assert any(f.rule == "integrity.against" and "not found" in f.message for f in findings)
