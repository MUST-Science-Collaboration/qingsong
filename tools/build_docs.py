"""Build the documentation from its sources.

- Every Markdown document listed in `documents` becomes an HTML page in docs/html/.
- The reference part of docs/api.md (modules, commands and check rules) is generated from the code,
  below the marker line, so that it cannot drift from the code.
- docs/index.html, the entrance to all of them, is generated from the same list.

    uv run python tools/build_docs.py           # write everything
    uv run python tools/build_docs.py --check   # exit 1 and name the files that are out of date

Edit the Markdown, never the HTML.
"""

import argparse
import ast
import dataclasses
import html
import importlib
import inspect
import os
import re
import sys
import typing
from dataclasses import dataclass
from pathlib import Path

from markdown_it import MarkdownIt

repository = Path(__file__).resolve().parents[1]
docs_folder = repository / "docs"
pages_folder = docs_folder / "html"
api_source = docs_folder / "api.md"
generated_marker = (
    "<!-- Generated reference: tools/build_docs.py writes everything below this line. "
    "Do not edit it by hand. -->"
)


@dataclass(frozen=True)
class Document:
    key: str
    source: str
    title: str
    group: str
    summary: str


documents = [
    Document(
        "readme",
        "README.md",
        "Overview",
        "Start here",
        "What qingsong is, what it does, and the main commands at a glance.",
    ),
    Document(
        "howto",
        "docs/howto.md",
        "How to use qingsong",
        "Start here",
        "The concepts, the rules and the everyday workflow, with worked examples for people and "
        "agents: writing requirements, recording changes, reviewing, approving and releasing.",
    ),
    Document(
        "api",
        "docs/api.md",
        "API reference",
        "Reference",
        "How the code is organised and how to extend it, then every module, command and check "
        "rule, generated from the code.",
    ),
    Document(
        "spec",
        "docs/SPEC.md",
        "Specification",
        "Reference",
        "The architecture and the accepted decisions: the source of truth for the design.",
    ),
    Document(
        "agents",
        "AGENTS.md",
        "Contributor rules",
        "Project",
        "Standing rules for people and agents who change this repository.",
    ),
    Document(
        "todo",
        "docs/TODO.md",
        "Task list",
        "Project",
        "What is done, what is next, and what waits for later.",
    ),
    Document(
        "lessons",
        "docs/lessons.md",
        "Lessons",
        "Project",
        "Mistakes made while building qingsong, and the safeguards adopted against each.",
    ),
]
journal_summaries = {
    "2026-02_legacy_todo.md": "Task list of the earlier version 0.1.",
    "2026-02-24_handover.md": "Handover note of the earlier version 0.1.",
    "2026-02-25_journal.md": "Journal of the earlier version 0.1.",
}


def all_documents() -> list[Document]:
    journal = [
        Document(
            "journal-" + path.stem,
            path.relative_to(repository).as_posix(),
            path.stem,
            "History",
            journal_summaries.get(path.name, "Development journal."),
        )
        for path in sorted((docs_folder / "journal").glob("*.md"))
    ]
    return documents + journal


# Markdown to HTML ------------------------------------------------------------------------------


def slug_of(text: str, taken: dict[str, int]) -> str:
    """GitHub's heading anchors: lower case, punctuation removed, spaces as hyphens."""
    base = re.sub(r"[^\w\- ]", "", text.strip().lower()).replace(" ", "-")
    count = taken.get(base, 0)
    taken[base] = count + 1
    return base if count == 0 else f"{base}-{count}"


def plain_text(inline_token) -> str:
    return "".join(
        child.content
        for child in inline_token.children or []
        if child.type in ("text", "code_inline")
    )


def page_link(target: str, source: Path, sources: dict[Path, Document]) -> str:
    """Rewrite a link between Markdown documents to their pages, and a link to another file of
    the repository to a path relative to the pages folder."""
    if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
        return target
    path_part, _, anchor = target.partition("#")
    if not path_part:
        return target
    resolved = (source.parent / path_part).resolve()
    if resolved in sources:
        return f"{sources[resolved].key}.html" + (f"#{anchor}" if anchor else "")
    try:
        resolved.relative_to(repository)
    except ValueError:
        return target
    relative = Path(os.path.relpath(resolved, pages_folder)).as_posix()
    return relative + (f"#{anchor}" if anchor else "")


