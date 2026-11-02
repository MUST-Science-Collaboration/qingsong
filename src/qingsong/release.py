"""Releases of documents and their change summaries (docs/SPEC.md §5.5).

A release is prepared on a branch (`prepare`), reviewed and merged like any other change, and then
tagged at the commit of the main branch that first contains it (`tag_release`). The change summary
(`changes`) compares a document between two states of the vault."""

import datetime
import re
from dataclasses import asdict, dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.error import YAMLError

from qingsong import __version__, gitutil
from qingsong.hashing import field_value, text_hash
from qingsong.operations import (
    OperationError,
    edit,
    history_event,
    require_person,
    today_date,
    translation_fields,
)
from qingsong.schema import Block, Document, RecordBase, plain
from qingsong.vault import Vault, load, vault_at

version_pattern = re.compile(r"^\d+(\.\d+)*$")
content_fields: dict[str, tuple[str, ...]] = {
    "requirement": (
        "title",
        "statement",
        "values",
        "rationale",
        "notes",
        "suggestions",
        "justification",
        "justified_by",
        "level",
        "allocated_to",
        "interface",
        "verification",
        "variants",
    ),
    "figure": ("title", "caption", "alt", "files"),
}
link_fields = ("derives_from", "constrained_by")
front_fields = ("title", "scope", "front")


def parse_version(version: str) -> tuple[int, ...]:
    if not version_pattern.match(version):
        raise OperationError(f"version {version!r} must be dotted numbers, such as 1.2")
    return tuple(int(part) for part in version.split("."))


def tag_name(document_id: str, version: str) -> str:
    return f"release/{document_id}/{version}"


def require_document(vault: Vault, document_id: str) -> Document:
    document = vault.records.get(document_id)
    if not isinstance(document, Document):
        raise OperationError(f"no document {document_id} (or it does not load; run qingsong check)")
    return document


def outline_records(blocks: list[Block]) -> list[str]:
    """Requirement and figure IDs in outline order."""
    found: list[str] = []
    for block in blocks:
        if block.section is not None:
            found.extend(outline_records(block.section.blocks))
        elif block.requirement:
            found.append(block.requirement)
        elif block.figure:
            found.append(block.figure)
    return found


def section_texts(blocks: list[Block], key: str = "", title: Any = None) -> dict[str, dict]:
    """Section key → its title and its own text, table and definitions blocks (records excluded).
    Blocks outside any section are kept under the empty key."""
    own = [
        block.model_dump(mode="json", exclude_none=True)
        for block in blocks
        if block.section is None and not block.requirement and not block.figure
    ]
    result = {key: {"title": title, "blocks": own}}
    for block in blocks:
        if block.section is not None:
            result.update(
                section_texts(block.section.blocks, block.section.key, block.section.title)
            )
    return result


def release_blockers(vault: Vault, document: Document) -> list[str]:
    """Why the document cannot be released from this state: errors on the document or on the
    records of its outline, integrity errors anywhere, and translations not reviewed."""
    from qingsong import checks

    scope = {document.id, *outline_records(document.outline)}
    reasons = [
        f"{finding.rule} {finding.record or finding.file or 'vault'}: {finding.message}"
        for finding in checks.run(vault)
        if finding.severity == "error"
        and (finding.rule.startswith("integrity.") or finding.record in scope)
    ]
    if vault.config is not None:
        languages = {vault.config.languages.reference, vault.config.languages.second}
        for record_id in dict.fromkeys(outline_records(document.outline)):
            record = vault.records.get(record_id)
            if record is None or record.lifecycle != "current":
                continue
            origin = getattr(record, "text_origin", None)
            states = getattr(record, "translation", {}) or {}
            for name in translation_fields(vault, record.type):
                value = field_value(record, name)
                if not isinstance(value, dict) or not value:
                    continue
                if not languages <= set(value):
                    reasons.append(f"{record_id}: {name} exists in one language only")
                    continue
                state = states.get(name)
                if (
                    state is None
                    or state.status != "reviewed"
                    or origin not in value
                    or state.source_hash != text_hash(value[origin])
                ):
                    reasons.append(f"{record_id}: the translation of {name} is not reviewed")
    return reasons


