"""Moving numbers into value slots without changing the meaning; forms; goals (docs/SPEC.md §5.2)."""

import datetime

import pytest
from conftest import edit_yaml, git, requirement_file

from qingsong import checks, operations
from qingsong.checks.consistency import allowed
from qingsong.hashing import approved_text_hash
from qingsong.operations import OperationError
from qingsong.schema import ValueSlot
from qingsong.slots import normalized, slot_values
from qingsong.vault import load

day = datetime.date(2026, 11, 2)
record_id = "INS-OPT-REQ-001"


def write_statement(root, english: str, chinese: str, approve: bool = True) -> None:
    def change(data):
        data["statement"]["en"] = english
        data["statement"]["zh"] = chinese

    edit_yaml(requirement_file(root, record_id), change)
    operations.revise(
        root, record_id, "editorial", "aperture added", "alice", translation="reviewed", today=day
    )
    if approve:
        operations.approve(root, record_id, "agreed", "alice", "test", today=day)


def aperture(**changes) -> dict:
    fields = {
        "relation": "eq",
        "value": 140,
        "tolerance": {"plus": 2, "minus": 2},
        "unit": "mm",
        "certainty": "firm",
        "replaces": {"en": "140 mm ± 2 mm", "zh": "140 mm ± 2 mm"},
    }
    fields.update(changes)
    return {"aperture": fields}


english = "The reflectance of every lens surface shall be {reflectance} from 400 to 900 nm, over a clear aperture of 140 mm ± 2 mm."
chinese = "每个透镜表面在400至900 nm、140 mm ± 2 mm通光孔径内的反射率应{reflectance}。"


def findings(root, rule: str, against: str | None = None):
    return [f for f in checks.run(load(root), against=against) if f.rule == rule]


def test_a_move_keeps_the_meaning_and_the_approval(demo):
    write_statement(demo, english, chinese)
    record, comparisons = slot_values(demo, record_id, aperture(), "alice", today=day)
    assert record.statement["en"].endswith("over a clear aperture of {aperture}.")
    assert "{aperture}通光孔径" in record.statement["zh"]
    assert record.values["aperture"].tolerance.plus == 2
    assert record.normative_revision == 1
    assert record.approval.text_hash == approved_text_hash(record, "en")
    event = record.history[-1]
    assert event.event == "slotted" and event.change_class == "editorial"
    assert event.normative_hash_after == record.normative_hash != event.normative_hash_before
    assert [language for language, _, _ in comparisons] == ["en", "zh"]
    for rule in ("change.approval", "change.translation", "change.unrecorded", "content.values"):
        assert not [f for f in findings(demo, rule) if f.record == record_id], rule


def test_a_dry_run_writes_nothing(demo):
    write_statement(demo, english, chinese)
    path = requirement_file(demo, record_id)
    before = path.read_text(encoding="utf-8")
    _, comparisons = slot_values(demo, record_id, aperture(), "alice", today=day, dry_run=True)
    assert path.read_text(encoding="utf-8") == before
    assert "{aperture}" in comparisons[0][2]


@pytest.mark.parametrize(
    ("statement_en", "slot", "message"),
    [
        (english.replace("of 140", "of at least 140"), aperture(), "'at least' sits next to"),
        (english, aperture(value=141), "a move must keep the meaning"),
        (english.replace("aperture of", "aperture 140 mm ± 2 mm of"), aperture(), "occurs 2 times"),
        (english, aperture(replaces={"en": "140 mm ± 2 mm"}), "in zh as well"),
        (english, {"Aperture": aperture()["aperture"]}, "lower case"),
        (english, {"reflectance": aperture()["aperture"]}, "already has this slot"),
    ],
)
def test_moves_that_could_change_the_meaning_are_refused(demo, statement_en, slot, message):
    write_statement(demo, statement_en, chinese)
    with pytest.raises(OperationError, match=message):
        slot_values(demo, record_id, slot, "alice", today=day)


def test_unrecorded_edits_are_not_carried_into_an_approval(demo):
    write_statement(demo, english, chinese)
    edit_yaml(
        requirement_file(demo, record_id),
        lambda data: data["rationale"].__setitem__("en", "Changed without recording."),
    )
    with pytest.raises(OperationError, match="unrecorded changes"):
        slot_values(demo, record_id, aperture(), "alice", today=day)