def render_markdown(text: str, source: Path, sources: dict[Path, Document]):
    markdown = MarkdownIt("commonmark", {"html": True}).enable(["table", "strikethrough"])
    tokens = markdown.parse(text)
    taken: dict[str, int] = {}
    contents: list[tuple[int, str, str]] = []
    title = None
    for index, token in enumerate(tokens):
        if token.type == "heading_open":
            inline = tokens[index + 1]
            anchor = slug_of(plain_text(inline), taken)
            token.attrSet("id", anchor)
            level = int(token.tag[1])
            if level == 1 and title is None:
                title = plain_text(inline)
            elif level in (2, 3):
                contents.append((level, anchor, html.escape(plain_text(inline))))
        if token.type == "inline":
            for child in token.children or []:
                if child.type == "link_open":
                    child.attrSet("href", page_link(child.attrGet("href") or "", source, sources))
        if token.type == "table_open":
            token.attrSet("class", "table")
    body = markdown.renderer.render(tokens, markdown.options, {})
    body = body.replace("<table", '<div class="table-wrap"><table').replace(
        "</table>", "</table></div>"
    )
    return title, contents, body


stylesheet = """\
:root {
  --accent: #c2410c; --accent2: #f59e0b; --ink: #1f2937; --muted: #6b7280; --line: #e5e7eb;
  --bg: #ffffff; --panel: #f9fafb; --wash: #fff7ed;
}
* { box-sizing: border-box; }
html { scroll-padding-top: 64px; }
body { margin: 0; font-family: Georgia, "Times New Roman", "Songti SC", "STSong", serif; color: var(--ink);
       background: var(--bg); line-height: 1.6; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
header.top { position: sticky; top: 0; z-index: 10; background: rgba(255,255,255,0.97);
             border-bottom: 1px solid var(--line); display: flex; flex-wrap: wrap; align-items: baseline;
             gap: 4px 18px; padding: 10px 16px; }
header.top .brand { font-weight: bold; font-size: 1.1rem; color: var(--ink); }
header.top .brand span { color: var(--accent); font-weight: normal; margin-left: 4px; }
header.top nav { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 0.95rem; }
header.top nav a { color: var(--muted); }
header.top nav a.here { color: var(--accent); border-bottom: 2px solid var(--accent2); }
.layout { display: grid; grid-template-columns: 250px minmax(0, 1fr); gap: 32px; max-width: 1200px;
          margin: 0 auto; padding: 16px 16px 64px; }
aside.contents { position: sticky; top: 64px; align-self: start; max-height: calc(100vh - 80px);
                 overflow-y: auto; font-size: 0.86rem; border-right: 1px solid var(--line); padding-right: 12px; }
aside.contents h2 { font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted);
                    margin: 8px 0; border: 0; }
aside.contents ol { list-style: none; margin: 0; padding: 0; }
aside.contents li { margin: 3px 0; }
aside.contents li.level-3 { padding-left: 12px; font-size: 0.82rem; }
aside.contents a { color: var(--ink); }
aside.contents a:hover { color: var(--accent); }
main { min-width: 0; max-width: 860px; }
main h1 { font-size: 2rem; margin: 8px 0 12px; }
main h2 { font-size: 1.4rem; margin: 40px 0 10px; padding-bottom: 4px; border-bottom: 2px solid var(--accent2); }
main h3 { font-size: 1.15rem; margin: 28px 0 8px; }
main h4 { font-size: 1rem; margin: 20px 0 6px; color: var(--accent); }
code { font-family: Menlo, Consolas, monospace; font-size: 0.86em; background: var(--panel);
       padding: 1px 4px; border-radius: 3px; overflow-wrap: anywhere; }
pre { background: var(--panel); border: 1px solid var(--line); border-left: 3px solid var(--accent2);
      padding: 10px 14px; overflow-x: auto; border-radius: 4px; }
pre code { background: none; padding: 0; overflow-wrap: normal; }
blockquote { margin: 16px 0; padding: 8px 16px; background: var(--wash); border-left: 3px solid var(--accent); }
blockquote p { margin: 6px 0; }
.table-wrap { overflow-x: auto; margin: 12px 0; }
table { border-collapse: collapse; font-size: 0.92rem; }
th, td { border: 1px solid var(--line); padding: 5px 9px; text-align: left; vertical-align: top; }
th { background: var(--panel); }
footer { color: var(--muted); font-size: 0.82rem; max-width: 1200px; margin: 0 auto; padding: 12px 16px 32px;
         border-top: 1px solid var(--line); }
@media (max-width: 860px) {
  .layout { grid-template-columns: minmax(0, 1fr); }
  aside.contents { position: static; max-height: none; border-right: 0; border-bottom: 1px solid var(--line);
                   padding-bottom: 8px; }
  aside.contents li.level-3 { display: none; }
}
@media print { header.top, aside.contents { display: none; } .layout { display: block; } }

/* entrance page */
.hero { max-width: 1100px; margin: 0 auto; padding: 36px 16px 8px; }
.hero h1 { font-size: 2.3rem; margin: 0; }
.hero h1 span { color: var(--accent); font-weight: normal; }
.hero p { font-size: 1.1rem; color: var(--muted); max-width: 760px; }
.entrance { max-width: 1100px; margin: 0 auto; padding: 0 16px 48px; }
.entrance h2 { font-size: 1.25rem; margin: 32px 0 10px; padding-bottom: 4px; border-bottom: 2px solid var(--accent2); }
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 14px; }
.card { display: block; border: 1px solid var(--line); border-top: 3px solid var(--accent); border-radius: 6px;
        padding: 12px 14px; color: var(--ink); background: var(--bg); }
.card:hover { text-decoration: none; background: var(--wash); }
.card b { display: block; font-size: 1.05rem; color: var(--accent); margin-bottom: 4px; }
.card span { display: block; font-size: 0.92rem; }
.card small { display: block; margin-top: 8px; color: var(--muted); font-family: Menlo, Consolas, monospace;
              font-size: 0.75rem; }
.flow { display: flex; flex-wrap: wrap; gap: 8px; align-items: stretch; margin: 8px 0 4px; padding: 0; list-style: none; }
.flow li { flex: 1 1 140px; border: 1px solid var(--line); border-radius: 6px; padding: 8px 10px; background: var(--panel);
           font-size: 0.88rem; position: relative; }
.flow li b { display: block; color: var(--accent); }
.flow code { font-size: 0.8em; }
.note { color: var(--muted); font-size: 0.9rem; }
ul.history { padding-left: 20px; }
"""