def on_main(root: Path, document_path: str, version: str) -> bool:
    return any(
        has_release(gitutil.read_at(root, ref, document_path), version)
        for ref in gitutil.main_refs(root)
    )


def has_release(text: str | None, version: str) -> bool:
    if not text:
        return False
    try:
        data = plain(YAML(typ="safe", pure=True).load(StringIO(text)))
    except YAMLError:
        return False
    if not isinstance(data, dict):
        return False
    return any(
        isinstance(entry, dict) and str(entry.get("version")) == version
        for entry in data.get("releases") or []
    )


def prepare(
    root: Path,
    document_id: str,
    version: str,
    person: str,
    summary: dict[str, str],
    release_date: datetime.date | None = None,
    note: dict[str, str] | None = None,
    via: str | None = None,
    today: datetime.date | None = None,
) -> Document:
    """Write the release entry (step 1 of §5.5). Refuses with every reason at once."""
    today = today_date(today)
    vault = load(root)
    require_person(vault, person)
    if not vault.is_approver(person):
        raise OperationError(f"{person} is not an approver (people.yaml)")
    document = require_document(vault, document_id)
    key = parse_version(version)
    entries = document.releases
    replacing = bool(entries) and entries[-1].version == version
    document_path = vault.relative(vault.files[document_id])
    if replacing:
        if not entries[-1].made_with_qingsong:
            raise OperationError(f"version {version} was released before qingsong")
        if on_main(root, document_path, version):
            raise OperationError(
                f"version {version} is already on the main branch; a correction is a new version"
            )
    elif any(entry.version == version for entry in entries):
        raise OperationError(f"version {version} was already released")
    earlier = entries[:-1] if replacing else entries
    if earlier and key <= max(parse_version(entry.version) for entry in earlier):
        raise OperationError(
            f"version {version} must be higher than {', '.join(e.version for e in earlier)}"
        )
    release_date = release_date or today
    if earlier and release_date < earlier[-1].date:
        raise OperationError(f"date {release_date} is before the previous release")
    if vault.config is not None:
        missing = [
            language
            for language in (vault.config.languages.reference, vault.config.languages.second)
            if not (summary.get(language) or "").strip()
        ]
        if missing:
            raise OperationError(f"give the release summary in {', '.join(missing)}")
    blockers = release_blockers(vault, document)
    if blockers:
        raise OperationError(
            "the document cannot be released yet:\n  "
            + "\n  ".join(blockers[:40])
            + (f"\n  … and {len(blockers) - 40} more" if len(blockers) > 40 else "")
        )
    entry: dict[str, Any] = {"version": version, "date": release_date, "summary": dict(summary)}
    entry["by"] = person
    if note:
        entry["note"] = dict(note)
    entry["tag"] = tag_name(document_id, version)
    entry["made_with_qingsong"] = True
    entry["engine"] = __version__

    def change(data: CommentedMap, old: RecordBase) -> None:
        releases = data.setdefault("releases", [])
        if replacing:
            releases[-1] = entry
        else:
            releases.append(entry)
        data["revision"] = old.revision + 1
        verb = "prepared again" if replacing else "prepared"
        data["history"].append(
            history_event(
                old.revision + 1, today, person, "released", f"release {version} {verb}", via=via
            )
        )

    record = edit(vault, document_id, change)
    assert isinstance(record, Document)
    return record


def find_release_commit(root: Path, document_path: str, version: str) -> str:
    """The commit on the main branch's first-parent history that first contains the release."""
    found: set[str] = set()
    for ref in gitutil.main_refs(root):
        for commit in gitutil.first_parent_commits(root, ref, document_path):
            if has_release(gitutil.read_at(root, commit, document_path), version):
                found.add(commit)
                break
    if not found:
        raise OperationError(
            f"version {version} is not on the main branch yet; merge the release first"
        )
    if len(found) > 1:
        raise OperationError(
            "main and origin/main disagree about where the release entered; pull or push first"
        )
    return found.pop()


