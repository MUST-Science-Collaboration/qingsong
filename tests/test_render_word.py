"""The Word renderer writes a valid package with numbered, bilingual content."""

import zipfile

import docx

from qingsong.render.word import check_package, render_docx
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
    assert "The detector read noise shall be [≤ 3] (see Figure 2.1)." in texts
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
