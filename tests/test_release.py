"""Releases, change summaries and the consistency intervals (docs/SPEC.md §5.5, §10)."""

import datetime
import math

import pytest
from conftest import edit_yaml, git, requirement_file

from qingsong import checks, gitutil, operations, release
from qingsong.checks.consistency import Interval, allowed
from qingsong.operations import OperationError
from qingsong.schema import Quantity, ValueSlot
from qingsong.vault import load, vault_at

document_id = "DEMO-INS-DET-RD"
day = datetime.date(2026, 11, 2)
author = ["-c", "user.name=T", "-c", "user.email=t@example.org"]


def commit_all(root, message: str) -> str:
    git(root, *author, "add", "-A")
    git(root, *author, "commit", "-q", "-m", message)
    return git(root, "rev-parse", "HEAD").strip()


def reword_rationale(root, english: str, chinese: str) -> None:
    def change(data):
        data["rationale"]["en"] = english
        data["rationale"]["zh"] = chinese

    edit_yaml(requirement_file(root, "INS-DET-REQ-001"), change)
    operations.revise(
        root,
        "INS-DET-REQ-001",
        "editorial",
        "rationale reworded for clarity",
        "alice",
        translation="reviewed",
        today=day,
    )


def summary() -> dict[str, str]:
    return {"en": "Rationale reworded", "zh": "修改理由"}


def quantity(unit: str) -> Quantity:
    return Quantity.model_validate(
        {
            "id": "test.length",
            "type": "quantity",
            "title": {"en": "Length"},
            "lifecycle": "current",
            "revision": 1,
            "normative_revision": 1,
            "normative_hash": "0" * 16,
            "history": [],
            "stamp": "0" * 16,
            "dimension": "[length]",
            "unit": unit,
        }
    )


def slot(**fields) -> ValueSlot:
    return ValueSlot.model_validate({"certainty": "firm", **fields})


def test_open_and_closed_ends():
    meter = quantity("m")
    below = allowed(slot(relation="lt", value=3, unit="m"), meter)
    from_three = allowed(slot(relation="ge", value=3, unit="m"), meter)
    up_to_three = allowed(slot(relation="le", value=3, unit="m"), meter)
    assert below.intersection(from_three) is None
    assert up_to_three.intersection(from_three) == Interval(3, 3)


def test_units_and_tolerances_convert():
    meter = quantity("m")
    in_millimetres = allowed(slot(relation="le", value=3, unit="mm"), meter)
    assert in_millimetres.within(Interval(-math.inf, 0.003))
    toleranced = allowed(
        slot(relation="eq", value=140, unit="um", tolerance={"plus": 2, "minus": 2}), meter
    )
    assert math.isclose(toleranced.low, 138e-6) and math.isclose(toleranced.high, 142e-6)
    assert allowed(slot(relation="approx", value=1, unit="m"), meter) is None
    assert allowed(slot(relation="le", certainty="tbd"), meter) is None
    assert allowed(slot(relation="le", value=1), meter) is None


def test_offset_units_convert_by_their_ends():
    kelvin = Quantity.model_validate(
        {**quantity("K").model_dump(), "dimension": "[temperature]", "unit": "K"}
    )
    interval = allowed(slot(relation="range", minimum=-10, maximum=20, unit="degC"), kelvin)
    assert math.isclose(interval.low, 263.15) and math.isclose(interval.high, 293.15)


def test_environmental_child_must_cover_its_parent(demo):
    def mark(data):
        data["environmental"] = True

    edit_yaml(demo / "quantities" / "environment.temperature.yaml", mark)
    narrow = {"quantity": "environment.temperature", "relation": "range", "minimum": 0}
    narrow.update({"maximum": 5, "unit": "degC", "certainty": "firm"})

    def add(data):
        data["values"]["operating"] = narrow
        data["derives_from"] = [{"id": "DEMO-SYS-REQ-001", "normative_revision": 1}]

    edit_yaml(requirement_file(demo, "INS-SYS-REQ-001"), add)
    hits = [f for f in checks.run(load(demo)) if f.rule == "consistency.child_looser"]
    assert hits and "must cover" in hits[0].message


def test_unrelated_nodes_do_not_conflict(demo):
    conflicting = {"quantity": "detector.read_noise", "relation": "ge", "value": 5}
    conflicting.update({"unit": "count", "certainty": "firm"})

    def add(data):
        data["values"]["noise"] = conflicting

    edit_yaml(requirement_file(demo, "INS-OPT-REQ-001"), add)
    assert not [f for f in checks.run(load(demo)) if f.rule == "consistency.conflict"]


