"""Every check rule has a fixture that triggers it (docs/SPEC.md §10, §13)."""

import datetime
import shutil
from pathlib import Path

import pytest
from conftest import edit_yaml, git, requirement_file

from qingsong import checks, operations
from qingsong.vault import load


def run(root: Path, against: str | None = None):
    return checks.run(load(root), against=against)


def set_field(record_id: str, key: str, value):
    def change(root: Path) -> None:
        edit_yaml(requirement_file(root, record_id), lambda data: data.__setitem__(key, value))

    return change


def broken_config(root: Path) -> None:
    (root / "qingsong.toml").write_text("[project\ncode = ", encoding="utf-8")


def broken_yaml(root: Path) -> None:
    requirement_file(root, "INS-DET-REQ-001").write_text("id: [unclosed\n", encoding="utf-8")


def unknown_field(root: Path) -> None:
    set_field("INS-DET-REQ-001", "colour", "red")(root)


def missing_glossary(root: Path) -> None:
    (root / "glossary.yaml").unlink()


def misplaced_file(root: Path) -> None:
    source = requirement_file(root, "INS-DET-REQ-001")
    shutil.move(source, root / "requirements" / "DEMO" / source.name)


def duplicate_id(root: Path) -> None:
    source = requirement_file(root, "INS-DET-REQ-001")
    shutil.copy(source, source.with_name("INS-DET-REQ-009.yaml"))


def bad_id(root: Path) -> None:
    set_field("INS-DET-REQ-001", "id", "INS-DET-RQ-001")(root)


def dangling_link(root: Path) -> None:
    set_field(
        "INS-DET-REQ-001", "derives_from", [{"id": "INS-SYS-REQ-099", "normative_revision": 1}]
    )(root)


def changed_image(root: Path) -> None:
    (root / "figures" / "INS" / "INS-DET-FIG-001.png").write_bytes(b"not the recorded image")


def removed_since_reference(root: Path) -> str:
    git(root, "init", "-q", "-b", "main")
    git(root, "-c", "user.name=T", "-c", "user.email=t@example.org", "add", "-A")
    git(root, "-c", "user.name=T", "-c", "user.email=t@example.org", "commit", "-q", "-m", "base")
    requirement_file(root, "INS-OPT-REQ-001").unlink()
    return "main"


def second_root(root: Path) -> None:
    (root / "tree" / "XTRA.yaml").write_text(
        "node: XTRA\nnames: {en: X}\nkind: product\nstatus: active\n"
    )


def wrong_parent(root: Path) -> None:
    (root / "tree" / "XTRA.yaml").write_text(
        "parent: INS\nnode: XTRA\nnames: {en: X}\nkind: product\nstatus: active\n"
    )


def reserved_code(root: Path) -> None:
    path = root / "tree" / "INS.yaml"
    path.write_text(path.read_text().replace("node: OPT", "node: REQ"))


def work_allocation(root: Path) -> None:
    set_field("INS-DET-REQ-001", "allocated_to", "INS-AIT")(root)


def unknown_namespace(root: Path) -> None:
    source = requirement_file(root, "INS-DET-REQ-001")
    target = root / "requirements" / "XYZ" / "XYZ-ABC-REQ-001.yaml"
    target.parent.mkdir()
    target.write_text(source.read_text().replace("INS-DET-REQ-001", "XYZ-ABC-REQ-001"))


def level_upside_down(root: Path) -> None:
    set_field("INS-OPT-REQ-001", "level", "science")(root)


def parentless(root: Path) -> None:
    set_field("INS-DET-REQ-001", "derives_from", [])(root)


def cycle(root: Path) -> None:
    set_field(
        "DEMO-SCI-REQ-001", "derives_from", [{"id": "INS-DET-REQ-001", "normative_revision": 1}]
    )(root)


def superseded_without_successor(root: Path) -> None:
    set_field("DEMO-SRV-REQ-001", "lifecycle", "superseded")(root)


