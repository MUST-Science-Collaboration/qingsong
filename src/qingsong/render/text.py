"""The text format of docs/SPEC.md §5.4 (a Markdown subset), shared by the HTML and Word renderers.

Block level: paragraphs, bullet lists ("- ") and numbered lists ("1. "), nested by indentation.
Inline: **bold**, *italic*, `code`, ~sub~, ^sup^, $math$, [text](url), [[ID]] and [[DOC#key]]
references, and backslash escapes. Open values (bracketed text, TBD, TBC, 待定, 待确认) are marked.
The inline rules follow pandoc where the two could differ: emphasis, sub- and superscript and math
need non-space characters inside their markers, so "2 * 3", "~45 m" and "$5" stay as written."""

import html
import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal

Resolver = Callable[[str, str | None, str], tuple[str, str | None]]

token_pattern = re.compile(
    r"(?P<escape>\\[\\`*_{}\[\]()#+\-.!~^$|])"
    r"|(?P<reference>\[\[(?P<target>[A-Za-z0-9._-]+)(?:#(?P<key>[A-Za-z0-9_-]+))?\]\])"
    r"|(?P<link>\[(?P<link_text>[^\[\]]+)\]\((?P<url>(?:[^()\s]|\([^()\s]*\))+)\))"
    r"|(?P<code>`[^`\n]+`)"
    r"|(?P<math>\$(?=\S)[^$\n]*?(?<=\S)\$(?!\d))"
    r"|(?P<bold>\*\*(?=\S)(?:[^*\n]|\*(?!\*))+?(?<=\S)\*\*)"
    r"|(?P<italic>\*(?=[^\s*])[^*\n]*?(?<=[^\s*])\*)"
    r"|(?P<sub>~[^~\s]+~)"
    r"|(?P<sup>\^[^\^\s]+\^)"
    r"|(?P<open>\[(?!\^)[^\[\]]+\]|(?<![A-Za-z0-9])(?:TBD|TBC)(?![A-Za-z0-9])|待定|待确认)"
)
safe_url = re.compile(r"^(?:https?://|mailto:|#|\.{0,2}/|[A-Za-z0-9_][A-Za-z0-9_./-]*(?:#.*)?$)")


