"""Static HTML site (docs/SPEC.md §12.1): works offline from a folder; no external resources."""

import datetime
import json
import shutil
from collections import Counter
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape
from markupsafe import Markup

from qingsong import __version__, checks
from qingsong.findings import Finding
from qingsong.render.model import (
    children_of,
    documents_of,
    number_document,
    requirement_documents,
    tree_data,
)
from qingsong.render.text import blocks, inline, substitute_slots
from qingsong.schema import Document, Figure, Requirement
from qingsong.vault import Vault

static_dir = Path(__file__).parent / "static"
record_pages = {"requirement": "r", "figure": "f"}
register_types = (
    "issue",
    "decision",
    "source",
    "condition",
    "quantity",
    "interface",
    "verification",
    "waiver",
    "baseline",
)
words = {
    "en": {"section": "Section", "figure": "Figure"},
    "zh": {"section": "第{}节", "figure": "图"},
}


class Site:
    def __init__(self, vault: Vault, output: Path):
        self.vault = vault
        self.output = output
        self.findings: list[Finding] = checks.run(vault)
        self.by_record: dict[str, list[Finding]] = {}
        for finding in self.findings:
            if finding.record:
                self.by_record.setdefault(finding.record, []).append(finding)
        self.children = children_of(vault)
        self.in_documents = requirement_documents(vault)
        self.documents = documents_of(vault)
        self.numberings = {document.id: number_document(document) for document in self.documents}
        self.figure_document = {
            figure: document_id
            for document_id, numbering in self.numberings.items()
            for figure in numbering.figures
        }
        self.languages = (
            (vault.config.languages.reference, vault.config.languages.second)
            if vault.config
            else ("en", "zh")
        )
        self.environment = Environment(
            loader=PackageLoader("qingsong.render", "templates"),
            autoescape=select_autoescape(["html"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    # links and text -------------------------------------------------------------------------
    def href(self, record_id: str, prefix: str) -> str:
        record = self.vault.records.get(record_id)
        if record is None:
            return ""
        if record.type in record_pages:
            return f"{prefix}{record_pages[record.type]}/{record_id}.html"
        if isinstance(record, Document):
            return f"{prefix}documents/{record_id}.html"
        return f"{prefix}registers.html#{record_id}"

    def resolver(self, prefix: str, document: Document | None):
        numbering = self.numberings.get(document.id) if document else None

        def resolve(target: str, key: str | None, language: str) -> tuple[str, str | None]:
            record = self.vault.records.get(target)
            if record is None:
                return f"[[{target}]]", None
            if key:
                other = self.numberings.get(target)
                number = other.sections.get(key, "?") if other else "?"
                label = (
                    f"Section {number}"
                    if language == "en"
                    else words["zh"]["section"].format(number)
                )
                local = document is not None and target == document.id
                return label, f"#{key}" if local else f"{prefix}documents/{target}.html#{key}"
            if isinstance(record, Figure):
                number = numbering.figures.get(target) if numbering else None
                if number is None and target in self.figure_document:
                    number = self.numberings[self.figure_document[target]].figures[target]
                label = (
                    (f"Figure {number}" if language == "en" else f"图{number}")
                    if number
                    else target
                )
                return (
                    label,
                    f"#{target}"
                    if numbering and target in numbering.figures
                    else self.href(target, prefix),
                )
            return target, self.href(target, prefix)

        return resolve

    def text(
        self,
        value: dict | None,
        prefix: str,
        document: Document | None = None,
        block: bool = True,
        values: dict | None = None,
    ) -> Markup:
        if not value:
            return Markup("")
        if values:
            value = {
                language: substitute_slots(text, values, language)
                for language, text in value.items()
            }
        resolve = self.resolver(prefix, document)
        parts = []
        for language in self.languages:
            if language in value:
                body = (
                    blocks(value[language], language, resolve)
                    if block
                    else inline(value[language], language, resolve)
                )
                tag = "div" if block else "span"
                parts.append(f'<{tag} class="lang {language}" lang="{language}">{body}</{tag}>')
            else:
                tag = "div" if block else "span"
                fallback = next(iter(value.values()))
                body = (
                    blocks(fallback, language, resolve)
                    if block
                    else inline(fallback, language, resolve)
                )
                parts.append(
                    f'<{tag} class="lang {language} missing" title="no {language} text">'
                    f"{body}</{tag}>"
                )
        return Markup("".join(parts))

    def caption(
        self, figure: Figure, number: str | None, prefix: str, document: Document | None
    ) -> Markup:
        """One block per language: the numbered label followed by the caption in that language."""
        resolve = self.resolver(prefix, document)
        parts = []
        for language in self.languages:
            label = ""
            if number:
                label = f"Figure {number}." if language == "en" else f"图{number}"
            text = figure.caption.get(language)
            missing = "" if text else " missing"
            body = inline(text or next(iter(figure.caption.values())), language, resolve)
            parts.append(
                f'<div class="lang {language}{missing}" lang="{language}"><b>{label}</b> {body}</div>'
            )
        return Markup("".join(parts))

    def plain(self, value: dict | None, language: str = "en") -> str:
        if not value:
            return ""
        return value.get(language) or next(iter(value.values()))

    # pages ----------------------------------------------------------------------------------
    def render(self, template: str, target: str, prefix: str, **context) -> None:
        page = self.environment.get_template(template).render(
            site=self,
            prefix=prefix,
            vault=self.vault,
            version=__version__,
            generated=datetime.date.today().isoformat(),
            **context,
        )
        path = self.output / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(page, encoding="utf-8")

    def build(self) -> Path:
        if self.output.exists():
            shutil.rmtree(self.output)
        self.output.mkdir(parents=True)
        shutil.copytree(static_dir, self.output / "static")
        self.copy_images()
        requirements = sorted(
            (record for record in self.vault.records.values() if isinstance(record, Requirement)),
            key=lambda record: record.id,
        )
        severity = Counter(finding.severity for finding in self.findings)
        maturity = Counter(
            record.maturity for record in requirements if record.lifecycle == "current"
        )
        levels = Counter(record.level for record in requirements if record.lifecycle == "current")
        open_issues = [
            record
            for record in self.vault.records.values()
            if record.type == "issue" and record.status == "open"
        ]
        events = sorted(
            ((event, record) for record in self.vault.records.values() for event in record.history),
            key=lambda item: (item[0].date, item[1].id),
            reverse=True,
        )[:15]
        self.render(
            "index.html",
            "index.html",
            "",
            requirements=requirements,
            severity=severity,
            maturity=maturity,
            levels=levels,
            open_issues=open_issues,
            events=events,
            documents=self.documents,
        )
        self.render(
            "tree.html", "tree.html", "", tree=json.dumps(tree_data(self.vault), ensure_ascii=False)
        )
        self.render(
            "flow.html",
            "flow.html",
            "",
            flow=json.dumps(self.flow_data(requirements), ensure_ascii=False),
        )
        for document in self.documents:
            self.render(
                "document.html",
                f"documents/{document.id}.html",
                "../",
                document=document,
                numbering=self.numberings[document.id],
            )
        for requirement in requirements:
            self.render("requirement.html", f"r/{requirement.id}.html", "../", record=requirement)
        for figure in (
            record for record in self.vault.records.values() if isinstance(record, Figure)
        ):
            self.render("figure.html", f"f/{figure.id}.html", "../", record=figure)
        registers = {
            kind: sorted(
                (record for record in self.vault.records.values() if record.type == kind),
                key=lambda record: record.id,
            )
            for kind in register_types
        }
        self.render("registers.html", "registers.html", "", registers=registers)
        rules = checks.all_rule_summaries()
        grouped: dict[str, list[Finding]] = {}
        for finding in self.findings:
            grouped.setdefault(finding.rule, []).append(finding)
        self.render(
            "checks.html", "checks.html", "", grouped=grouped, rules=rules, severity=severity
        )
        self.write_search_index(requirements)
        return self.output / "index.html"

    def copy_images(self) -> None:
        for record in self.vault.records.values():
            if isinstance(record, Figure):
                folder = self.vault.files[record.id].parent
                for image in record.files:
                    target = self.output / "images" / image.path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if (folder / image.path).exists():
                        shutil.copyfile(folder / image.path, target)

    def flow_data(self, requirements: list[Requirement]) -> dict:
        levels = (
            [{"name": level.name, "names": level.names} for level in self.vault.config.levels]
            if self.vault.config
            else []
        )
        nodes = [
            {
                "id": record.id,
                "title": record.title,
                "level": record.level,
                "allocated": record.allocated_to,
                "maturity": record.maturity,
                "parents": [link.id for link in record.derives_from],
                "suspect": [
                    link.id
                    for link in record.derives_from
                    if link.id in self.vault.records
                    and link.normative_revision < self.vault.records[link.id].normative_revision
                ],
                "url": f"r/{record.id}.html",
            }
            for record in requirements
            if record.lifecycle == "current"
        ]
        return {"levels": levels, "nodes": nodes}

    def write_search_index(self, requirements: list[Requirement]) -> None:
        entries = []
        for record in self.vault.records.values():
            if record.type not in (
                "requirement",
                "figure",
                "issue",
                "decision",
                "source",
                "document",
            ):
                continue
            texts = []
            for name in ("title", "statement", "caption", "description"):
                value = getattr(record, name, None)
                if isinstance(value, dict):
                    texts.extend(value.values())
            entries.append(
                {
                    "id": record.id,
                    "type": record.type,
                    "title": self.plain(record.title),
                    "title_zh": record.title.get("zh", ""),
                    "aliases": [alias.id for alias in record.aliases],
                    "text": " ".join(texts)[:600],
                    "url": self.href(record.id, ""),
                }
            )
        (self.output / "static" / "search_index.js").write_text(
            "window.QINGSONG_INDEX = " + json.dumps(entries, ensure_ascii=False) + ";\n",
            encoding="utf-8",
        )


def render_site(vault: Vault, output: Path) -> Path:
    return Site(vault, output).build()