page_template = """\
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · qingsong</title>
<link rel="stylesheet" href="docs.css">
</head>
<body>
<header class="top"><a class="brand" href="../index.html">qingsong<span>青松</span></a>
<nav>{navigation}</nav></header>
<div class="layout">
<aside class="contents"><h2>On this page</h2><ol>
{contents}
</ol></aside>
<main>
{body}
</main>
</div>
<footer>Generated from <code>{source}</code> by <code>tools/build_docs.py</code>. Edit the Markdown file,
then rebuild; this page is overwritten.</footer>
</body>
</html>
"""


def navigation(current: str | None, prefix: str) -> str:
    links = []
    for document in documents:
        here = ' class="here"' if document.key == current else ""
        links.append(f'<a{here} href="{prefix}{document.key}.html">{document.title}</a>')
    return "\n".join(links)


def page(document: Document, sources: dict[Path, Document], text: str | None = None) -> str:
    source = repository / document.source
    if text is None:
        text = source.read_text(encoding="utf-8")
    title, contents, body = render_markdown(text, source, sources)
    items = "\n".join(
        f'<li class="level-{level}"><a href="#{anchor}">{label}</a></li>'
        for level, anchor, label in contents
    )
    return page_template.format(
        title=html.escape(title or document.title),
        navigation=navigation(document.key, ""),
        contents=items,
        body=body,
        source=html.escape(document.source),
    )