def alias_equal_to_id(root: Path) -> None:
    set_field(
        "INS-DET-REQ-001", "aliases", [{"id": "INS-SYS-REQ-001", "kind": "legacy", "document": "X"}]
    )(root)


def condition_on_product(root: Path) -> None:
    edit_yaml(
        root / "conditions" / "SITE-COND-001.yaml", lambda data: data.__setitem__("node", "INS")
    )


def hand_edit(root: Path) -> None:
    def change(data):
        data["statement"]["en"] = data["statement"]["en"].replace("detector", "sensor")

    edit_yaml(requirement_file(root, "INS-DET-REQ-001"), change)


def history_gap(root: Path) -> None:
    set_field("INS-DET-REQ-001", "revision", 3)(root)


def parent_value_change(root: Path) -> None:
    edit_yaml(
        requirement_file(root, "DEMO-SRV-REQ-001"),
        lambda data: data["values"]["sn"].__setitem__("value", 6),
    )
    operations.revise(
        root,
        "DEMO-SRV-REQ-001",
        "value",
        "raise the S/N target",
        "alice",
        today=datetime.date(2026, 11, 2),
    )


def unauthorized_approval(root: Path) -> None:
    edit_yaml(
        requirement_file(root, "INS-SYS-REQ-001"),
        lambda data: data["approval"].__setitem__("by", "bob"),
    )


def stale_translation(root: Path) -> None:
    def change(data):
        data["statement"]["zh"] = data["statement"]["zh"] + "（修改）"

    edit_yaml(requirement_file(root, "INS-OPT-REQ-001"), change)


def stale_verification(root: Path) -> None:
    folder = root / "verifications"
    folder.mkdir()
    (folder / "VER-INS-DET-REQ-001-01.yaml").write_text(
        "id: VER-INS-DET-REQ-001-01\ntype: verification\ntitle: {en: Read noise test}\n"
        "requirement: INS-DET-REQ-001\nrequirement_normative_revision: 2\nmethod: test\nstatus: planned\n",
        encoding="utf-8",
    )
    operations.adopt(root, folder / "VER-INS-DET-REQ-001-01.yaml", "alice", "test fixture")


def unknown_language(root: Path) -> None:
    edit_yaml(
        requirement_file(root, "INS-DET-REQ-001"),
        lambda data: data["title"].__setitem__("fr", "Bruit"),
    )


def missing_chinese(root: Path) -> None:
    edit_yaml(requirement_file(root, "DEMO-SCI-REQ-001"), lambda data: data["statement"].pop("zh"))


def two_shalls(root: Path) -> None:
    def change(data):
        data["statement"]["en"] = "The survey shall be adequate and shall be fast."

    edit_yaml(requirement_file(root, "DEMO-SCI-REQ-001"), change)


def untracked_open_value(root: Path) -> None:
    def change(data):
        data["statement"]["en"] = "The survey shall measure [1,000,000] redshifts."

    edit_yaml(requirement_file(root, "DEMO-SCI-REQ-001"), change)


def wrong_unit(root: Path) -> None:
    edit_yaml(
        requirement_file(root, "INS-DET-REQ-001"),
        lambda data: data["values"]["read_noise"].__setitem__("unit", "meter"),
    )


def missing_rationale(root: Path) -> None:
    edit_yaml(requirement_file(root, "DEMO-SCI-REQ-001"), lambda data: data.pop("rationale"))


def malformed_reference(root: Path) -> None:
    edit_yaml(
        requirement_file(root, "INS-DET-REQ-001"),
        lambda data: data["rationale"].__setitem__("en", "See [[ INS-SYS-REQ-001 ]]."),
    )


def compliant_without_evidence(root: Path) -> None:
    folder = root / "verifications"
    folder.mkdir()
    (folder / "VER-INS-DET-REQ-001-01.yaml").write_text(
        "id: VER-INS-DET-REQ-001-01\ntype: verification\ntitle: {en: Read noise test}\n"
        "requirement: INS-DET-REQ-001\nrequirement_normative_revision: 1\nmethod: test\n"
        "status: compliant\n",
        encoding="utf-8",
    )
    operations.adopt(root, folder / "VER-INS-DET-REQ-001-01.yaml", "alice", "test fixture")


