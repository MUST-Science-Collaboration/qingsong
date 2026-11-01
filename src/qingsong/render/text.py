"""Render the text format of docs/SPEC.md §5.4 (a Markdown subset) to HTML.

Supported: paragraphs, "- " lists, **bold**, *italic*, `code`, ~sub~, ^sup^, $math$, [text](url),
[[ID]] and [[DOC#key]] references. Open values (bracketed text, TBD, TBC, 待定, 待确认) are marked."""

import html
import re
from collections.abc import Callable

Resolver = Callable[[str, str | None, str], tuple[str, str | None]]

token_pattern = re.compile(
    r"(?P<reference>\[\[(?P<target>[A-Za-z0-9._-]+)(?:#(?P<key>[A-Za-z0-9_-]+))?\]\])"
    r"|(?P<link>\[(?P<link_text>[^\[\]]+)\]\((?P<url>[^)\s]+)\))"
    r"|(?P<code>`[^`\n]+`)"
    r"|(?P<math>\$[^$\n]+\$)"
    r"|(?P<bold>\*\*[^*\n]+\*\*)"
    r"|(?P<italic>\*[^*\n]+\*)"
    r"|(?P<sub>~[^~\s][^~\n]*~)"
    r"|(?P<sup>\^[^^\s][^^\n]*\^)"
    r"|(?P<open>\[[^\[\]]+\]|(?<![A-Za-z0-9])(?:TBD|TBC)(?![A-Za-z0-9])|待定|待确认)"
)


def inline(text: str, language: str, resolve: Resolver) -> str:
    output: list[str] = []
    position = 0
    for match in token_pattern.finditer(text):
        output.append(html.escape(text[position : match.start()]))
        position = match.end()
        kind = match.lastgroup
        token = match.group(0)
        if match.group("reference"):
            label, href = resolve(match.group("target"), match.group("key"), language)
            output.append(
                f'<a class="ref" href="{html.escape(href)}">{html.escape(label)}</a>'
                if href
                else f'<span class="ref broken">{html.escape(label)}</span>'
            )
        elif match.group("link"):
            output.append(
                f'<a href="{html.escape(match.group("url"))}">'
                f"{inline(match.group('link_text'), language, resolve)}</a>"
            )
        elif kind == "code":
            output.append(f"<code>{html.escape(token[1:-1])}</code>")
        elif kind == "math":
            output.append(f'<span class="math">{html.escape(token[1:-1])}</span>')
        elif kind == "bold":
            output.append(f"<strong>{inline(token[2:-2], language, resolve)}</strong>")
        elif kind == "italic":
            output.append(f"<em>{inline(token[1:-1], language, resolve)}</em>")
        elif kind == "sub":
            output.append(f"<sub>{html.escape(token[1:-1])}</sub>")
        elif kind == "sup":
            output.append(f"<sup>{html.escape(token[1:-1])}</sup>")
        elif kind == "open":
            output.append(f'<mark class="open" title="open value">{html.escape(token)}</mark>')
    output.append(html.escape(text[position:]))
    return "".join(output)


list_marker = re.compile(r"^\s*-\s+")


def blocks(text: str, language: str, resolve: Resolver) -> str:
    """Paragraphs and "- " lists."""
    parts: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text.strip()):
        lines = [line for line in paragraph.split("\n") if line.strip()]
        if lines and all(list_marker.match(line) for line in lines):
            items = "".join(
                "<li>" + inline(list_marker.sub("", line), language, resolve) + "</li>"
                for line in lines
            )
            parts.append(f"<ul>{items}</ul>")
        elif lines:
            parts.append(
                f"<p>{inline(' '.join(line.strip() for line in lines), language, resolve)}</p>"
            )
    return "".join(parts)
