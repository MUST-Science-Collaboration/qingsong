"""Defect classes found in the 2026-11-01 review of version 0.1 stay caught (docs/lessons.md §6)."""

import shutil

from conftest import edit_yaml, git, requirement_file

from qingsong import checks
from qingsong.vault import load


def findings(root, against=None):
    return [(finding.rule, finding.severity) for finding in checks.run(load(root), against=against)]


def test_duplicate_id_is_an_error_not_a_silent_overwrite(demo):
    source = requirement_file(demo, "INS-DET-REQ-001")
    shutil.copy(source, source.with_name("copy.yaml"))
    assert ("integrity.duplicate_id", "error") in findings(demo)


def test_unreadable_file_is_an_error_not_a_skipped_warning(demo):
    requirement_file(demo, "INS-DET-REQ-001").write_text("title: [\n")
    assert ("integrity.yaml_syntax", "error") in findings(demo)


def test_dangling_link_is_an_error(demo):
    edit_yaml(
        requirement_file(demo, "INS-OPT-REQ-001"),
        lambda data: data["derives_from"][0].__setitem__("id", "INS-SYS-REQ-404"),
    )
    assert ("integrity.unresolved_reference", "error") in findings(demo)


def test_deleted_record_is_an_error(demo_repository):
    requirement_file(demo_repository, "INS-DET-REQ-001").unlink()
    assert ("integrity.against", "error") in findings(demo_repository, against="main")


def test_missing_field_is_not_filled_in_by_default(demo):
    edit_yaml(requirement_file(demo, "INS-DET-REQ-001"), lambda data: data.pop("maturity"))
    assert ("integrity.schema", "error") in findings(demo)
    assert "INS-DET-REQ-001" not in load(demo).records


def test_bidirectional_reference_is_not_a_cycle(demo):
    edit_yaml(
        requirement_file(demo, "INS-DET-REQ-001"),
        lambda data: data["rationale"].__setitem__("en", "See also [[INS-OPT-REQ-001]]."),
    )
    edit_yaml(
        requirement_file(demo, "INS-OPT-REQ-001"),
        lambda data: data["rationale"].__setitem__("en", "See also [[INS-DET-REQ-001]]."),
    )
    assert not [rule for rule, _ in findings(demo) if rule == "structure.cycle"]


def test_checks_never_write_to_the_vault(demo_repository):
    checks.run(load(demo_repository), against="main")
    assert git(demo_repository, "status", "--porcelain") == ""


def test_unknown_text_origin_is_a_finding_not_a_crash(demo):
    edit_yaml(
        requirement_file(demo, "INS-DET-REQ-001"),
        lambda data: data.__setitem__("text_origin", "fr"),
    )
    assert ("content.languages", "error") in findings(demo)


def test_empty_statement_is_an_error(demo):
    edit_yaml(
        requirement_file(demo, "INS-DET-REQ-001"), lambda data: data.__setitem__("statement", {})
    )
    assert ("content.languages", "error") in findings(demo)


def test_open_values_next_to_chinese_and_no_false_alarms(demo):
    def change(data):
        data["statement"]["zh"] = "巡天应测量红移，数量为TBD。"
        data["statement"]["en"] = (
            "The survey shall measure redshifts ($z_{max}$, see [Table 2](t.md))."
        )

    edit_yaml(requirement_file(demo, "DEMO-SCI-REQ-001"), change)
    found = [f for f in checks.run(load(demo)) if f.record == "DEMO-SCI-REQ-001"]
    assert any(f.rule == "content.open_values" and "TBD" in f.message for f in found)
    assert not any(f.rule == "content.values" for f in found)


def test_long_text_with_repeated_spaces_survives_writing(demo):
    from qingsong import operations

    def change(data):
        data["rationale"]["en"] = "word " * 40 + "two  spaces   three    four" + " word" * 40

    edit_yaml(requirement_file(demo, "DEMO-SCI-REQ-001"), change)
    operations.revise(demo, "DEMO-SCI-REQ-001", "editorial", "long rationale", "alice")
    assert ("change.unrecorded", "error") not in findings(demo)
