"""The Word renderer writes a valid package with numbered, bilingual content."""

import datetime
import re
import zipfile

import docx
import pytest
from conftest import edit_yaml
from docx.oxml.ns import qn

from qingsong.render.html import render_site
from qingsong.render.word import change_record_limit, check_package, display_width, render_docx
from qingsong.vault import load


def test_word_document_is_valid_and_complete(demo, tmp_path):
    output = render_docx(load(demo), "DEMO-INS-DET-RD", tmp_path / "out.docx", version="1.1")
    assert check_package(output) == []
    with zipfile.ZipFile(output) as package:
        assert not [name for name in package.namelist() if name.endswith("/")]
        assert any(name.startswith("word/media/") for name in package.namelist())
    texts = [paragraph.text for paragraph in docx.Document(str(output)).paragraphs]
    assert "1. Introduction (简介)" in texts
    assert "2.1 INS-DET-REQ-001 Read noise (读出噪声)" in texts
    assert "The detector read noise shall be ≤ [3] (see Figure 2.1)." in texts
    assert any(text.startswith("Figure 2.1. ") for text in texts)
    assert any(text.startswith("图2.1 ") for text in texts)
    assert "本文件给出探测器的需求，见第2节。" in texts
    assert not any("{read_noise}" in text or "[[" in text for text in texts)


def test_package_check_finds_directory_entries(tmp_path):
    path = tmp_path / "bad.docx"
    with zipfile.ZipFile(path, "w") as package:
        package.writestr("word/", "")
        package.writestr("word/document.xml", '<w:tblW w:w="5000.0"/>')
    problems = check_package(path)
    assert any("directory entry" in problem for problem in problems)
    assert any("integers" in problem for problem in problems)


def test_table_of_contents_is_filled_without_an_update_prompt(demo, tmp_path):
    """Word asks "fields that may refer to other files" when updateFields is set; the table of
    contents is filled instead, each entry linked to a bookmark on its heading."""
    output = render_docx(load(demo), "DEMO-INS-DET-RD", tmp_path / "out.docx")
    with zipfile.ZipFile(output) as package:
        settings = package.read("word/settings.xml").decode("utf-8")
        body = package.read("word/document.xml").decode("utf-8")
    assert "updateFields" not in settings
    assert body.count('w:fldCharType="begin"') == body.count('w:fldCharType="end"')
    assert "TOC \\o" in body
    anchors = re.findall(r'w:anchor="(_Toc\d+)"', body)
    bookmarks = set(re.findall(r'w:bookmarkStart w:id="\d+" w:name="(_Toc\d+)"', body))
    assert anchors and set(anchors) == bookmarks
    texts = [paragraph.text for paragraph in docx.Document(str(output)).paragraphs]
    toc = texts.index("TABLE OF CONTENTS")
    assert "1. Introduction (简介)" in texts[toc + 1 : toc + 12]

    prompted = render_docx(
        load(demo), "DEMO-INS-DET-RD", tmp_path / "prompted.docx", update_fields_on_open=True
    )
    with zipfile.ZipFile(prompted) as package:
        assert "updateFields" in package.read("word/settings.xml").decode("utf-8")


def add_releases(demo, long_summary: dict) -> None:
    def change(data):
        data["releases"].append(
            {
                "version": "1.1",
                "date": datetime.date(2026, 2, 1),
                "summary": long_summary,
                "note": {"en": "Reviewed by the detector group."},
                "by": "alice",
                "made_with_qingsong": True,
            }
        )
        data["releases"].append(
            {
                "version": "1.2",
                "date": datetime.date(2026, 3, 1),
                "summary": {"en": "Correct a figure", "zh": "更正一幅图"},
                "by": "Carol Example (before the record)",
                "made_with_qingsong": True,
            }
        )

    edit_yaml(demo / "documents" / "DEMO-INS-DET-RD.yaml", change)


