"""Identifier syntax, namespaces and file paths (docs/SPEC.md §4.3, §5.3, §6)."""

import re
from pathlib import Path

segment = r"[A-Z][A-Z0-9]*"
id_patterns: dict[str, re.Pattern[str]] = {
    "requirement": re.compile(
        rf"^(?P<namespace>{segment}(?:-{segment})+)-REQ-(?P<number>\d{{3,}})$"
    ),
    "figure": re.compile(rf"^(?P<namespace>{segment}(?:-{segment})+)-FIG-(?P<number>\d{{3,}})$"),
    "condition": re.compile(
        rf"^(?P<namespace>{segment}(?:-{segment})*)-COND-(?P<number>\d{{3,}})$"
    ),
    "interface": re.compile(rf"^IFC-(?P<namespace>{segment})-(?P<number>\d{{3,}})$"),
    "issue": re.compile(r"^ISS-(?P<number>\d{4,})$"),
    "decision": re.compile(r"^DEC-(?P<number>\d{4,})$"),
    "waiver": re.compile(r"^WVR-(?P<number>\d{4,})$"),
    "verification": re.compile(r"^VER-(?P<requirement>.+-REQ-\d{3,})-(?P<number>\d{2,})$"),
    "source": re.compile(r"^SRC-[A-Za-z0-9][A-Za-z0-9._-]*$"),
    "baseline": re.compile(r"^BL-[A-Za-z0-9][A-Za-z0-9._-]*$"),
    "document": re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Za-z0-9.]+)+$"),
    "quantity": re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$"),
}
number_widths: dict[str, int] = {
    "requirement": 3,
    "figure": 3,
    "condition": 3,
    "interface": 3,
    "issue": 4,
    "decision": 4,
    "waiver": 4,
    "verification": 2,
}
type_tokens: dict[str, str] = {"requirement": "REQ", "figure": "FIG", "condition": "COND"}
reserved_codes = {
    "REQ",
    "SYS",
    "COND",
    "FIG",
    "IFC",
    "ISS",
    "DEC",
    "WVR",
    "VER",
    "SRC",
    "BL",
    "RD",
    "ICD",
}
node_code_pattern = re.compile(r"^[A-Z][A-Z0-9]{1,5}$")
reference_pattern = re.compile(r"\[\[([A-Za-z0-9._-]+)(?:#([A-Za-z0-9_-]+))?\]\]")
any_double_bracket = re.compile(r"\[\[[^\[\]]*\]\]")


def id_matches(record_type: str, record_id: str) -> bool:
    pattern = id_patterns.get(record_type)
    return bool(pattern and pattern.match(record_id))


def namespace_of(record_type: str, record_id: str) -> str | None:
    pattern = id_patterns.get(record_type)
    match = pattern.match(record_id) if pattern else None
    if match and "namespace" in match.groupdict():
        return match.group("namespace")
    return None


def number_of(record_type: str, record_id: str) -> int | None:
    pattern = id_patterns.get(record_type)
    match = pattern.match(record_id) if pattern else None
    if match and "number" in match.groupdict():
        return int(match.group("number"))
    return None


def format_id(record_type: str, namespace: str | None, number: int) -> str:
    width = number_widths[record_type]
    digits = f"{number:0{width}d}"
    if record_type in type_tokens:
        return f"{namespace}-{type_tokens[record_type]}-{digits}"
    if record_type == "interface":
        return f"IFC-{namespace}-{digits}"
    if record_type == "verification":
        return f"VER-{namespace}-{digits}"
    prefixes = {"issue": "ISS", "decision": "DEC", "waiver": "WVR"}
    return f"{prefixes[record_type]}-{digits}"


def relative_path(record_type: str, record_id: str) -> Path:
    from qingsong.schema import folders_with_system, record_folders

    folder = Path(record_folders[record_type])
    if record_type in folders_with_system:
        folder = folder / record_id.split("-")[0]
    return folder / f"{record_id}.yaml"


def references_in_text(text: str) -> list[tuple[str, str | None]]:
    return [(match.group(1), match.group(2)) for match in reference_pattern.finditer(text)]


def sort_key(record_id: str) -> tuple:
    """Order IDs with their numbers compared as numbers (REQ-9 before REQ-10)."""
    return tuple(
        (0, int(part), "") if part.isdigit() else (1, 0, part)
        for part in re.split(r"(\d+)", record_id)
        if part
    )