def figure_placed_twice(root: Path) -> None:
    def change(data):
        data["outline"][1]["section"]["blocks"].append({"figure": "INS-DET-FIG-001"})

    edit_yaml(root / "documents" / "DEMO-INS-DET-RD.yaml", change)


def unknown_rule_in_issue(root: Path) -> None:
    edit_yaml(
        root / "issues" / "ISS-0001.yaml", lambda data: data.__setitem__("rule", "content.colour")
    )


def stale_proposal(root: Path) -> None:
    from qingsong import review

    day = datetime.date(2026, 11, 2)
    change = {"record": "INS-DET-REQ-001", "field": "rationale", "text": {"en": "New reason."}}
    review.propose(root, "ISS-0001", "bob", {"en": "reword"}, [change], today=day)

    def reword(data):
        data["rationale"]["en"] = "The rationale was edited after the proposal."

    edit_yaml(requirement_file(root, "INS-DET-REQ-001"), reword)
    operations.revise(root, "INS-DET-REQ-001", "editorial", "reworded", "alice", today=day)


cases = {
    "integrity.proposal": unknown_rule_in_issue,
    "change.stale_proposal": stale_proposal,
    "structure.outline": figure_placed_twice,
    "content.references": malformed_reference,
    "content.evidence": compliant_without_evidence,
    "integrity.config": broken_config,
    "integrity.yaml_syntax": broken_yaml,
    "integrity.schema": unknown_field,
    "integrity.missing_file": missing_glossary,
    "integrity.path_mismatch": misplaced_file,
    "integrity.duplicate_id": duplicate_id,
    "integrity.id_syntax": bad_id,
    "integrity.unresolved_reference": dangling_link,
    "integrity.figure_file": changed_image,
    "integrity.against": removed_since_reference,
    "structure.tree_root": second_root,
    "structure.tree_parent": wrong_parent,
    "structure.node_code": reserved_code,
    "structure.allocation": work_allocation,
    "structure.namespace": unknown_namespace,
    "structure.level": level_upside_down,
    "structure.justification": parentless,
    "structure.cycle": cycle,
    "structure.lifecycle": superseded_without_successor,
    "structure.alias": alias_equal_to_id,
    "structure.ends": condition_on_product,
    "change.unrecorded": hand_edit,
    "change.history": history_gap,
    "change.suspect_link": parent_value_change,
    "change.approval": unauthorized_approval,
    "change.translation": stale_translation,
    "change.stale_evidence": stale_verification,
    "content.languages": unknown_language,
    "content.bilingual": missing_chinese,
    "content.writing": two_shalls,
    "content.open_values": untracked_open_value,
    "content.values": wrong_unit,
    "content.completeness": missing_rationale,
}


def test_clean_demo_has_no_findings(demo):
    assert run(demo) == []


def test_every_rule_has_a_fixture():
    assert set(checks.all_rule_summaries()) == set(cases)


@pytest.mark.parametrize("rule_id", sorted(cases))
def test_fixture_triggers_rule(demo, rule_id):
    against = cases[rule_id](demo)
    findings = run(demo, against=against if isinstance(against, str) else None)
    hits = [finding for finding in findings if finding.rule == rule_id]
    assert hits, f"{rule_id} did not fire; findings: {[f.rule for f in findings]}"
    assert any(finding.severity in ("error", "warning") for finding in hits)


def test_committed_demo_matches_its_sources(built_demo):
    committed = Path(__file__).resolve().parents[1] / "examples" / "demo"
    built_files = {
        path.relative_to(built_demo): path.read_bytes()
        for path in built_demo.rglob("*")
        if path.is_file()
    }
    committed_files = {
        path.relative_to(committed): path.read_bytes()
        for path in committed.rglob("*")
        if path.is_file()
    }
    assert built_files == committed_files, "run: uv run python examples/build_demo.py"