def test_change_record_has_fixed_columns_names_and_an_appendix(demo, tmp_path):
    """Columns keep their widths, people show by name, and an explanation too long for its cell
    is printed in Appendix A and cited in the table."""
    long_summary = {
        "en": "Raise the read-noise limit after the detector tests. " * 5,
        "zh": "根据探测器测试结果放宽读出噪声限值。" * 5,
    }
    assert display_width(long_summary["en"]) <= change_record_limit
    assert display_width(long_summary["zh"] + long_summary["en"]) > change_record_limit
    add_releases(demo, {language: text.strip() for language, text in long_summary.items()})
    output = render_docx(load(demo), "DEMO-INS-DET-RD", tmp_path / "out.docx", version="1.2")
    assert check_package(output) == []
    word = docx.Document(str(output))

    table = word.tables[0]
    rows = [[cell.text for cell in row.cells] for row in table.rows]
    assert rows[1] == ["v1.0", "2026/01/15", "首次发布（Word） (First issue (Word))", ""]
    assert rows[2] == ["v1.1", "2026/02/01", "详见附录A.1 (See Appendix A.1)", "Alice Example"]
    assert rows[3] == [
        "v1.2",
        "2026/03/01",
        "更正一幅图 (Correct a figure)",
        "Carol Example (before the record)",
    ]
    widths = [cell.width.twips for cell in table.rows[1].cells]
    assert widths == [column.width.twips for column in table.columns]
    assert widths[2] > widths[3] > widths[1] > widths[0]
    assert table._tbl.tblPr.find(qn("w:tblLayout")).get(qn("w:type")) == "fixed"

    texts = [paragraph.text for paragraph in word.paragraphs]
    appendix = texts.index("Appendix A. Document Change Records (附录A 文件修订记录)")
    assert appendix > texts.index("2. Performance (性能)")
    assert texts[appendix + 1] == "A.1 v1.1 (2026/02/01)"
    assert long_summary["en"].strip() in texts[appendix:]
    assert long_summary["zh"].strip() in texts[appendix:]
    assert "Reviewed by the detector group." in texts[appendix:]
    toc = texts.index("TABLE OF CONTENTS")
    assert "Appendix A. Document Change Records (附录A 文件修订记录)" in texts[toc : toc + 12]


def test_short_change_records_need_no_appendix(demo, tmp_path):
    output = render_docx(load(demo), "DEMO-INS-DET-RD", tmp_path / "out.docx")
    texts = [paragraph.text for paragraph in docx.Document(str(output)).paragraphs]
    assert not any(text.startswith("Appendix A") for text in texts)


def test_html_change_record_shows_names(demo, tmp_path):
    add_releases(demo, {"en": "Raise the read-noise limit", "zh": "放宽读出噪声限值"})
    site = render_site(load(demo), tmp_path / "site").parent
    page = (site / "documents" / "DEMO-INS-DET-RD.html").read_text(encoding="utf-8")
    assert "<td>Alice Example</td>" in page
    assert "<td>alice</td>" not in page


def write_template(root, cover: list[str], header: list[list[str]], footer: str | None = None):
    """A reference document with a cover, header paragraphs given as runs, and an optional
    footer."""
    template = docx.Document()
    for line in cover:
        template.add_paragraph(line)
    section = template.sections[0]
    section.header.paragraphs[0].text = ""
    for index, runs in enumerate(header):
        paragraph = section.header.paragraphs[0] if index == 0 else section.header.add_paragraph()
        for run in runs:
            paragraph.add_run(run)
    if footer:
        section.footer.paragraphs[0].text = footer
    (root / "templates").mkdir(exist_ok=True)
    template.save(str(root / "templates" / "reference.docx"))


def test_template_cover_header_and_footer_are_kept_with_fields_filled(demo, tmp_path):
    write_template(
        demo,
        cover=["{title_zh}", "{title_en}", "{document_id} v{version}"],
        header=[["Ref.: {document_id}"], ["Ver.: {ver", "sion}"], ["Date: ", "{date}"]],
        footer="Demo Observatory",
    )
    output = render_docx(load(demo), "DEMO-INS-DET-RD", tmp_path / "out.docx", version="1.0")
    word = docx.Document(str(output))
    texts = [paragraph.text for paragraph in word.paragraphs]
    assert texts[:4] == [
        "探测器需求文档",
        "Detector Requirements",
        "DEMO-INS-DET-RD v1.0",
        "Document Change Records",
    ]
    assert not any(text.startswith("Generated from") for text in texts)
    section = word.sections[0]
    assert [paragraph.text for paragraph in section.header.paragraphs] == [
        "Ref.: DEMO-INS-DET-RD",
        "Ver.: 1.0",
        "Date: Jan 15, 2026",
    ]
    assert [paragraph.text for paragraph in section.footer.paragraphs] == ["Demo Observatory"]
    with zipfile.ZipFile(output) as package:
        footers = [name for name in package.namelist() if name.startswith("word/footer")]
        assert "PAGE" not in "".join(package.read(name).decode("utf-8") for name in footers)


def test_a_template_without_cover_or_footer_gets_the_built_in_ones(demo, tmp_path):
    write_template(demo, cover=[], header=[["{document_id} · {title_en}"]])
    output = render_docx(load(demo), "DEMO-INS-DET-RD", tmp_path / "out.docx")
    word = docx.Document(str(output))
    texts = [paragraph.text for paragraph in word.paragraphs]
    assert texts[0] == "探测器需求文档"
    assert any(text.startswith("Generated from") for text in texts[:4])
    section = word.sections[0]
    assert section.header.paragraphs[0].text == "DEMO-INS-DET-RD · Detector Requirements"
    footer = section.footer._element.xml
    assert "PAGE" in footer


def test_an_unknown_template_field_is_an_error(demo, tmp_path):
    write_template(demo, cover=["{titel_en}"], header=[["{document_id}"]])
    with pytest.raises(ValueError, match=r"\{titel_en\}"):
        render_docx(load(demo), "DEMO-INS-DET-RD", tmp_path / "out.docx")