workflow_steps = [
    ("Branch", "Never on <code>main</code>: every change starts on a branch."),
    ("Edit", "Change the record's YAML file, or create one with <code>qingsong new</code>."),
    ("Record", "<code>qingsong revise</code> stamps it and adds a history event."),
    ("Check", "<code>qingsong check</code>: no errors before a commit."),
    ("Review", "Issues, proposed fixes and the review page's decisions file."),
    ("Approve", "An approver approves; merges happen with their permission."),
    ("Release", "<code>release prepare</code>, merge, <code>release tag</code>, issued copy."),
]


def entrance(all_pages: list[Document]) -> str:
    groups: dict[str, list[Document]] = {}
    for document in all_pages:
        groups.setdefault(document.group, []).append(document)
    sections = []
    steps = "\n".join(
        f"<li><b>{number}. {name}</b>{text}</li>"
        for number, (name, text) in enumerate(workflow_steps, start=1)
    )
    sections.append(
        '<h2>The workflow at a glance</h2>\n<ol class="flow">\n' + steps + "\n</ol>\n"
        '<p class="note">Each step is explained, with examples, in '
        '<a href="html/howto.html">How to use qingsong</a>.</p>'
    )
    for group in ("Start here", "Reference", "Project"):
        cards = "\n".join(
            f'<a class="card" href="html/{document.key}.html"><b>{document.title}</b>'
            f"<span>{html.escape(document.summary)}</span><small>{document.source}</small></a>"
            for document in groups.get(group, [])
        )
        sections.append(f'<h2>{group}</h2>\n<div class="cards">\n{cards}\n</div>')
    history = "\n".join(
        f'<li><a href="html/{document.key}.html">{document.title}</a>: '
        f"{html.escape(document.summary)}</li>"
        for document in groups.get("History", [])
    )
    sections.append(
        '<h2>History</h2>\n<p class="note">Notes kept from the earlier version 0.1, which was '
        'replaced by the rebuild. They describe a design that no longer exists.</p>\n<ul class="history">\n'
        + history
        + "\n</ul>"
    )
    from qingsong import __version__

    return f"""\
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>qingsong documentation</title>
<link rel="stylesheet" href="html/docs.css">
</head>
<body>
<header class="top"><a class="brand" href="index.html">qingsong<span>青松</span></a>
<nav>{navigation(None, "html/")}</nav></header>
<div class="hero">
<h1>qingsong <span>青松</span> documentation</h1>
<p>qingsong keeps a project's requirements as checked, versioned engineering records in a git
repository, and generates the documents people read from them. Version {__version__}.</p>
<p class="note">New here? Read the <a href="html/readme.html">Overview</a>, then
<a href="html/howto.html">How to use qingsong</a>. Agents also follow the
<a href="html/agents.html">contributor rules</a>; every command accepts <code>--json</code>.</p>
</div>
<div class="entrance">
{chr(10).join(sections)}
</div>
<footer>Generated by <code>tools/build_docs.py</code> from the Markdown documents of this repository.
Edit the Markdown files, then rebuild.</footer>
</body>
</html>
"""


# Reference generated from the code ---------------------------------------------------------------

module_groups = [
    (
        "Records and the vault",
        [
            "qingsong.schema",
            "qingsong.vault",
            "qingsong.ids",
            "qingsong.hashing",
            "qingsong.findings",
            "qingsong.walk",
        ],
    ),
    (
        "Checks",
        [
            "qingsong.checks",
            "qingsong.checks.integrity",
            "qingsong.checks.structure",
            "qingsong.checks.change",
            "qingsong.checks.content",
            "qingsong.checks.consistency",
            "qingsong.checks.documents",
        ],
    ),
    (
        "Changing the record",
        [
            "qingsong.operations",
            "qingsong.review",
            "qingsong.decisions_file",
            "qingsong.slots",
            "qingsong.wording",
            "qingsong.release",
            "qingsong.gitutil",
        ],
    ),
    (
        "Outputs",
        [
            "qingsong.render.model",
            "qingsong.render.text",
            "qingsong.render.html",
            "qingsong.render.word",
            "qingsong.export",
        ],
    ),
]
module_path_pattern = re.compile(r"\b(?:[a-z_][a-z0-9_]*\.)+(?=[A-Za-z_])")


