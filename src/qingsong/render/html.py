"""Static HTML site (docs/SPEC.md §12.1): works offline from a folder; no external resources."""

import datetime
import difflib
import html
import json
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jinja2 import Environment, PackageLoader, select_autoescape
from markupsafe import Markup

from qingsong import __version__, checks, gitutil, ids
from qingsong.checks.content import numbers_in_text, requirement_form
from qingsong.findings import Finding
from qingsong.hashing import field_value, proposal_hash
from qingsong.operations import OperationError
from qingsong.render.model import (
    children_of,
    documents_of,
    number_document,
    requirement_documents,
    tree_data,
)
from qingsong.render.text import blocks, format_slot, inline, substitute_slots
from qingsong.review import kind_labels
from qingsong.schema import (
    Document,
    Figure,
    Issue,
    Proposal,
    ProposedChange,
    Requirement,
    ValueSlot,
)
from qingsong.vault import Vault

if TYPE_CHECKING:
    from qingsong.release import ChangeSummary

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
field_labels = {
    "title": {"en": "Title", "zh": "标题"},
    "statement": {"en": "Requirement", "zh": "需求"},
    "rationale": {"en": "Rationale", "zh": "原因"},
    "notes": {"en": "Notes", "zh": "说明"},
    "suggestions": {"en": "Suggestions", "zh": "建议"},
    "verification.criteria": {"en": "Verification", "zh": "验收方式"},
}
state_labels = {"proposed": "Fix proposed", "open": "Open", "closed": "Closed"}
diff_token = re.compile(r"\s+|[A-Za-z0-9_]+|[^\sA-Za-z0-9_]")


def diff_markup(old: str, new: str) -> Markup:
    """Word-level difference (character level for Chinese): deleted text struck, new text marked."""
    before, after = diff_token.findall(old), diff_token.findall(new)
    parts = []
    matcher = difflib.SequenceMatcher(None, before, after, autojunk=False)
    for operation, start, end, new_start, new_end in matcher.get_opcodes():
        removed = html.escape("".join(before[start:end]))
        added = html.escape("".join(after[new_start:new_end]))
        if operation == "equal":
            parts.append(removed)
            continue
        if removed:
            parts.append(f"<del>{removed}</del>")
        if added:
            parts.append(f"<ins>{added}</ins>")
    return Markup("".join(parts).replace("\n", "<br>"))


def script_json(data) -> str:
    """JSON that is safe inside a <script> element."""
    text = json.dumps(data, ensure_ascii=False)
    for character, escaped in (
        ("<", "\\u003c"),
        (">", "\\u003e"),
        ("&", "\\u0026"),
        ("\u2028", "\\u2028"),
        ("\u2029", "\\u2029"),
    ):
        text = text.replace(character, escaped)
    return text