def test_prepare_refuses_with_reasons(demo_repository):
    root = demo_repository
    with pytest.raises(OperationError, match="not an approver"):
        release.prepare(root, document_id, "1.1", "bob", summary(), today=day)
    with pytest.raises(OperationError, match="released before qingsong"):
        release.prepare(root, document_id, "1.0", "alice", summary(), today=day)
    with pytest.raises(OperationError, match="higher than"):
        release.prepare(root, document_id, "0.9", "alice", summary(), today=day)
    with pytest.raises(OperationError, match="in zh"):
        release.prepare(root, document_id, "1.1", "alice", {"en": "x"}, today=day)

    def machine(data):
        data["rationale"]["en"] = "Changed without reviewing the Chinese."

    edit_yaml(requirement_file(root, "INS-DET-REQ-001"), machine)
    operations.revise(root, "INS-DET-REQ-001", "editorial", "edited", "alice", today=day)
    with pytest.raises(OperationError, match="translation of rationale is not reviewed"):
        release.prepare(root, document_id, "1.1", "alice", summary(), today=day)


def test_release_flow_with_squash_merge(demo_repository):
    root = demo_repository
    first = git(root, "rev-parse", "HEAD").strip()
    assert release.tag_release(root, document_id, "1.0", at="HEAD") == (
        "release/DEMO-INS-DET-RD/1.0",
        first,
    )

    git(root, "checkout", "-q", "-b", "release-1.1")
    reword_rationale(root, "Keeps faint spectra sky-limited.", "使暗弱光谱处于天光限。")
    record = release.prepare(root, document_id, "1.1", "alice", summary(), today=day)
    entry = record.releases[-1]
    assert entry.tag == "release/DEMO-INS-DET-RD/1.1" and entry.made_with_qingsong
    assert record.history[-1].event == "released"
    again = release.prepare(root, document_id, "1.1", "alice", summary(), today=day)
    assert [item.version for item in again.releases] == ["1.0", "1.1"]
    commit_all(root, "prepare 1.1")
    with pytest.raises(OperationError, match="not on the main branch"):
        release.tag_release(root, document_id, "1.1")

    git(root, "checkout", "-q", "main")
    git(root, "merge", "-q", "--squash", "release-1.1")
    squashed = commit_all(root, "release 1.1 (squash)")
    with pytest.raises(OperationError, match="already on the main branch"):
        release.prepare(root, document_id, "1.1", "alice", summary(), today=day)
    edit_yaml(
        requirement_file(root, "INS-OPT-REQ-001"),
        lambda data: (
            data["notes"].__setitem__("en", "Later.")
            if data.get("notes")
            else data.__setitem__("notes", {"en": "Later.", "zh": "以后。"})
        ),
    )
    operations.revise(root, "INS-OPT-REQ-001", "editorial", "a later change", "alice", today=day)
    later = commit_all(root, "a later change")
    assert later != squashed

    tag, commit = release.tag_release(root, document_id, "1.1")
    assert commit == squashed
    assert gitutil.commit_of(root, tag) == squashed
    with pytest.raises(OperationError, match="already exists"):
        release.tag_release(root, document_id, "1.1")
    assert not [
        f
        for f in checks.run(load(root))
        if f.rule.startswith("documents.") and f.severity != "info"
    ]

    summary_since = release.changes(root, document_id, since="1.0", until=tag)
    assert summary_since.approximate
    revised = {change.record: change for change in summary_since.revised}
    assert set(revised) == {"INS-DET-REQ-001"}
    assert revised["INS-DET-REQ-001"].fields == ["rationale"]
    assert [event["event"] for event in revised["INS-DET-REQ-001"].events] == ["revised"]
    assert "front" not in summary_since.front_matter
    exact = release.changes(root, document_id)
    assert not exact.approximate and exact.since == "v1.1"


def test_changes_report_outline_and_sections(demo_repository):
    root = demo_repository
    release.tag_release(root, document_id, "1.0", at="HEAD")

    def restructure(data):
        performance = data["outline"][1]["section"]
        performance["blocks"] = [block for block in performance["blocks"] if "figure" not in block]
        data["outline"][0]["section"]["title"]["en"] = "About this document"

    edit_yaml(root / "documents" / f"{document_id}.yaml", restructure)
    operations.revise(root, document_id, "editorial", "outline changed", "alice", today=day)
    found = release.changes(root, document_id)
    assert found.removed == ["INS-DET-FIG-001"]
    assert [(section.key, section.status) for section in found.sections] == [
        ("introduction", "changed")
    ]
    assert found.lines()[0].startswith(f"{document_id}: changes since v1.0")


def test_release_entries_are_append_only(demo_repository):
    root = demo_repository

    def rewrite(data):
        data["releases"][0]["summary"]["en"] = "Rewritten"

    edit_yaml(root / "documents" / f"{document_id}.yaml", rewrite)
    operations.revise(root, document_id, "editorial", "summary rewritten", "alice", today=day)
    hits = [
        f
        for f in checks.run(load(root), against="main")
        if f.rule == "integrity.against" and "release 1.0" in f.message
    ]
    assert hits