def without_optional(text: str) -> str:
    """`Optional[X]` written as `X | None`, as Python 3.14 prints it, so that the reference does
    not depend on the Python version that builds it."""
    start = text.find("Optional[")
    while start != -1:
        depth, index = 0, start + len("Optional")
        for index in range(start + len("Optional"), len(text)):
            depth += {"[": 1, "]": -1}.get(text[index], 0)
            if depth == 0:
                break
        inner = text[start + len("Optional[") : index]
        text = text[:start] + f"{inner} | None" + text[index + 1 :]
        start = text.find("Optional[")
    return text


def short_annotation(annotation) -> str:
    if annotation is inspect.Parameter.empty:
        return ""
    text = inspect.formatannotation(annotation)
    return without_optional(module_path_pattern.sub("", text))


def signature_of(function, wrap: bool = True) -> str:
    try:
        signature = inspect.signature(function)
    except (TypeError, ValueError):
        return "(…)"
    parts = []
    for parameter in signature.parameters.values():
        text = parameter.name
        if parameter.kind is parameter.VAR_POSITIONAL:
            text = "*" + text
        elif parameter.kind is parameter.VAR_KEYWORD:
            text = "**" + text
        annotation = short_annotation(parameter.annotation)
        if annotation:
            text += f": {annotation}"
        if parameter.default is not inspect.Parameter.empty:
            text += f" = {parameter.default!r}"
        parts.append(text)
    returned = short_annotation(signature.return_annotation)
    tail = f" -> {returned}" if returned else ""
    one_line = f"({', '.join(parts)}){tail}"
    if len(one_line) <= 72 or not wrap:
        return one_line
    return "(\n" + "".join(f"    {part},\n" for part in parts) + f"){tail}"


def documentation_of(item) -> str:
    text = inspect.getdoc(item) or ""
    return text.strip()