class Site:
    def __init__(self, vault: Vault, output: Path):
        self.vault = vault
        self.output = output
        self.findings: list[Finding] = checks.run(vault)
        self.by_record: dict[str, list[Finding]] = {}
        for finding in self.findings:
            if finding.record:
                self.by_record.setdefault(finding.record, []).append(finding)
        self.issues = sorted(
            (record for record in vault.records.values() if isinstance(record, Issue)),
            key=lambda record: ids.sort_key(record.id),
        )
        self.issues_by_record: dict[str, list[Issue]] = {}
        for issue in self.issues:
            targets = [*issue.records]
            targets += [
                change.record for proposal in issue.proposals or [] for change in proposal.changes
            ]
            for target in dict.fromkeys(targets):
                self.issues_by_record.setdefault(target, []).append(issue)
        for record in vault.records.values():
            if isinstance(record, Requirement):
                listed = [*record.issues, *(slot.issue for slot in record.values.values())]
                for issue_id in dict.fromkeys(item for item in listed if item):
                    issue = vault.records.get(issue_id)
                    known = self.issues_by_record.setdefault(record.id, [])
                    if isinstance(issue, Issue) and issue not in known:
                        known.append(issue)
        self.untracked: dict[str, list[Finding]] = {}
        for finding in self.findings:
            if finding.record and finding.issue is None and finding.severity != "info":
                self.untracked.setdefault(finding.record, []).append(finding)
        self.kind_labels = kind_labels
        self.field_labels = field_labels
        self.state_labels = state_labels
        self.children = children_of(vault)
        self.in_documents = requirement_documents(vault)
        self.documents = documents_of(vault)
        self.numberings = {document.id: number_document(document) for document in self.documents}
        self.changes = change_summaries(vault)
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
        if isinstance(record, Issue):
            return f"{prefix}review.html#{record_id}"
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

    def slot_text(self, slot) -> str:
        return format_slot(slot, "en").replace("\\", "")

    # review --------------------------------------------------------------------------------
    def issue_state(self, issue: Issue) -> str:
        if issue.status == "closed":
            return "closed"
        if any(proposal.status == "proposed" for proposal in issue.proposals or []):
            return "proposed"
        return "open"

    def open_issues_of(self, record_id: str) -> list[Issue]:
        return [
            issue for issue in self.issues_by_record.get(record_id, []) if issue.status == "open"
        ]

    def proposal_hash(self, proposal: Proposal) -> str:
        return proposal_hash(proposal)

    def open_proposals(self, issue: Issue) -> list[Proposal]:
        return [proposal for proposal in issue.proposals or [] if proposal.status == "proposed"]

    def issue_documents(self, issue: Issue) -> list[str]:
        found: dict[str, None] = {}
        for record_id in issue.records:
            for document_id in self.in_documents.get(record_id, []):
                found[document_id] = None
        return list(found)

    def record_link(self, record_id: str, prefix: str) -> str:
        """A requirement inside a document opens at its place in the document."""
        documents = self.in_documents.get(record_id, [])
        if documents:
            return f"{prefix}documents/{documents[0]}.html#{record_id}"
        return self.href(record_id, prefix)

    def change_diff(self, change: ProposedChange, language: str) -> Markup:
        """The difference as a reader sees it: references shown by their labels."""
        record = self.vault.records.get(change.record)
        current = field_value(record, change.field) if record is not None else None
        old = current.get(language, "") if isinstance(current, dict) else ""
        resolve = self.resolver("", None)

        def readable(text: str) -> str:
            return ids.reference_pattern.sub(
                lambda match: resolve(match.group(1), match.group(2), language)[0], text
            )

        return diff_markup(readable(old), readable(change.text.get(language, "")))

    form_labels = {
        "quantitative": {"en": "Quantitative", "zh": "定量"},
        "qualitative": {"en": "Qualitative", "zh": "定性"},
    }

    def form(self, record: Requirement) -> str:
        return requirement_form(record)

    def numbers_in_text(self, record: Requirement) -> bool:
        return bool(numbers_in_text(record))

    def form_hint(self, record: Requirement) -> str:
        if record.values:
            return f"values in slots: {', '.join(record.values)}; checks and the export read them"
        if numbers_in_text(record):
            return "numbers are written in the text; checks and the export do not read them"
        return "no numeric value; verified by its criteria"

    def is_text(self, value: Any) -> bool:
        """Bilingual text: a non-empty mapping from language codes to strings."""
        return (
            isinstance(value, dict)
            and bool(value)
            and set(value) <= set(self.languages)
            and all(isinstance(item, str) for item in value.values())
        )

    def field_diff(
        self,
        before: Any,
        after: Any,
        language: str,
        values_before: dict | None = None,
        values_after: dict | None = None,
    ) -> Markup:
        """Word-level difference of one language of a changed text field. With value slots given,
        the texts are compared as a reader sees them, with the values filled in."""
        old = before.get(language, "") if isinstance(before, dict) else ""
        new = after.get(language, "") if isinstance(after, dict) else ""
        if values_before is not None or values_after is not None:
            old = self.filled(old, values_before or {}, language)
            new = self.filled(new, values_after or {}, language)
        return diff_markup(old, new)

    def filled(self, text: str, values: dict, language: str) -> str:
        slots = {}
        for name, fields in values.items():
            try:
                slots[name] = ValueSlot.model_validate(fields)
            except ValueError:
                continue
        return re.sub(r"\\(.)", r"\1", substitute_slots(text, slots, language))

    def as_text(self, value: Any) -> str:
        if value is None:
            return "—"
        return json.dumps(value, ensure_ascii=False, indent=1, default=str)

    def blocks_text(self, blocks: list[dict], language: str) -> str:
        """The readable text of a section's own blocks, for a before/after difference."""
        lines: list[str] = []
        for block in blocks:
            if "text" in block:
                lines.append(block["text"].get(language, ""))
            elif "table" in block:
                table = block["table"]
                for row in [table.get("header", []), *table.get("rows", [])]:
                    lines.append(" | ".join(cell.get(language, "") for cell in row))
            elif "definitions" in block:
                lines.append(", ".join(block["definitions"].get("terms", [])))
        return "\n".join(lines)

    def blocks_diff(self, before: list[dict], after: list[dict], language: str) -> Markup:
        return diff_markup(self.blocks_text(before, language), self.blocks_text(after, language))

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
        open_issues = [issue for issue in self.issues if issue.status == "open"]
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
        self.render("tree.html", "tree.html", "", tree=script_json(tree_data(self.vault)))
        self.render(
            "flow.html",
            "flow.html",
            "",
            flow=script_json(self.flow_data(requirements)),
        )
        for document in self.documents:
            summary = self.changes.get(document.id)
            if summary is not None and not isinstance(summary, str):
                self.render(
                    "changes.html",
                    f"documents/{document.id}-changes.html",
                    "../",
                    document=document,
                    summary=summary,
                )
            else:
                summary = None
            self.render(
                "document.html",
                f"documents/{document.id}.html",
                "../",
                document=document,
                numbering=self.numberings[document.id],
                summary=summary,
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
        order = {"proposed": 0, "open": 1, "closed": 2}
        reviewed = sorted(
            self.issues,
            key=lambda issue: (order[self.issue_state(issue)], ids.sort_key(issue.id)),
        )
        kinds = Counter(issue.kind for issue in self.issues if issue.status == "open")
        states = Counter(self.issue_state(issue) for issue in self.issues)
        untracked_by_rule: dict[str, list[Finding]] = {}
        for findings in self.untracked.values():
            for finding in findings:
                untracked_by_rule.setdefault(finding.rule, []).append(finding)
        self.render(
            "review.html",
            "review.html",
            "",
            issues=reviewed,
            kinds=kinds,
            states=states,
            untracked_by_rule=dict(sorted(untracked_by_rule.items())),
            rules=checks.all_rule_summaries(),
        )
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
                    target = self.output / "images" / record.id / image.path
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
            "window.QINGSONG_INDEX = " + script_json(entries) + ";\n",
            encoding="utf-8",
        )


def change_summaries(vault: Vault) -> "dict[str, ChangeSummary | str]":
    """Each document's changes since its last tagged release, or why there is no summary."""
    from qingsong.release import summaries_since_last_release

    if not gitutil.is_repository(vault.root):
        return {}
    try:
        return summaries_since_last_release(vault.root, vault)
    except OperationError:
        return {}


def render_site(vault: Vault, output: Path) -> Path:
    """Write the static HTML site into `output` (replaced) and return the path of its index page."""
    return Site(vault, output).build()
