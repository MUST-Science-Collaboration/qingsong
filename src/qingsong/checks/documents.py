"""Document rules: release entries and their tags (docs/SPEC.md §5.5, §10)."""

from collections.abc import Iterator

from qingsong import gitutil
from qingsong.checks import Context, relative_file, rule
from qingsong.findings import Finding
from qingsong.schema import Document


def documents(context: Context) -> Iterator[Document]:
    for record in context.vault.records.values():
        if isinstance(record, Document):
            yield record


@rule("documents.release", "release entries are well formed, in order, and made by approvers")
def release_entries(context: Context) -> Iterator[Finding]:
    for document in documents(context):
        for message, fix in release_problems(context, document):
            yield Finding(
                "documents.release",
                "error",
                message,
                record=document.id,
                file=relative_file(context.vault, document.id),
                fix=fix,
            )


def release_problems(context: Context, document: Document) -> Iterator[tuple[str, str | None]]:
    from qingsong.operations import OperationError
    from qingsong.release import parse_version, tag_name

    previous_key: tuple[int, ...] | None = None
    previous_date = None
    seen: set[str] = set()
    for entry in document.releases:
        if entry.version in seen:
            yield (
                f"version {entry.version} is listed twice",
                "two releases were prepared in parallel; give the later one a new version",
            )
            continue
        seen.add(entry.version)
        try:
            key = parse_version(entry.version)
        except OperationError as error:
            yield str(error), None
            continue
        if previous_key is not None and key <= previous_key:
            yield f"version {entry.version} is not higher than the one before it", None
        if previous_date is not None and entry.date < previous_date:
            yield f"release {entry.version} is dated before the one before it", None
        previous_key, previous_date = key, entry.date
        if not entry.made_with_qingsong:
            continue
        expected = tag_name(document.id, entry.version)
        if entry.tag != expected:
            yield f"release {entry.version} must name the tag {expected}", None
        if not entry.engine:
            yield f"release {entry.version} does not record the qingsong version", None
        if not entry.by or not context.vault.is_approver(entry.by):
            yield f"release {entry.version} was not made by an approver", None


@rule("documents.release_tag", "release tags mark a commit that holds the same release entry")
def release_tags(context: Context) -> Iterator[Finding]:
    from qingsong.release import has_release, tag_name

    vault = context.vault
    if not gitutil.is_repository(vault.root):
        return
    for document in documents(context):
        file = relative_file(vault, document.id)
        if file is None:
            continue
        for entry in document.releases:
            tag = tag_name(document.id, entry.version)
            if not gitutil.tag_exists(vault.root, tag):
                if entry.made_with_qingsong:
                    yield Finding(
                        "documents.release_tag",
                        "info",
                        f"release {entry.version} has no tag {tag} yet",
                        record=document.id,
                        file=file,
                        fix=f"after the merge: qingsong release tag {document.id} {entry.version}",
                    )
                continue
            if not has_release(gitutil.read_at(vault.root, tag, file), entry.version):
                yield Finding(
                    "documents.release_tag",
                    "error",
                    f"the tag {tag} marks a state without release {entry.version}",
                    record=document.id,
                    file=file,
                    fix="the tag was moved or the entry was rewritten; restore one of them",
                )