def test_vault_at_reads_the_stored_state(demo_repository):
    root = demo_repository
    edit_yaml(
        requirement_file(root, "INS-DET-REQ-001"),
        lambda data: data["title"].__setitem__("en", "Changed in the working tree"),
    )
    with vault_at(root, "HEAD") as earlier:
        assert earlier.records["INS-DET-REQ-001"].title["en"] == "Read noise"
    with pytest.raises(gitutil.GitError):
        with vault_at(root, "no-such-ref"):
            pass


def test_issued_copy_and_changes_page(demo_repository, tmp_path):
    import docx
    from typer.testing import CliRunner

    from qingsong.cli import app
    from qingsong.render.html import render_site

    root = demo_repository
    release.tag_release(root, document_id, "1.0", at="HEAD")
    reword_rationale(root, "Keeps faint spectra sky-limited.", "使暗弱光谱处于天光限。")

    runner = CliRunner()
    output = tmp_path / "issued.docx"
    result = runner.invoke(
        app,
        ["render", "docx", document_id, str(output), "--release", "1.0", "--vault", str(root)],
    )
    assert result.exit_code == 0, result.output
    properties = docx.Document(str(output)).core_properties
    assert properties.version == "1.0"
    assert properties.comments == "release tag release/DEMO-INS-DET-RD/1.0"
    texts = "\n".join(paragraph.text for paragraph in docx.Document(str(output)).paragraphs)
    assert "Keeps faint spectra" not in texts and "Keeps the faintest spectra" in texts

    result = runner.invoke(app, ["release", "changes", document_id, "--json", "--vault", str(root)])
    assert result.exit_code == 0, result.output
    assert '"INS-DET-REQ-001"' in result.output

    site = render_site(load(root), tmp_path / "site").parent
    page = (site / "documents" / f"{document_id}-changes.html").read_text()
    assert "INS-DET-REQ-001" in page and "<ins>" in page
    assert "Changes since v1.0" in (site / "documents" / f"{document_id}.html").read_text()


def test_export_lists_values_with_intervals(demo_repository, tmp_path):
    import json

    from typer.testing import CliRunner

    from qingsong.cli import app

    root = demo_repository
    output = tmp_path / "export.json"
    result = CliRunner().invoke(
        app, ["export", "json", "--output", str(output), "--vault", str(root)]
    )
    assert result.exit_code == 0, result.output
    data = json.loads(output.read_text())
    assert data["format"] == "qingsong-export" and data["format_version"] == 1
    assert data["commit"] == git(root, "rev-parse", "HEAD").strip() and data["dirty"] is False
    noise = next(entry for entry in data["values"] if entry["slot"] == "read_noise")
    assert noise["interval"] == {"low": None, "high": 3.0, "low_open": False, "high_open": False}
    assert noise["requirement"] == "INS-DET-REQ-001" and noise["certainty"] == "provisional"
    ids_in_order = [record["id"] for record in data["records"]]
    assert ids_in_order == sorted(ids_in_order, key=__import__("qingsong.ids").ids.sort_key)
    assert str(root) not in output.read_text()

    edit_yaml(
        requirement_file(root, "INS-DET-REQ-001"),
        lambda data: data["title"].__setitem__("en", "Edited"),
    )
    again = CliRunner().invoke(app, ["export", "json", "--vault", str(root)])
    assert json.loads(again.output)["dirty"] is True
    at_head = CliRunner().invoke(app, ["export", "json", "--at", "HEAD", "--vault", str(root)])
    exported = json.loads(at_head.output)
    titles = {record["id"]: record["title"]["en"] for record in exported["records"]}
    assert titles["INS-DET-REQ-001"] == "Read noise" and exported["dirty"] is False


def test_open_limits_compare_with_unbounded_ends():
    """Review finding 1: the open flag of `lt`/`gt` must not leak onto the infinite end."""
    meter = quantity("m")
    assert allowed(slot(relation="le", value=5, unit="m"), meter).within(
        allowed(slot(relation="lt", value=10, unit="m"), meter)
    )
    assert allowed(slot(relation="ge", value=5, unit="m"), meter).within(
        allowed(slot(relation="gt", value=3, unit="m"), meter)
    )
    assert not allowed(slot(relation="le", value=10, unit="m"), meter).within(
        allowed(slot(relation="lt", value=10, unit="m"), meter)
    )