def defined_names(module) -> list[str]:
    tree = ast.parse(inspect.getsource(module))
    names = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.append(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names.extend(target.id for target in targets if isinstance(target, ast.Name))
    return names


def is_type_alias(value) -> bool:
    return typing.get_origin(value) is not None


def alias_text(value) -> str:
    """A type alias as written; for `Annotated`, the type and what the annotation adds."""
    if typing.get_origin(value) is typing.Annotated:
        inner, *metadata = typing.get_args(value)
        notes = []
        for item in metadata:
            if getattr(item, "discriminator", None):
                notes.append(f"chosen by `{item.discriminator}`")
            for constraint in getattr(item, "metadata", []):
                if getattr(constraint, "pattern", None):
                    notes.append(f"pattern `{constraint.pattern}`")
        return f"`{short_annotation(inner)}`" + (f" ({'; '.join(notes)})" if notes else "")
    return f"`{short_annotation(value)}`"


def field_rows(item) -> list[tuple[str, str, str]]:
    """Fields declared by the class itself; inherited ones are listed with the parent."""
    from pydantic import BaseModel

    rows = []
    if issubclass(item, BaseModel):
        own = inspect.get_annotations(item)  # the class's own; not in __dict__ from Python 3.14
        for name, field in item.model_fields.items():
            if name not in own:
                continue
            if field.is_required():
                default = "required"
            elif field.default_factory is not None:
                default = repr(field.default_factory())
            else:
                default = repr(field.default)
            rows.append((field.alias or name, short_annotation(field.annotation), default))
    elif dataclasses.is_dataclass(item):
        for field in dataclasses.fields(item):
            if field.default is not dataclasses.MISSING:
                default = repr(field.default)
            elif field.default_factory is not dataclasses.MISSING:
                default = repr(field.default_factory())
            else:
                default = "required"
            rows.append((field.name, short_annotation(field.type), default))
    return rows


def own_documentation(item) -> str:
    """A class's own docstring: not inherited, and not the one dataclasses generate."""
    text = item.__dict__.get("__doc__") or ""
    if not text or text.startswith(f"{item.__name__}("):
        return ""
    return inspect.cleandoc(text)


def table_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def describe_class(item, lines: list[str]) -> None:
    bases = [base.__name__ for base in item.__bases__ if base is not object]
    heading = f"#### class `{item.__name__}`" + (f" ({', '.join(bases)})" if bases else "")
    lines.extend([heading, ""])
    documentation = own_documentation(item)
    if documentation:
        lines.extend([documentation, ""])
    rows = field_rows(item)
    if rows:
        lines.extend(["| Field | Type | Default |", "| --- | --- | --- |"])
        lines.extend(
            f"| `{name}` | `{table_cell(kind)}` | `{table_cell(default)}` |"
            for name, kind, default in rows
        )
        lines.append("")
    for name, member in item.__dict__.items():
        if name.startswith("_"):
            continue
        function = member.fget if isinstance(member, property) else member
        if isinstance(member, (classmethod, staticmethod)):
            function = member.__func__
        if not inspect.isfunction(function):
            continue
        kind = "property " if isinstance(member, property) else ""
        lines.extend([f"- {kind}`{name}{signature_of(function) if not kind else ''}`"])
        documentation = documentation_of(function)
        if documentation:
            lines.append("  " + documentation.replace("\n", "\n  "))
    lines.append("")


def describe_module(name: str, registered: dict) -> list[str]:
    module = importlib.import_module(name)
    path = Path(inspect.getsourcefile(module)).relative_to(repository).as_posix()
    lines = [f"### `{name}`", "", f"Source: [`{path}`](../{path})", ""]
    documentation = documentation_of(module)
    if documentation:
        lines.extend([documentation, ""])
    aliases, classes, functions = [], [], []
    for item_name in defined_names(module):
        item = getattr(module, item_name, None)
        if item is None:
            continue
        if inspect.isclass(item) and item.__module__ == name:
            classes.append(item)
        elif inspect.isfunction(item) and item.__module__ == name:
            functions.append(item)
        elif is_type_alias(item):
            aliases.append((item_name, item))
    if aliases:
        lines.extend(["**Types**", ""])
        lines.extend(f"- `{alias}`: {alias_text(value)}" for alias, value in aliases)
        lines.append("")
    if classes:
        lines.extend(["**Classes**", ""])
        for item in classes:
            describe_class(item, lines)
    checks = [function for function in functions if function in registered]
    documented = [
        function
        for function in functions
        if function not in registered and documentation_of(function)
    ]
    helpers = [
        function
        for function in functions
        if function not in registered and not documentation_of(function)
    ]
    if checks:
        lines.extend(["**Check rules**", ""])
        lines.extend(
            f"- `{registered[function].rule_id}` (`{function.__name__}`): "
            f"{registered[function].summary}."
            for function in checks
        )
        lines.append("")
    if documented:
        lines.extend(["**Functions**", ""])
        for function in documented:
            lines.extend(
                [
                    f"#### `{function.__name__}`",
                    "",
                    "```python",
                    f"def {function.__name__}{signature_of(function)}",
                    "```",
                    "",
                    documentation_of(function),
                    "",
                ]
            )
    if helpers:
        lines.extend(["**Helpers**", ""])
        lines.extend(
            f"- `{function.__name__}{signature_of(function, wrap=False)}`" for function in helpers
        )
        lines.append("")
    return lines


def command_reference() -> list[str]:
    from typer.main import get_command

    from qingsong.cli import app

    lines = []

    def visit(command, path: list[str]) -> None:
        if hasattr(command, "commands"):
            for name in command.commands:
                visit(command.commands[name], path + [name])
            return
        arguments = [
            parameter for parameter in command.params if parameter.param_type_name == "argument"
        ]
        usage = " ".join(
            ["qingsong", *path, *(argument.human_readable_name.upper() for argument in arguments)]
        )
        lines.extend([f"### `qingsong {' '.join(path)}`", ""])
        help_text = (command.help or "").strip().split("\n\n")[0]
        if help_text:
            lines.extend([help_text.replace("\n", " "), ""])
        lines.extend(["```bash", usage + " [OPTIONS]", "```", ""])
        rows = []
        for parameter in command.params:
            if parameter.name in ("help", "vault", "as_json"):
                continue
            if parameter.param_type_name == "argument":
                label = parameter.human_readable_name.upper()
                help_text = getattr(parameter, "help", "") or ""
            else:
                label = ", ".join(parameter.opts)
                help_text = parameter.help or ""
            required = "yes" if parameter.required else ""
            rows.append(f"| `{label}` | {required} | {table_cell(help_text)} |")
        if rows:
            lines.extend(
                ["| Argument or option | Required | Meaning |", "| --- | --- | --- |", *rows, ""]
            )

    visit(get_command(app), [])
    return lines


def rule_reference() -> tuple[list[str], dict]:
    from qingsong import checks

    for module in ("change", "consistency", "content", "documents", "integrity", "structure"):
        importlib.import_module(f"qingsong.checks.{module}")
    summaries = dict(checks.load_rules)
    summaries.update({rule_id: rule.summary for rule_id, rule in checks.rules.items()})
    lines = ["| Rule | What it checks |", "| --- | --- |"]
    lines.extend(
        f"| `{rule_id}` | {summaries[rule_id]}{' *(load)*' if rule_id in checks.load_rules else ''} |"
        for rule_id in sorted(summaries)
    )
    registered = {rule.function: rule for rule in checks.rules.values()}
    return lines + [""], registered


def generated_reference() -> str:
    rules, registered = rule_reference()
    lines = [
        generated_marker,
        "",
        "## Commands",
        "",
        "Generated from the command-line interface. Every command also accepts `--vault PATH` "
        "(default: the nearest folder holding `qingsong.toml`), `--json` (machine-readable "
        "output; `init` and `rules` take only `--json`) and `--help`. `--by` names a person in "
        "`people.yaml`; `--via` names the agent acting for them.",
        "",
        *command_reference(),
        "## Check rules",
        "",
        "Generated from the rule registry; `qingsong rules` prints the same list. Severities "
        "often depend on the record's maturity. The rules marked *(load)* report problems found "
        "while reading the vault.",
        "",
        *rules,
    ]
    for group, names in module_groups:
        lines.extend([f"## Modules: {group.lower()}", ""])
        for name in names:
            lines.extend(describe_module(name, registered))
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).rstrip() + "\n"


