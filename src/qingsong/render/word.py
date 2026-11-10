"""Word output (docs/SPEC.md §12.2): a formal document generated from the records.

The layout follows the MUST requirement documents: cover, change record, responsibilities, table of
contents, acronyms, reference documents, publications, then numbered sections with bilingual
requirement entries (requirement, rationale, notes, suggestions, verification), figures with numbered
captions in both languages, and tables. A change-record explanation too long for its cell is printed
in Appendix A at the end and cited in the table. A reference document (`templates/reference.docx` in
the vault) supplies the styles; its body is discarded."""

import datetime
import re
import unicodedata
import zipfile
from pathlib import Path

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.image.image import Image as DocxImage
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Emu, Pt, Twips

from qingsong.render.model import documents_of, number_document
from qingsong.render.text import parse_blocks, substitute_slots, token_pattern
from qingsong.schema import Block, Document, Figure, Release, Requirement
from qingsong.vault import Vault

settings_after_update = {
    qn(f"w:{name}")
    for name in (
        "hdrShapeDefaults",
        "footnotePr",
        "endnotePr",
        "compat",
        "docVars",
        "rsids",
        "attachedSchema",
        "themeFontLang",
        "clrSchemeMapping",
        "doNotIncludeSubdocsInStats",
        "doNotAutoCompressPictures",
        "forceUpgrade",
        "captions",
        "readModeInkLockDown",
        "smartTagType",
        "shapeDefaults",
        "doNotEmbedSmartTags",
        "decimalSymbol",
        "listSeparator",
    )
} | {
    "{http://schemas.openxmlformats.org/officeDocument/2006/math}mathPr",
    "{http://schemas.openxmlformats.org/schemaLibrary/2006/main}schemaLibrary",
}
part_labels = [
    ("statement", "需求 (Requirement)"),
    ("rationale", "原因 (Rationale)"),
    ("notes", "说明 (Notes)"),
    ("suggestions", "建议 (Suggestions)"),
]
verification_label = "验收方式 (Verification)"
change_record_widths = (0.10, 0.14, 0.52, 0.24)
change_record_limit = 300
"""The longest change-record explanation printed in the table, in display columns (a Chinese
character counts as two). About six lines of the explanation column. A longer one goes to Appendix A."""


def display_width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(character) in "WF" else 1 for character in text)


def explanation(release: Release) -> str:
    """The change-record text of a release: the summary in both languages, then the note."""
    summary = release.summary
    text = (
        f"{summary['zh']} ({summary['en']})"
        if "zh" in summary and "en" in summary
        else summary.get("en") or summary.get("zh", "")
    )
    if release.note:
        text += "\n" + next(iter(release.note.values()))
    return text