def inline(text: str, language: str, resolve: Resolver) -> str:
    output: list[str] = []
    position = 0
    for match in token_pattern.finditer(text):
        output.append(html.escape(text[position : match.start()]))
        position = match.end()
        kind = match.lastgroup
        token = match.group(0)
        if match.group("escape"):
            output.append(html.escape(token[1]))
        elif match.group("reference"):
            label, href = resolve(match.group("target"), match.group("key"), language)
            output.append(
                f'<a class="ref" href="{html.escape(href)}">{html.escape(label)}</a>'
                if href
                else f'<span class="ref broken">{html.escape(label)}</span>'
            )
        elif match.group("link"):
            url = match.group("url")
            body = inline(match.group("link_text"), language, resolve)
            output.append(
                f'<a href="{html.escape(url)}">{body}</a>'
                if safe_url.match(url)
                else f"{body} ({html.escape(url)})"
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


# block structure ------------------------------------------------------------------------------
list_item = re.compile(r"^(?P<indent>\s*)(?P<marker>-|\d+\.)\s+(?P<text>.*)$")


@dataclass
class ListItem:
    level: int
    ordered: bool
    text: str


@dataclass
class Block:
    kind: str  # "paragraph" or "list"
    text: str = ""
    items: list[ListItem] = field(default_factory=list)


def parse_blocks(text: str) -> list[Block]:
    """Paragraphs and lists. A list may start right after a paragraph line, items continue on
    indented lines, blank lines between items keep one list, and indentation nests items."""
    result: list[Block] = []
    paragraph: list[str] = []
    current: Block | None = None

    def close_paragraph() -> None:
        if paragraph:
            result.append(Block("paragraph", " ".join(part.strip() for part in paragraph)))
            paragraph.clear()

    for line in text.strip().split("\n"):
        match = list_item.match(line)
        if match:
            close_paragraph()
            if current is None:
                current = Block("list")
                result.append(current)
            level = len(match.group("indent").expandtabs(4)) // 2
            current.items.append(
                ListItem(level, match.group("marker") != "-", match.group("text").strip())
            )
        elif not line.strip():
            close_paragraph()
        elif current is not None and line.startswith((" ", "\t")):
            current.items[-1].text += " " + line.strip()
        else:
            current = None
            paragraph.append(line)
    close_paragraph()
    return result


def blocks(text: str, language: str, resolve: Resolver) -> str:
    parts: list[str] = []
    for block in parse_blocks(text):
        if block.kind == "paragraph":
            parts.append(f"<p>{inline(block.text, language, resolve)}</p>")
            continue
        html_parts: list[str] = []
        stack: list[str] = []
        for item in block.items:
            tag = "ol" if item.ordered else "ul"
            while len(stack) > item.level + 1:
                html_parts.append(f"</li></{stack.pop()}>")
            if len(stack) == item.level + 1:
                html_parts.append("</li>")
            while len(stack) < item.level + 1:
                html_parts.append(f"<{tag}>")
                stack.append(tag)
            html_parts.append(f"<li>{inline(item.text, language, resolve)}")
        while stack:
            html_parts.append(f"</li></{stack.pop()}>")
        parts.append("".join(html_parts))
    return "".join(parts)


# value slots ----------------------------------------------------------------------------------
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
attached_units = {"°", "″", "′"}  # SI: a space before %, none before angle symbols
superscripts = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")
markdown_special = re.compile(r"([\\`*_{}~^$|])")


def number(value: float) -> str:
    """Plain decimal notation with a thousands separator, a true minus sign, and a power of ten
    only for extreme magnitudes."""
    if value == 0:
        return "0"
    sign = "−" if value < 0 else ""
    magnitude = abs(value)
    if magnitude >= 1e9 or magnitude < 1e-4:
        exponent = math.floor(math.log10(magnitude))
        mantissa = f"{magnitude / 10**exponent:.6g}"
        return f"{sign}{mantissa} × 10{str(exponent).translate(superscripts)}"
    text = format(Decimal(repr(magnitude)), "f")
    whole, _, fraction = text.partition(".")
    fraction = fraction.rstrip("0")
    whole = f"{int(whole):,}" if len(whole) > 3 else whole
    return sign + whole + (f".{fraction}" if fraction else "")


def unit_label(unit: str | None) -> str:
    if not unit:
        return ""
    label = unit_labels.get(unit, unit)
    label = re.sub(
        r"\*\*\s*(-?\d+)|\^\s*(-?\d+)",
        lambda match: (match.group(1) or match.group(2)).translate(superscripts),
        label,
    )
    return re.sub(r"\s*\*\s*", "·", label)


def format_slot(slot, language: str) -> str:
    """A value slot as it reads in a document: relation, value, tolerance, unit and certainty.
    The result is escaped so that it is never read as markup."""
    if slot.certainty == "tbd":
        return "TBD" if language == "en" else "TBD（待定）"
    unit = unit_label(slot.unit)
    spaced = (unit if unit in attached_units else f" {unit}") if unit else ""
    sign = ""
    if slot.relation == "range":
        amount = f"{number(slot.minimum)}–{number(slot.maximum)}{spaced}"
    else:
        value = number(slot.value)
        if slot.tolerance:
            plus, minus = slot.tolerance.plus, slot.tolerance.minus
            tolerance = (
                f" ± {number(plus)}" if plus == minus else f" +{number(plus)}/−{number(minus)}"
            )
            value = f"({value}{tolerance})" if unit in attached_units else value + tolerance
        sign = relation_signs[slot.relation]
        amount = f"{value}{spaced}"
    if slot.certainty == "provisional":
        amount = f"[{amount}]"
    text = sign + amount
    if slot.certainty == "tbc":
        text = f"{text} (TBC)" if language == "en" else f"{text}（待确认）"
    if slot.goal is not None:
        goal = f"{number(slot.goal)}{spaced}"
        text += f" (goal {goal})" if language == "en" else f"（目标为{goal}）"
    return markdown_special.sub(r"\\\1", text)


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