def test_until_compares_with_the_release_before_it(demo_repository):
    """Review finding 2: --until at a release tag compares with the release before it."""
    root = demo_repository
    release.tag_release(root, document_id, "1.0", at="HEAD")
    git(root, "checkout", "-q", "-b", "next")
    reword_rationale(root, "Keeps faint spectra sky-limited.", "使暗弱光谱处于天光限。")
    release.prepare(root, document_id, "1.1", "alice", summary(), today=day)
    commit_all(root, "prepare 1.1")
    git(root, "checkout", "-q", "main")
    git(root, "merge", "-q", "--no-ff", "-m", "merge 1.1", "next")
    tag, _ = release.tag_release(root, document_id, "1.1")
    found = release.changes(root, document_id, until=tag)
    assert found.since == "v1.0" and [c.record for c in found.revised] == ["INS-DET-REQ-001"]
    with pytest.raises(OperationError, match="not earlier"):
        release.changes(root, document_id, since="1.1", until="release/DEMO-INS-DET-RD/1.0")


def test_reordering_and_moves_within_a_document_are_reported(demo_repository):
    """Review finding 3: order and moves within the document are changes."""
    root = demo_repository
    release.tag_release(root, document_id, "1.0", at="HEAD")
    path = root / "documents" / f"{document_id}.yaml"

    def swap(data):
        blocks = data["outline"][1]["section"]["blocks"]
        blocks[0], blocks[1] = blocks[1], blocks[0]

    edit_yaml(path, swap)
    operations.revise(root, document_id, "editorial", "figure first", "alice", today=day)
    found = release.changes(root, document_id)
    assert not found.is_empty()
    assert [(section.key, section.status) for section in found.sections] == [
        ("performance", "reordered")
    ]

    def move(data):
        figure = data["outline"][1]["section"]["blocks"].pop(0)
        data["outline"][0]["section"]["blocks"].append(figure)

    edit_yaml(path, move)
    operations.revise(root, document_id, "editorial", "figure moved", "alice", today=day)
    found = release.changes(root, document_id)
    assert found.moved_within == {"INS-DET-FIG-001": ["performance", "introduction"]}
    assert not found.sections


def test_repeated_section_keys_are_errors(demo):
    def repeat(data):
        data["outline"][1]["section"]["key"] = "introduction"

    edit_yaml(demo / "documents" / f"{document_id}.yaml", repeat)
    hits = [f for f in checks.run(load(demo)) if f.rule == "structure.outline"]
    assert any(f.severity == "error" and "'introduction'" in f.message for f in hits)


def test_empty_values_are_not_shown_as_text(demo, tmp_path):
    """Review finding 4: an empty mapping is not bilingual text."""
    from qingsong.render.html import Site

    site = Site(load(demo), tmp_path / "site")
    assert not site.is_text({})
    assert not site.is_text({"read_noise": {"relation": "le"}})
    assert site.is_text({"en": "text", "zh": "文本"})


def test_file_history_follows_renames(tmp_path):
    """Review finding 5: the commit that introduced a release is found across a rename."""
    root = tmp_path / "repository"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    (root / "old.yaml").write_text("releases: [{version: '1.0'}]\n")
    first = commit_all(root, "add")
    git(root, "mv", "old.yaml", "new.yaml")
    second = commit_all(root, "rename")
    assert gitutil.first_parent_history(root, "main", "new.yaml") == [
        (first, "old.yaml"),
        (second, "new.yaml"),
    ]


def test_conflicts_give_one_finding_per_requirement(demo):
    """Review finding 6: a requirement in conflict with several others gets one finding."""
    for record_id, value in (("INS-SYS-REQ-001", 5), ("INS-OPT-REQ-001", 6)):
        conflicting = {"quantity": "detector.read_noise", "relation": "ge", "value": value}
        conflicting.update({"unit": "count", "certainty": "firm"})

        def add(data, conflicting=conflicting):
            data["values"]["noise"] = conflicting
            data["allocated_to"] = "INS"

        edit_yaml(requirement_file(demo, record_id), add)
    hits = [f for f in checks.run(load(demo)) if f.rule == "consistency.conflict"]
    by_record = {}
    for finding in hits:
        by_record.setdefault(finding.record, []).append(finding)
    assert len(by_record["INS-DET-REQ-001"]) == 1
    assert "INS-OPT-REQ-001" in by_record["INS-DET-REQ-001"][0].message
    assert "INS-SYS-REQ-001" in by_record["INS-DET-REQ-001"][0].message


def test_no_changes_page_without_a_tagged_release(demo, tmp_path):
    """Review finding 7: documents without a tagged release get no changes page or link."""
    from qingsong.render.html import render_site

    site = render_site(load(demo), tmp_path / "site").parent
    assert not (site / "documents" / f"{document_id}-changes.html").exists()
    assert "Changes since" not in (site / "documents" / f"{document_id}.html").read_text()


def test_repeated_version_is_reported_once(demo):
    def repeat(data):
        data["releases"].append(dict(data["releases"][0]))

    edit_yaml(demo / "documents" / f"{document_id}.yaml", repeat)
    hits = [f for f in checks.run(load(demo)) if f.rule == "documents.release"]
    assert len(hits) == 1 and "twice" in hits[0].message