def test_a_stale_approval_stays_stale(demo):
    write_statement(demo, english, chinese)

    def reword(data):
        data["rationale"]["en"] = "Reworded after the approval."
        data["statement"]["en"] = english.replace("every lens", "each lens")

    edit_yaml(requirement_file(demo, record_id), reword)
    operations.revise(
        demo, record_id, "editorial", "statement reworded", "alice", translation="reviewed"
    )
    record, _ = slot_values(demo, record_id, aperture(), "alice", today=day)
    assert record.approval.text_hash != approved_text_hash(record, "en")
    assert [f for f in findings(demo, "change.approval") if f.record == record_id]


def test_relation_words_inside_the_literal_are_read(demo):
    write_statement(
        demo,
        english.replace("140 mm ± 2 mm", "more than [20,000] mm"),
        chinese.replace("140 mm ± 2 mm", "超过[20,000] mm"),
        approve=False,
    )
    slot = {
        "relation": "gt",
        "value": 20000,
        "unit": "mm",
        "certainty": "provisional",
        "issue": "ISS-0001",
        "replaces": {"en": "more than [20,000] mm", "zh": "超过[20,000] mm"},
    }
    record, _ = slot_values(demo, record_id, {"aperture": slot}, "alice", today=day)
    assert "{aperture}" in record.statement["en"] and "{aperture}" in record.statement["zh"]


def test_against_accepts_the_move_and_nothing_after_it(demo_repository):
    root = demo_repository
    write_statement(root, english, chinese)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "aperture")
    slot_values(root, record_id, aperture(), "alice", today=day)
    assert not findings(root, "integrity.against", against="main")

    path = requirement_file(root, record_id)
    data = operations.load_round_trip(path)
    data["values"]["aperture"]["value"] = 150
    _record, text = operations.stamped(data)
    path.write_text(text, encoding="utf-8")
    assert any(
        "normative revision did not change" in f.message
        for f in findings(root, "integrity.against", against="main")
    )


def test_a_relation_said_twice_is_flagged(demo):
    def doubled(data):
        data["statement"]["en"] = data["statement"]["en"].replace("transmit", "transmit at least")

    edit_yaml(requirement_file(demo, "INS-SYS-REQ-001"), doubled)
    messages = [f.message for f in findings(demo, "content.values")]
    assert any("'at least' next to it says it again" in message for message in messages)


def test_normalisation_names_its_differences():
    assert normalized("140 μm ± 2 μm") == normalized("140 ± 2 μm")
    assert normalized("≥ [7,500]") == normalized("≥ [7500]")
    assert normalized("at least [90 %]") == normalized("≥ [90 %]")
    assert normalized("140 µm") == normalized("140 μm")
    assert normalized("(20 ± 0.5)%") == normalized("20 ± 0.5 %")
    assert normalized("[20,000] mm") == normalized("[20,000 mm]")
    assert normalized("[20,000] mm") != normalized("[20,000 m]")
    assert normalized("90 %") != normalized("≥ 90 %")
    assert normalized("140 mm") != normalized("140 m")


def test_goals_sit_on_the_better_side_and_are_not_compared():
    with pytest.raises(ValueError, match="better side"):
        ValueSlot.model_validate({"relation": "le", "value": 1, "goal": 2, "certainty": "firm"})
    with pytest.raises(ValueError, match="belongs to a limit"):
        ValueSlot.model_validate({"relation": "eq", "value": 1, "goal": 1, "certainty": "firm"})
    from test_release import quantity

    meter = quantity("m")
    plain = ValueSlot.model_validate(
        {"relation": "ge", "value": 5, "unit": "m", "certainty": "firm"}
    )
    with_goal = plain.model_copy(update={"goal": 8})
    assert allowed(plain, meter) == allowed(with_goal, meter)


def test_forms_are_shown_and_exported(demo, tmp_path):
    import json

    from qingsong.export import export_vault
    from qingsong.render.html import render_site

    write_statement(demo, english, chinese, approve=False)
    site = render_site(load(demo), tmp_path / "site").parent
    page = (site / "r" / f"{record_id}.html").read_text()
    assert "form-quantitative" in page and "numbers in text" in page
    science = (site / "r" / "DEMO-SCI-REQ-001.html").read_text()
    assert "form-qualitative" in science
    data = json.loads(json.dumps(export_vault(load(demo), None, None)))
    assert data["forms"]["DEMO-SCI-REQ-001"] == "qualitative"
    assert data["forms"][record_id] == "quantitative"
