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


relation_signs = {"eq": "", "le": "≤ ", "lt": "< ", "ge": "≥ ", "gt": "> ", "approx": "≈ "}
unit_labels = {
    "percent": "%",
    "degC": "°C",
    "degree": "°",
    "deg": "°",
    "um": "μm",
    "micrometer": "μm",
    "count": "",
    "dimensionless": "",
    "arcsec": "″",
    "arcmin": "′",
}


def number(value: float) -> str:
    return f"{value:,.10g}" if abs(value) >= 10000 else f"{value:.10g}"


def unit_label(unit: str | None) -> str:
    if not unit:
        return ""
    label = unit_labels.get(unit, unit)
    if not label:
        return ""
    return label if label in ("%", "°", "″", "′") else f" {label}"


def format_slot(slot, language: str) -> str:
    """A value slot as it reads in a document: relation, value, tolerance, unit and certainty."""
    if slot.certainty == "tbd":
        return "TBD" if language == "en" else "TBD（待定）"
    unit = unit_label(slot.unit)
    if slot.relation == "range":
        text = f"{number(slot.minimum)}–{number(slot.maximum)}{unit}"
    else:
        text = f"{relation_signs[slot.relation]}{number(slot.value)}"
        if slot.tolerance:
            plus, minus = slot.tolerance.plus, slot.tolerance.minus
            text += f" ± {number(plus)}" if plus == minus else f" +{number(plus)}/−{number(minus)}"
        text += unit
    if slot.certainty == "provisional":
        return f"[{text}]"
    if slot.certainty == "tbc":
        return f"{text} (TBC)" if language == "en" else f"{text}（待确认）"
    return text


slot_reference = re.compile(r"\{([a-z][a-z0-9_]*)\}")


def substitute_slots(text: str, values: dict, language: str) -> str:
    """Replace {slot} placeholders with formatted values; unknown names stay visible."""
    if not values:
        return text
    return slot_reference.sub(
        lambda match: (
            format_slot(values[match.group(1)], language)
            if match.group(1) in values
            else match.group(0)
        ),
        text,
    )
