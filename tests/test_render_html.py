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
        "images/INS-DET-FIG-001.png",
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