def api_document() -> str:
    current = api_source.read_text(encoding="utf-8")
    handwritten, marker, _ = current.partition(generated_marker)
    if not marker:
        raise SystemExit(f"{api_source.name} lacks the marker line of the generated reference")
    return handwritten.rstrip() + "\n\n" + generated_reference()


# Build -------------------------------------------------------------------------------------------


def outputs() -> dict[Path, str]:
    result = {api_source: api_document()}
    pages = all_documents()
    sources = {(repository / document.source).resolve(): document for document in pages}
    for document in pages:
        text = result[api_source] if document.key == "api" else None
        result[pages_folder / f"{document.key}.html"] = page(document, sources, text)
    result[pages_folder / "docs.css"] = stylesheet
    result[docs_folder / "index.html"] = entrance(pages)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--check", action="store_true", help="report out-of-date files; write nothing"
    )
    arguments = parser.parse_args()
    expected = outputs()
    stale = [
        path
        for path, text in expected.items()
        if not path.exists() or path.read_text(encoding="utf-8") != text
    ]
    known = set(expected)
    extra = (
        [path for path in pages_folder.glob("*") if path not in known]
        if pages_folder.exists()
        else []
    )
    if arguments.check:
        for path in stale:
            print(f"out of date: {path.relative_to(repository)}")
        for path in extra:
            print(f"no longer generated: {path.relative_to(repository)}")
        return 1 if stale or extra else 0
    for path in stale:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(expected[path], encoding="utf-8")
        print(f"wrote {path.relative_to(repository)}")
    for path in extra:
        path.unlink()
        print(f"removed {path.relative_to(repository)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
