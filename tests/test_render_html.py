"""The HTML site renders every record, resolves references and numbers documents."""

import re

from qingsong.render.html import render_site
from qingsong.render.model import number_document
from qingsong.vault import load


def test_site_renders_every_page(demo, tmp_path):
    vault = load(demo)
    index = render_site(vault, tmp_path / "site")
    site = index.parent
    for name in (
        "index.html",
        "tree.html",
        "flow.html",
        "registers.html",
        "checks.html",
        "static/site.css",
        "static/search_index.js",
        "images/INS-DET-FIG-001/INS-DET-FIG-001.png",
        "documents/DEMO-INS-DET-RD.html",
        "f/INS-DET-FIG-001.html",
    ):
        assert (site / name).exists(), name
    requirements = [
        record_id for record_id, record in vault.records.items() if record.type == "requirement"
    ]
    assert {path.stem for path in (site / "r").glob("*.html")} == set(requirements)


def test_references_resolve_and_documents_are_numbered(demo, tmp_path):
    vault = load(demo)
    document = vault.records["DEMO-INS-DET-RD"]
    numbering = number_document(document)
    assert numbering.sections == {"introduction": "1", "performance": "2"}
    assert numbering.requirements == {"INS-DET-REQ-001": "2.1"}
    assert numbering.figures == {"INS-DET-FIG-001": "2.1"}
    site = render_site(vault, tmp_path / "site").parent
    page = (site / "documents" / "DEMO-INS-DET-RD.html").read_text()
    assert "Section 2" in page and "第2节" in page
    assert "Figure 2.1" in page and "图2.1" in page
    for path in site.rglob("*.html"):
        assert 'class="ref broken"' not in path.read_text(), path.name


def test_open_values_are_marked_and_text_is_escaped(demo, tmp_path):
    from conftest import edit_yaml, requirement_file

    edit_yaml(
        requirement_file(demo, "DEMO-SCI-REQ-001"),
        lambda data: data["rationale"].__setitem__(
            "en", "Keep <script> out; [5 %] is provisional."
        ),
    )
    site = render_site(load(demo), tmp_path / "site").parent
    page = (site / "r" / "DEMO-SCI-REQ-001.html").read_text()
    assert "&lt;script&gt;" in page and "<script> out" not in page
    assert re.search(r'<mark class="open"[^>]*>\[5 %\]</mark>', page)


def test_record_text_cannot_break_out_of_scripts(demo, tmp_path):
    from conftest import edit_yaml, requirement_file

    edit_yaml(
        requirement_file(demo, "INS-DET-REQ-001"),
        lambda data: data["title"].__setitem__("en", "Noise </script><script>alert(1)</script>"),
    )
    site = render_site(load(demo), tmp_path / "site").parent
    for name in ("tree.html", "flow.html", "static/search_index.js"):
        assert "</script><script>alert(1)" not in (site / name).read_text(), name


def test_inline_markup_follows_pandoc_rules():
    from qingsong.render.text import blocks, inline

    def resolve(target, key, language):
        return target, None

    assert inline("costs $5 or $10", "en", resolve) == "costs $5 or $10"
    assert inline("~45 m to ~50 m", "en", resolve) == "~45 m to ~50 m"
    assert inline("2 * 3 = 6 and 4 * 5", "en", resolve) == "2 * 3 = 6 and 4 * 5"
    assert inline("H~2~O and m^2^", "en", resolve) == "H<sub>2</sub>O and m<sup>2</sup>"
    assert (
        inline("**bold *nested* here**", "en", resolve)
        == "<strong>bold <em>nested</em> here</strong>"
    )
    assert inline(r"\*literal\*", "en", resolve) == "*literal*"
    assert "<mark" not in inline("Note[^1]", "en", resolve)
    assert "href" not in inline("[x](javascript:alert(1))", "en", resolve)
    assert blocks("Shall:\n- a\n- b", "en", resolve) == "<p>Shall:</p><ul><li>a</li><li>b</li></ul>"
    assert blocks("- a\n  more\n- b\n  - c", "en", resolve) == (
        "<ul><li>a more</li><li>b<ul><li>c</li></ul></li></ul>"
    )


def test_value_slots_read_as_written():
    from qingsong.render.text import format_slot
    from qingsong.schema import ValueSlot

    def slot(**fields):
        return ValueSlot.model_validate(fields)

    assert (
        format_slot(
            slot(
                relation="eq",
                value=100,
                tolerance={"plus": 2, "minus": 2},
                unit="um",
                certainty="firm",
            ),
            "en",
        )
        == "100 ± 2 μm"
    )
    assert (
        format_slot(slot(relation="le", value=0.8, unit="deg", certainty="provisional"), "en")
        == "[≤ 0.8°]"
    )
    assert (
        format_slot(
            slot(relation="range", minimum=-5, maximum=-3, unit="degC", certainty="firm"), "en"
        )
        == "−5–−3 °C"
    )
    assert (
        format_slot(slot(relation="ge", value=25000000000, unit="Hz", certainty="tbc"), "en")
        == "≥ 2.5 × 10¹⁰ Hz (TBC)"
    )
    assert (
        format_slot(
            slot(
                relation="eq",
                value=20,
                tolerance={"plus": 0.5, "minus": 0.5},
                unit="percent",
                certainty="firm",
            ),
            "en",
        )
        == "(20 ± 0.5)%"
    )
    assert (
        format_slot(slot(relation="eq", value=7500, unit="count", certainty="firm"), "en")
        == "7,500"
    )
    assert (
        format_slot(slot(relation="eq", value=9.8, unit="m/s^2", certainty="firm"), "en")
        == "9.8 m/s²"
    )