def tag_release(
    root: Path, document_id: str, version: str, at: str | None = None
) -> tuple[str, str]:
    """Create the release tag (step 2 of §5.5); return the tag and the commit it marks.

    A release made with qingsong is tagged at the commit that introduced it. A release made before
    qingsong is tagged at the commit given with `at`, where the record was verified against the
    issued document."""
    vault = load(root)
    document = require_document(vault, document_id)
    entry = next((item for item in document.releases if item.version == version), None)
    if entry is None:
        raise OperationError(f"{document_id} has no release {version}")
    tag = tag_name(document_id, version)
    if gitutil.tag_exists(root, tag):
        raise OperationError(f"the tag {tag} already exists")
    document_path = vault.relative(vault.files[document_id])
    if entry.made_with_qingsong:
        if at:
            raise OperationError(
                "a release made with qingsong is tagged where it entered the main branch; "
                "do not give --at"
            )
        commit = find_release_commit(root, document_path, version)
    else:
        if not at:
            raise OperationError(
                f"version {version} was released before qingsong: give --at COMMIT, the commit "
                "where the record was verified against the issued document"
            )
        commit = gitutil.commit_of(root, at) or ""
        if not commit:
            raise OperationError(f"git reference {at!r} not found")
        if not any(gitutil.is_ancestor(root, commit, ref) for ref in gitutil.main_refs(root)):
            raise OperationError(f"{at} is not on the main branch")
        if not has_release(gitutil.read_at(root, commit, document_path), version):
            raise OperationError(f"{document_id} at {at} does not list release {version}")
    if entry.made_with_qingsong:
        try:
            with vault_at(root, commit) as earlier:
                then = require_document(earlier, document_id)
                entry_then = next((e for e in then.releases if e.version == version), None)
                if entry_then is None or entry_then != entry:
                    raise OperationError(
                        f"the release entry changed after it reached main (at {commit[:12]})"
                    )
                blockers = release_blockers(earlier, then)
        except gitutil.GitError as error:
            raise OperationError(str(error)) from error
        if blockers:
            raise OperationError(
                f"the state at {commit[:12]} cannot be released:\n  " + "\n  ".join(blockers[:40])
            )
    summary = next(iter(entry.summary.values()), "")
    try:
        gitutil.create_tag(root, tag, commit, f"{document_id} {version}: {summary}")
    except gitutil.GitError as error:
        raise OperationError(str(error)) from error
    return tag, commit


@dataclass
class RecordChange:
    record: str
    type: str
    title: dict[str, str]
    kind: str
    fields: list[str] = field(default_factory=list)
    before: dict[str, Any] = field(default_factory=dict)
    after: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    maturity: list[str | None] | None = None
    lifecycle: list[str] | None = None
    superseded_by: list[str] = field(default_factory=list)
    aliases_added: list[str] = field(default_factory=list)
    aliases_removed: list[str] = field(default_factory=list)
    history_rewritten: bool = False


@dataclass
class SectionChange:
    key: str
    status: str
    title_before: dict[str, str] | None = None
    title_after: dict[str, str] | None = None
    blocks_before: list[dict] = field(default_factory=list)
    blocks_after: list[dict] = field(default_factory=list)