class WordRenderer:
    def __init__(
        self,
        vault: Vault,
        document: Document,
        version: str | None,
        template: Path | None,
        latin_font: str | None = None,
        east_asian_font: str | None = None,
        update_fields_on_open: bool = False,
        tag: str | None = None,
    ):
        self.vault = vault
        self.tag = tag
        self.update_fields_on_open = update_fields_on_open
        self.contents_entries: list[tuple[int, str, str]] = []
        self.change_details: list[tuple[str, Release]] = []
        self.document = document
        self.numbering = number_document(document)
        self.numberings = {record.id: number_document(record) for record in documents_of(vault)}
        self.version = version
        self.latin_font = latin_font
        self.east_asian_font = east_asian_font
        self.word = (
            docx.Document(str(template)) if template and template.exists() else docx.Document()
        )
        self.clear_body()
        self.bullet_number = self.bullet_numbering()

    # set-up ---------------------------------------------------------------------------------
    def clear_body(self) -> None:
        body = self.word.element.body
        for child in list(body):
            if child.tag != qn("w:sectPr"):
                body.remove(child)

    def bullet_numbering(self) -> int | None:
        """A numbering instance for bullet lists, based on the template's first bullet definition."""
        try:
            numbering = self.word.part.numbering_part.element
        except Exception:  # documents without a numbering part get plain indented paragraphs
            return None
        abstract_id = None
        for abstract in numbering.findall(qn("w:abstractNum")):
            level = abstract.find(qn("w:lvl"))
            fmt = level.find(qn("w:numFmt")) if level is not None else None
            if fmt is not None and fmt.get(qn("w:val")) == "bullet":
                abstract_id = abstract.get(qn("w:abstractNumId"))
                break
        if abstract_id is None:
            return None
        existing = [int(num.get(qn("w:numId"))) for num in numbering.findall(qn("w:num"))]
        number_id = max(existing, default=0) + 1
        num = OxmlElement("w:num")
        num.set(qn("w:numId"), str(number_id))
        abstract = OxmlElement("w:abstractNumId")
        abstract.set(qn("w:val"), abstract_id)
        num.append(abstract)
        numbering.append(num)
        return number_id

    # text -----------------------------------------------------------------------------------
    def label(self, target: str, key: str | None, language: str) -> str:
        """The same labels as the HTML site: sections and figures are numbered by the document
        that holds them, also when that is another document."""
        record = self.vault.records.get(target)
        if key:
            other = self.numberings.get(target)
            number = other.sections.get(key, "?") if other else "?"
            return f"Section {number}" if language == "en" else f"第{number}节"
        if isinstance(record, Figure):
            home = (
                self.numbering
                if target in self.numbering.figures
                else next(
                    (
                        numbering
                        for numbering in self.numberings.values()
                        if target in numbering.figures
                    ),
                    None,
                )
            )
            if home:
                number = home.figures[target]
                return f"Figure {number}" if language == "en" else f"图{number}"
        return target

    def font(self, run, monospace: bool = False) -> None:
        if monospace:
            run.font.name = "Menlo"
            return
        if self.latin_font:
            run.font.name = self.latin_font
        if self.east_asian_font:
            properties = run._element.get_or_add_rPr()
            fonts = properties.find(qn("w:rFonts"))
            if fonts is None:
                fonts = OxmlElement("w:rFonts")
                properties.insert(0, fonts)
            fonts.set(qn("w:eastAsia"), self.east_asian_font)

    def runs(
        self, paragraph, text: str, language: str, bold: bool = False, italic: bool = False
    ) -> None:
        position = 0
        for match in token_pattern.finditer(text):
            if match.start() > position:
                self.add_run(paragraph, text[position : match.start()], bold=bold, italic=italic)
            position = match.end()
            kind, token = match.lastgroup, match.group(0)
            if match.group("reference"):
                self.add_run(
                    paragraph,
                    self.label(match.group("target"), match.group("key"), language),
                    bold=bold,
                    italic=italic,
                )
            elif match.group("link"):
                self.runs(paragraph, match.group("link_text"), language, bold, italic)
                if match.group("url") != match.group("link_text"):
                    self.add_run(paragraph, f" ({match.group('url')})", italic=italic)
            elif kind == "code":
                self.add_run(paragraph, token[1:-1], monospace=True)
            elif kind == "math":
                self.add_run(paragraph, token[1:-1], italic=True)
            elif kind == "bold":
                self.runs(paragraph, token[2:-2], language, True, italic)
            elif kind == "italic":
                self.runs(paragraph, token[1:-1], language, bold, True)
            elif kind == "sub":
                self.add_run(paragraph, token[1:-1], bold=bold, italic=italic, subscript=True)
            elif kind == "sup":
                self.add_run(paragraph, token[1:-1], bold=bold, italic=italic, superscript=True)
            else:
                self.add_run(paragraph, token, bold=bold, italic=italic)
        if position < len(text):
            self.add_run(paragraph, text[position:], bold=bold, italic=italic)

    def add_run(
        self,
        paragraph,
        text: str,
        bold: bool = False,
        italic: bool = False,
        subscript: bool = False,
        superscript: bool = False,
        monospace: bool = False,
    ):
        run = paragraph.add_run(text)
        run.bold = bold or None
        run.italic = italic or None
        if subscript:
            run.font.subscript = True
        if superscript:
            run.font.superscript = True
        self.font(run, monospace)
        return run

    def paragraph(
        self,
        text: str = "",
        language: str = "en",
        style: str | None = None,
        level: int | None = None,
        bold: bool = False,
        align=None,
    ):
        paragraph = self.word.add_paragraph(style=style if style in self.style_names() else None)
        if level is not None:
            self.bulletize(paragraph, level)
        if align is not None:
            paragraph.alignment = align
        if text:
            self.runs(paragraph, text, language, bold=bold)
        return paragraph

    def style_names(self) -> set[str]:
        if not hasattr(self, "_style_names"):
            self._style_names = {style.name for style in self.word.styles}
        return self._style_names

    def bulletize(self, paragraph, level: int) -> None:
        if "List Paragraph" in self.style_names():
            paragraph.style = self.word.styles["List Paragraph"]
        if self.bullet_number is None:
            paragraph.paragraph_format.left_indent = Pt(18 * (level + 1))
            return
        properties = paragraph._p.get_or_add_pPr()
        numbering = OxmlElement("w:numPr")
        indent_level = OxmlElement("w:ilvl")
        indent_level.set(qn("w:val"), str(level))
        number = OxmlElement("w:numId")
        number.set(qn("w:val"), str(self.bullet_number))
        numbering.append(indent_level)
        numbering.append(number)
        properties.append(numbering)

    def localized_paragraphs(
        self, value: dict | None, level: int | None, languages=("en", "zh")
    ) -> None:
        """Each language's paragraphs in turn; list items become bullets one level deeper (numbered
        items keep their number as text)."""
        if not value:
            return
        shown = [language for language in languages if language in value]
        same = len(shown) == 2 and value[shown[0]].strip() == value[shown[1]].strip()
        for language in shown[:1] if same else shown:
            for block in parse_blocks(value[language]):
                if block.kind == "paragraph":
                    self.paragraph(block.text, language, level=level)
                    continue
                counters: dict[int, int] = {}
                for item in block.items:
                    counters[item.level] = counters.get(item.level, 0) + 1
                    prefix = f"{counters[item.level]}. " if item.ordered else ""
                    base = (level + 1) if level is not None else 0
                    self.paragraph(prefix + item.text, language, level=min(base + item.level, 8))

    def bilingual_title(self, value: dict) -> str:
        english, chinese = value.get("en", ""), value.get("zh", "")
        return f"{english} ({chinese})" if english and chinese else english or chinese

    # tables ---------------------------------------------------------------------------------
    def text_width(self):
        section = self.word.sections[-1]
        return Emu(section.page_width - section.left_margin - section.right_margin)

    def table(
        self,
        header: list[str],
        rows: list[list[str]],
        languages: list[str] | None = None,
        widths: tuple[float, ...] | None = None,
    ):
        """A table with a repeated header row. `widths` are the columns' shares of the text width,
        kept fixed in Word; without them the columns share the width equally."""
        table = self.word.add_table(rows=1, cols=len(header))
        if "Table" in {style.name for style in self.word.styles}:
            table.style = self.word.styles["Table"]
        elif "Table Grid" in {style.name for style in self.word.styles}:
            table.style = self.word.styles["Table Grid"]
        for cell, text in zip(table.rows[0].cells, header, strict=True):
            cell.paragraphs[0].text = ""
            self.runs(cell.paragraphs[0], text, "en", bold=True)
        header_row = table.rows[0]._tr.get_or_add_trPr()
        repeat = OxmlElement("w:tblHeader")
        repeat.set(qn("w:val"), "true")
        header_row.append(repeat)
        for row in rows:
            cells = table.add_row().cells
            row = [*row, *[""] * (len(cells) - len(row))][: len(cells)]
            for index, (cell, text) in enumerate(zip(cells, row, strict=True)):
                language = languages[index] if languages else "en"
                parts = text.split("\n") if text else [""]
                cell.paragraphs[0].text = ""
                self.runs(cell.paragraphs[0], parts[0], language)
                for extra in parts[1:]:
                    self.runs(cell.add_paragraph(), extra, "zh")
        if widths:
            self.fix_widths(table, widths)
        self.word.add_paragraph()
        return table

    def fix_widths(self, table, widths: tuple[float, ...]) -> None:
        columns = [Twips(int(self.text_width().twips * share)) for share in widths]
        table.autofit = False
        width = table._tbl.tblPr.find(qn("w:tblW"))
        width.set(qn("w:w"), str(sum(column.twips for column in columns)))
        width.set(qn("w:type"), "dxa")
        for column, size in zip(table.columns, columns, strict=True):
            column.width = size
        for row in table.rows:
            for cell, size in zip(row.cells, columns, strict=True):
                cell.width = size

    # document parts -------------------------------------------------------------------------
    def cover(self) -> None:
        title = self.document.title
        for language, size in (("zh", 22), ("en", 20)):
            if language in title:
                paragraph = self.paragraph(align=WD_ALIGN_PARAGRAPH.CENTER)
                run = self.add_run(paragraph, title[language], bold=True)
                run.font.size = Pt(size)
        line = f"{self.document.id}" + (f" · Version {self.version}" if self.version else "")
        self.paragraph(line, align=WD_ALIGN_PARAGRAPH.CENTER)
        self.paragraph(
            f"Generated from the MUST requirement record on {datetime.date.today().isoformat()}",
            align=WD_ALIGN_PARAGRAPH.CENTER,
        )

    def change_record(self) -> None:
        """One row per release. An explanation longer than `change_record_limit` is cited in its
        row and printed in Appendix A (`change_record_details`)."""
        self.paragraph("Document Change Records", bold=True)
        rows = []
        for release in self.document.releases:
            text = explanation(release)
            if display_width(text) > change_record_limit:
                number = f"A.{len(self.change_details) + 1}"
                self.change_details.append((number, release))
                text = f"详见附录{number} (See Appendix {number})"
            rows.append(
                [
                    f"v{release.version}",
                    release.date.strftime("%Y/%m/%d"),
                    text,
                    self.vault.person_name(release.by) if release.by else "",
                ]
            )
        self.table(
            ["Version", "Issue Date", "Explanation", "Changed by"],
            rows,
            widths=change_record_widths,
        )

    def change_record_details(self) -> None:
        if not self.change_details:
            return
        self.page_break()
        self.heading("Appendix A. Document Change Records (附录A 文件修订记录)", 1)
        for number, release in self.change_details:
            self.heading(f"{number} v{release.version} ({release.date:%Y/%m/%d})", 2)
            self.localized_paragraphs(release.summary, level=None)
            self.localized_paragraphs(release.note, level=None)

    def front_matter(self) -> None:
        front = self.document.front
        self.change_record()
        self.paragraph("Responsibilities", bold=True)
        self.table(
            ["Role", "Name"],
            [
                [
                    role.role.get("en") or next(iter(role.role.values())),
                    self.vault.person_name(role.person),
                ]
                for role in front.roles
            ],
        )
        self.page_break()
        self.table_of_contents()
        self.page_break()
        glossary = self.vault.glossary.terms if self.vault.glossary else {}
        if front.acronyms:
            self.heading("Acronyms", 3)
            self.table(
                ["Acronyms", "Description", "中文"],
                [
                    [
                        f"**{entry.text or key}**",
                        (entry.expansion or {}).get("en", ""),
                        (entry.expansion or {}).get("zh", ""),
                    ]
                    for key in front.acronyms
                    if (entry := glossary.get(key))
                ],
                languages=["en", "en", "zh"],
            )
        if front.reference_documents:
            self.heading("Reference Documents", 3)
            rows = []
            for source_id in front.reference_documents:
                source = self.vault.records.get(source_id)
                if source is not None:
                    rows.append(
                        [
                            source.number or "TBD",
                            source.title.get("en", ""),
                            source.title.get("zh", ""),
                        ]
                    )
            self.table(["Document No.", "Description", "中文"], rows, languages=["en", "en", "zh"])
        if front.bibliography:
            self.paragraph("Publications cited in this document (本文件引用的文献)", bold=True)
            for entry in front.bibliography:
                self.paragraph(entry, level=0)
        self.page_break()

    def table_of_contents(self) -> None:
        """A paragraph that marks where the table of contents goes; `fill_table_of_contents`
        replaces it once every heading is known."""
        self.paragraph("TABLE OF CONTENTS", bold=True)
        self.contents_marker = self.word.add_paragraph()

    def fill_table_of_contents(self) -> None:
        """A TOC field whose result already lists every heading of levels 1 to 3, each linked to a
        bookmark on its heading. Word shows it as it is, without asking to update fields when the
        document opens. Page numbers appear when the field is updated (F9, or Update Field); with
        `update_fields_on_open`, Word instead rebuilds the table on opening, after asking."""
        marker = getattr(self, "contents_marker", None)
        if marker is None:
            return

        def field_run(kind: str | None, text: str | None = None):
            run = OxmlElement("w:r")
            if kind:
                element = OxmlElement("w:fldChar")
                element.set(qn("w:fldCharType"), kind)
            else:
                element = OxmlElement("w:instrText")
                element.set(qn("xml:space"), "preserve")
                element.text = text
            run.append(element)
            return run

        entries: list = []
        for level, text, bookmark in self.contents_entries:
            style = f"toc {level}"
            paragraph = self.word.add_paragraph(
                style=style if style in self.style_names() else None
            )
            self.runs(paragraph, text, "en")
            link = OxmlElement("w:hyperlink")
            link.set(qn("w:anchor"), bookmark)
            link.set(qn("w:history"), "1")
            for run in paragraph._p.findall(qn("w:r")):
                link.append(run)
            paragraph._p.append(link)
            entries.append(paragraph._p)
        if not entries:
            paragraph = self.word.add_paragraph()
            self.add_run(paragraph, "Update this field to build the table of contents.")
            entries.append(paragraph._p)
        first = entries[0]
        position = 1 if first.find(qn("w:pPr")) is not None else 0
        for offset, run in enumerate(
            (
                field_run("begin"),
                field_run(None, 'TOC \\o "1-3" \\h \\z \\u'),
                field_run("separate"),
            )
        ):
            first.insert(position + offset, run)
        closing = self.word.add_paragraph()
        closing._p.append(field_run("end"))
        entries.append(closing._p)
        for element in entries:
            marker._p.addprevious(element)
        marker._p.getparent().remove(marker._p)
        if self.update_fields_on_open:
            self.request_field_update()

    def request_field_update(self) -> None:
        settings = self.word.settings.element
        update = settings.find(qn("w:updateFields"))
        if update is None:
            update = OxmlElement("w:updateFields")
            following = next(
                (child for child in settings if child.tag in settings_after_update), None
            )
            if following is not None:
                following.addprevious(update)
            else:
                settings.append(update)
        update.set(qn("w:val"), "true")

    def page_break(self) -> None:
        self.word.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    def heading(self, text: str, level: int) -> None:
        style = f"Heading {min(level, 5)}"
        paragraph = self.word.add_paragraph(style=style if style in self.style_names() else None)
        self.runs(paragraph, text, "en")
        if level <= 3:
            number = len(self.contents_entries) + 1
            bookmark = f"_Toc{number:08d}"
            start = OxmlElement("w:bookmarkStart")
            start.set(qn("w:id"), str(number))
            start.set(qn("w:name"), bookmark)
            end = OxmlElement("w:bookmarkEnd")
            end.set(qn("w:id"), str(number))
            first_run = paragraph._p.find(qn("w:r"))
            if first_run is not None:
                first_run.addprevious(start)
            else:
                paragraph._p.append(start)
            paragraph._p.append(end)
            self.contents_entries.append((level, text, bookmark))

    def outline(self, blocks: list[Block], depth: int) -> None:
        for block in blocks:
            if block.section is not None:
                number = self.numbering.sections[block.section.key]
                title = self.bilingual_title(block.section.title)
                self.heading(f"{number}. {title}" if depth == 1 else f"{number} {title}", depth)
                self.outline(block.section.blocks, depth + 1)
            elif block.text is not None:
                self.localized_paragraphs(block.text, level=None)
            elif block.requirement:
                record = self.vault.records.get(block.requirement)
                if isinstance(record, Requirement):
                    self.requirement(record, depth)
            elif block.figure:
                record = self.vault.records.get(block.figure)
                if isinstance(record, Figure):
                    self.figure(record)
            elif block.table is not None:
                if block.table.caption:
                    self.caption_paragraphs(block.table.caption)
                header = [
                    cell.get("en") or next(iter(cell.values())) for cell in block.table.header
                ]
                rows = [
                    [
                        "\n".join(
                            cell.get(language, "")
                            for language in ("en", "zh")
                            if cell.get(language)
                        )
                        for cell in row
                    ]
                    for row in block.table.rows
                ]
                self.table(header, rows)
            elif block.definitions is not None:
                if block.definitions.caption:
                    self.caption_paragraphs(block.definitions.caption)
                self.definitions(block.definitions.terms)

    def requirement(self, record: Requirement, depth: int) -> None:
        number = self.numbering.requirements.get(record.id, "")
        self.heading(f"{number} {record.id} {self.bilingual_title(record.title)}", depth)
        for name, label in part_labels:
            value = getattr(record, name)
            if value and name == "statement" and record.values:
                value = {
                    language: substitute_slots(text, record.values, language)
                    for language, text in value.items()
                }
            if value:
                self.paragraph(label, level=0)
                self.localized_paragraphs(value, level=1)
        if record.verification:
            self.paragraph(verification_label, level=0)
            self.localized_paragraphs(record.verification.criteria, level=1)

    def figure(self, record: Figure) -> None:
        folder = self.vault.files[record.id].parent
        width = self.text_width()
        embedded = False
        for image in record.files:
            path = folder / image.path
            if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".bmp") and path.exists():
                paragraph = self.word.add_paragraph()
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                native = DocxImage.from_file(str(path)).width
                paragraph.add_run().add_picture(str(path), width=min(native, width))
                embedded = True
                break
        if not embedded:
            names = ", ".join(image.path for image in record.files) or "no file"
            self.paragraph(
                f"[Image not embedded in Word ({names}); see the HTML version of {record.id}.]",
                align=WD_ALIGN_PARAGRAPH.CENTER,
            )
        number = self.numbering.figures.get(record.id)
        labels = (
            {"en": f"Figure {number}. ", "zh": f"图{number} "} if number else {"en": "", "zh": ""}
        )
        for language, prefix in labels.items():
            if language in record.caption:
                paragraph = self.paragraph(style="Caption")
                self.add_run(paragraph, prefix, bold=True)
                self.runs(paragraph, record.caption[language], language)

    def caption_paragraphs(self, caption: dict) -> None:
        for language in ("en", "zh"):
            if language in caption:
                paragraph = self.paragraph(style="Caption")
                self.runs(paragraph, caption[language], language)

    def definitions(self, terms: list[str]) -> None:
        glossary = self.vault.glossary.terms if self.vault.glossary else {}
        entries = [(key, glossary[key]) for key in terms if key in glossary]
        if not entries:
            return
        if all(entry.kind == "symbol" for _, entry in entries):
            rows = [
                [
                    entry.text or key,
                    "\n".join(
                        text
                        for text in (
                            (entry.definition or {}).get("en"),
                            (entry.definition or {}).get("zh"),
                        )
                        if text
                    ),
                ]
                for key, entry in entries
            ]
            self.table(["**Symbol**", "**Meaning**"], rows)
        else:
            rows = [
                [
                    (entry.expansion or {}).get("en", key),
                    (entry.definition or {}).get("en", ""),
                    (entry.definition or {}).get("zh", ""),
                ]
                for key, entry in entries
            ]
            self.table(["Term", "Definition", "中文"], rows, languages=["en", "en", "zh"])

    def header_and_footer(self) -> None:
        section = self.word.sections[0]
        header = (
            section.header.paragraphs[0]
            if section.header.paragraphs
            else section.header.add_paragraph()
        )
        header.text = ""
        title = self.document.title.get("en", self.document.id)
        self.add_run(
            header,
            f"{self.document.id} · {title}" + (f" · Ver. {self.version}" if self.version else ""),
        )
        footer = (
            section.footer.paragraphs[0]
            if section.footer.paragraphs
            else section.footer.add_paragraph()
        )
        footer.text = ""
        footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = footer.add_run()
        for kind, text in (("begin", None), (None, "PAGE"), ("end", None)):
            if kind:
                element = OxmlElement("w:fldChar")
                element.set(qn("w:fldCharType"), kind)
            else:
                element = OxmlElement("w:instrText")
                element.set(qn("xml:space"), "preserve")
                element.text = text
            run._r.append(element)

    def properties(self) -> None:
        """Document properties: the document number, title, version and, for an issued copy, the
        release tag (docs/SPEC.md §5.5)."""
        properties = self.word.core_properties
        properties.identifier = self.document.id
        properties.title = next(iter(self.document.title.values()), self.document.id)
        properties.version = self.version or ""
        properties.comments = f"release tag {self.tag}" if self.tag else ""

    def render(self, output: Path) -> Path:
        self.cover()
        self.page_break()
        self.front_matter()
        self.outline(self.document.outline, 1)
        self.change_record_details()
        self.fill_table_of_contents()
        self.header_and_footer()
        self.properties()
        output.parent.mkdir(parents=True, exist_ok=True)
        self.word.save(str(output))
        problems = check_package(output)
        if problems:
            raise ValueError(f"{output.name}: " + "; ".join(problems))
        return output


def check_package(path: Path) -> list[str]:
    """Problems that make Word report unreadable content: directory entries in the ZIP package and
    non-integer table widths."""
    problems = []
    with zipfile.ZipFile(path) as package:
        for info in package.infolist():
            if info.filename.endswith("/"):
                problems.append(f"directory entry {info.filename}")
        document = package.read("word/document.xml").decode("utf-8")
        if re.search(r'w:w="\d+\.\d+"', document):
            problems.append("table widths must be integers")
    return problems


def render_docx(
    vault: Vault,
    document_id: str,
    output: Path,
    version: str | None = None,
    update_fields_on_open: bool = False,
    tag: str | None = None,
) -> Path:
    document = vault.records.get(document_id)
    if not isinstance(document, Document):
        raise ValueError(f"no document {document_id}")
    template = vault.root / "templates" / "reference.docx"
    fonts = (vault.config.documents or {}) if vault.config else {}
    renderer = WordRenderer(
        vault,
        document,
        version,
        template,
        fonts.get("latin_font"),
        fonts.get("east_asian_font"),
        update_fields_on_open,
        tag,
    )
    return renderer.render(output)