@dataclass
class ChangeSummary:
    document: str
    since: str
    since_ref: str
    until: str
    approximate: bool
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    moved: dict[str, list[str]] = field(default_factory=dict)
    revised: list[RecordChange] = field(default_factory=list)
    bookkeeping: list[RecordChange] = field(default_factory=list)
    sections: list[SectionChange] = field(default_factory=list)
    front_matter: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (
            self.added
            or self.removed
            or self.revised
            or self.bookkeeping
            or self.sections
            or self.front_matter
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def bookkeeping_groups(self) -> dict[str, list[str]]:
        """Bookkeeping changes grouped by what happened: note → record IDs."""
        groups: dict[str, list[str]] = {}
        for change in self.bookkeeping:
            note = "; ".join(status_lines(change, prefix="")) or ", ".join(
                sorted({str(event.get("event")) for event in change.events})
            )
            groups.setdefault(note or "recorded again", []).append(change.record)
        return groups

    def lines(self) -> list[str]:
        head = f"{self.document}: changes since {self.since} ({self.since_ref}), to {self.until}"
        lines = [head]
        if self.approximate:
            lines.append(
                "  approximate: the earlier release was made before qingsong; its tag marks the "
                "record as verified against the issued file"
            )
        if self.is_empty():
            return [*lines, "  no changes"]
        for record_id in self.added:
            lines.append(f"  added      {record_id}")
        for record_id in self.removed:
            moved = self.moved.get(record_id)
            where = f" (moved to {', '.join(moved)})" if moved else ""
            lines.append(f"  removed    {record_id}{where}")
        for change in self.revised:
            lines.append(f"  revised    {change.record}: {', '.join(change.fields) or 'links'}")
            for event in change.events:
                kind = event.get("change_class") or event.get("event")
                lines.append(f"               r{event['revision']} {kind}: {event['summary']}")
            lines.extend(status_lines(change))
        for section in self.sections:
            lines.append(
                f"  section    {section.key or '(before the first section)'} {section.status}"
            )
        for name in self.front_matter:
            lines.append(f"  front      {name} changed")
        if self.bookkeeping:
            lines.append(f"  bookkeeping on {len(self.bookkeeping)} records (approvals, reviews):")
            for note, records in self.bookkeeping_groups().items():
                lines.append(f"    {note}: {compact_ids(records)}")
        return lines


def compact_ids(record_ids: list[str]) -> str:
    if len(record_ids) <= 3:
        return ", ".join(record_ids)
    return f"{record_ids[0]} … {record_ids[-1]} ({len(record_ids)} records)"


def status_lines(change: RecordChange, prefix: str = "               ") -> list[str]:
    lines = []
    if change.maturity:
        lines.append(f"{prefix}maturity {change.maturity[0]} → {change.maturity[1]}")
    if change.lifecycle:
        successors = f" by {', '.join(change.superseded_by)}" if change.superseded_by else ""
        lines.append(f"{prefix}{change.lifecycle[0]} → {change.lifecycle[1]}{successors}")
    if change.aliases_added or change.aliases_removed:
        lines.append(
            f"{prefix}aliases +{change.aliases_added or '-'} −{change.aliases_removed or '-'}"
        )
    if change.history_rewritten:
        lines.append(f"{prefix}warning: the earlier history is not a prefix of the later one")
    return lines


def dump(record: RecordBase, name: str) -> Any:
    return field_value(record, name)


def compare_record(old: RecordBase, new: RecordBase) -> RecordChange | None:
    if old.stamp == new.stamp and old.revision == new.revision:
        return None
    names = content_fields.get(new.type, ("title",))
    changed = [name for name in names if dump(old, name) != dump(new, name)]
    for name in link_fields:
        before = {link.id for link in getattr(old, name, [])}
        after = {link.id for link in getattr(new, name, [])}
        if before != after:
            changed.append(name)
    old_history = [event.model_dump(mode="json", exclude_none=True) for event in old.history]
    new_history = [event.model_dump(mode="json", exclude_none=True) for event in new.history]
    change = RecordChange(
        record=new.id,
        type=new.type,
        title=dict(new.title),
        kind="revised" if changed else "bookkeeping",
        fields=changed,
        before={name: dump(old, name) for name in changed},
        after={name: dump(new, name) for name in changed},
        events=[event for event in new_history if event["revision"] > old.revision],
        history_rewritten=new_history[: len(old_history)] != old_history,
    )
    old_maturity, new_maturity = getattr(old, "maturity", None), getattr(new, "maturity", None)
    if old_maturity != new_maturity:
        change.maturity = [old_maturity, new_maturity]
    if old.lifecycle != new.lifecycle:
        change.lifecycle = [old.lifecycle, new.lifecycle]
        change.superseded_by = list(new.superseded_by)
    old_aliases = {alias.id for alias in old.aliases}
    new_aliases = {alias.id for alias in new.aliases}
    change.aliases_added = sorted(new_aliases - old_aliases)
    change.aliases_removed = sorted(old_aliases - new_aliases)
    if change.aliases_added or change.aliases_removed or change.lifecycle:
        change.kind = "revised"
    return change


def compare(
    document_id: str,
    earlier: Vault,
    later: Vault,
    since: str,
    since_ref: str,
    until: str,
    approximate: bool,
) -> ChangeSummary:
    summary = ChangeSummary(document_id, since, since_ref, until, approximate)
    new_document = require_document(later, document_id)
    old_document = earlier.records.get(document_id)
    old_outline = (
        outline_records(old_document.outline) if isinstance(old_document, Document) else []
    )
    new_outline = outline_records(new_document.outline)
    summary.added = [record_id for record_id in new_outline if record_id not in old_outline]
    summary.removed = [record_id for record_id in old_outline if record_id not in new_outline]
    for record_id in summary.removed:
        homes = [
            other.id
            for other in later.records.values()
            if isinstance(other, Document)
            and other.id != document_id
            and record_id in outline_records(other.outline)
        ]
        if homes:
            summary.moved[record_id] = sorted(homes)
    for record_id in dict.fromkeys(record for record in new_outline if record in old_outline):
        old, new = earlier.records.get(record_id), later.records.get(record_id)
        if old is None or new is None:
            continue
        change = compare_record(old, new)
        if change is None:
            continue
        (summary.revised if change.kind == "revised" else summary.bookkeeping).append(change)
    old_sections = section_texts(old_document.outline) if isinstance(old_document, Document) else {}
    new_sections = section_texts(new_document.outline)
    for key in dict.fromkeys([*new_sections, *old_sections]):
        before, after = old_sections.get(key), new_sections.get(key)
        if before == after:
            continue
        if key == "" and not (before or {}).get("blocks") and not (after or {}).get("blocks"):
            continue
        status = "added" if before is None else "removed" if after is None else "changed"
        summary.sections.append(
            SectionChange(
                key=key,
                status=status,
                title_before=(before or {}).get("title"),
                title_after=(after or {}).get("title"),
                blocks_before=(before or {}).get("blocks", []),
                blocks_after=(after or {}).get("blocks", []),
            )
        )
    if isinstance(old_document, Document):
        for name in front_fields:
            if dump(old_document, name) != dump(new_document, name):
                summary.front_matter.append(name)
    return summary


def resolve_since(root: Path, document: Document, since: str | None) -> tuple[str, str, bool]:
    """(git reference, label, approximate) of the earlier state to compare with."""
    if since is None:
        for entry in reversed(document.releases):
            tag = tag_name(document.id, entry.version)
            if gitutil.tag_exists(root, tag):
                return tag, f"v{entry.version}", not entry.made_with_qingsong
        raise OperationError(
            f"no earlier release of {document.id} has a tag; give --since REF "
            "(or tag the earlier release: qingsong release tag)"
        )
    entry = next((item for item in document.releases if item.version == since), None)
    if entry is not None:
        tag = tag_name(document.id, since)
        if not gitutil.tag_exists(root, tag):
            raise OperationError(f"release {since} has no tag {tag}")
        return tag, f"v{since}", not entry.made_with_qingsong
    if gitutil.commit_of(root, since) is None:
        raise OperationError(f"{since!r} is neither a release of {document.id} nor a git reference")
    return since, since, False


def changes(
    root: Path, document_id: str, since: str | None = None, until: str | None = None
) -> ChangeSummary:
    try:
        if until is None:
            later = load(root)
            return changes_between(root, document_id, later, since, "the working tree")
        with vault_at(root, until) as later:
            return changes_between(root, document_id, later, since, until)
    except gitutil.GitError as error:
        raise OperationError(str(error)) from error


def changes_between(
    root: Path, document_id: str, later: Vault, since: str | None, until_label: str
) -> ChangeSummary:
    document = require_document(later, document_id)
    ref, label, approximate = resolve_since(root, document, since)
    with vault_at(root, ref) as earlier:
        return compare(document_id, earlier, later, label, ref, until_label, approximate)
