"""
Metadata loader for Qingsong.

Loads and validates metadata from YAML files and generates dynamic enums
for controlled vocabularies.

Design Decision:
----------------
Dynamic enums are generated at runtime rather than as a build step. This ensures
enums are always in sync with metadata and doesn't require a separate generation
step. The generated enums are cached in memory for performance.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from . import META_DIR


@dataclass
class Person:
    """Person record from people.yaml."""

    id: str
    name: str
    email: str
    role: str
    organization: str
    systems: list[str]
    active: bool


@dataclass
class SystemNode:
    """Hierarchy node representing a system/subsystem."""

    id: str
    name: str
    description: str
    owner: str
    tasks: list[str] = field(default_factory=list)
    subsystems: dict[str, "SystemNode"] = field(default_factory=dict)


@dataclass
class LinkTypeDefinition:
    """Link type definition from link_types.yaml."""

    name: str
    label: str
    description: str
    reverse_label: str
    allowed_source_types: list[str]
    allowed_target_types: list[str]
    cardinality: str
    bidirectional: bool = False
    same_type_only: bool = False


@dataclass
class VocabItem:
    """Single vocabulary item."""

    value: str
    label: str
    description: str
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Vocabulary:
    """Controlled vocabulary."""

    name: str
    description: str
    items: list[VocabItem]
    valid_values: list[str]


@dataclass
class Metadata:
    """Complete metadata loaded from files."""

    # Hierarchy
    project_id: str
    project_name: str
    project_description: str
    systems: dict[str, SystemNode]
    valid_system_paths: list[str]
    valid_l3_codes: list[str]

    # People
    people: dict[str, Person]
    valid_person_ids: list[str]

    # Vocabularies
    status_vocab: Vocabulary
    req_category_vocab: Vocabulary
    risk_category_vocab: Vocabulary
    ifc_type_vocab: Vocabulary
    link_types: dict[str, LinkTypeDefinition]
    valid_link_types: list[str]

    # Glossary
    glossary: dict[str, dict[str, str]]


# Global cache for metadata
_metadata_cache: Metadata | None = None
_dynamic_enums: dict[str, type[Enum]] = {}


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file using ruamel.yaml."""
    yaml = YAML(typ="safe")
    with open(path) as f:
        return yaml.load(f)


def _parse_hierarchy(data: dict[str, Any]) -> tuple[
    str, str, str, dict[str, SystemNode], list[str], list[str]
]:
    """Parse hierarchy.yaml into structured data."""
    project = data.get("project", {})
    project_id = project.get("id", "MUST")
    project_name = project.get("name", "")
    project_description = project.get("description", "")

    systems: dict[str, SystemNode] = {}
    systems_data = data.get("systems", {})

    for sys_id, sys_data in systems_data.items():
        subsystems: dict[str, SystemNode] = {}
        for sub_id, sub_data in sys_data.get("subsystems", {}).items():
            subsystems[sub_id] = SystemNode(
                id=sub_id,
                name=sub_data.get("name", ""),
                description=sub_data.get("description", ""),
                owner=sub_data.get("owner", ""),
                tasks=sub_data.get("tasks", []),
            )

        systems[sys_id] = SystemNode(
            id=sys_id,
            name=sys_data.get("name", ""),
            description=sys_data.get("description", ""),
            owner=sys_data.get("owner", ""),
            subsystems=subsystems,
        )

    valid_system_paths = data.get("valid_system_paths", [])
    valid_l3_codes = data.get("valid_l3_codes", [])

    return (
        project_id,
        project_name,
        project_description,
        systems,
        valid_system_paths,
        valid_l3_codes,
    )


def _parse_people(data: dict[str, Any]) -> tuple[dict[str, Person], list[str]]:
    """Parse people.yaml into structured data."""
    people: dict[str, Person] = {}
    people_data = data.get("people", {})

    for person_id, person_data in people_data.items():
        people[person_id] = Person(
            id=person_id,
            name=person_data.get("name", ""),
            email=person_data.get("email", ""),
            role=person_data.get("role", ""),
            organization=person_data.get("organization", ""),
            systems=person_data.get("systems", []),
            active=person_data.get("active", True),
        )

    valid_person_ids = data.get("valid_person_ids", list(people.keys()))

    return people, valid_person_ids


def _parse_vocab(name: str, data: dict[str, Any]) -> Vocabulary:
    """Parse a vocabulary file into structured data."""
    description = data.get("description", "")
    valid_values = data.get("valid_values", data.get("valid_paths", []))

    items: list[VocabItem] = []

    # Handle flat value structure
    if "values" in data:
        for value, value_data in data["values"].items():
            if isinstance(value_data, dict):
                items.append(VocabItem(
                    value=value,
                    label=value_data.get("label", value),
                    description=value_data.get("description", ""),
                    extra=value_data,
                ))
            else:
                items.append(VocabItem(
                    value=value,
                    label=str(value_data),
                    description="",
                ))

    # Handle hierarchical category structure
    if "categories" in data:
        for cat_id, cat_data in data["categories"].items():
            if isinstance(cat_data, dict) and "subcategories" in cat_data:
                for sub_id, sub_data in cat_data["subcategories"].items():
                    path = f"{cat_id}/{sub_id}"
                    items.append(VocabItem(
                        value=path,
                        label=sub_data.get("label", sub_id),
                        description=sub_data.get("description", ""),
                    ))

    # Handle interface types structure
    if "types" in data:
        for type_id, type_data in data["types"].items():
            if isinstance(type_data, dict) and "subtypes" in type_data:
                for sub_id, sub_data in type_data["subtypes"].items():
                    path = f"{type_id}/{sub_id}"
                    items.append(VocabItem(
                        value=path,
                        label=sub_data.get("label", sub_id),
                        description=sub_data.get("description", ""),
                    ))

    return Vocabulary(
        name=name,
        description=description,
        items=items,
        valid_values=valid_values,
    )


def _parse_link_types(data: dict[str, Any]) -> tuple[dict[str, LinkTypeDefinition], list[str]]:
    """Parse link_types.yaml into structured data."""
    link_types: dict[str, LinkTypeDefinition] = {}
    link_types_data = data.get("link_types", {})

    for lt_name, lt_data in link_types_data.items():
        link_types[lt_name] = LinkTypeDefinition(
            name=lt_name,
            label=lt_data.get("label", lt_name),
            description=lt_data.get("description", ""),
            reverse_label=lt_data.get("reverse_label", lt_name),
            allowed_source_types=lt_data.get("allowed_source_types", []),
            allowed_target_types=lt_data.get("allowed_target_types", []),
            cardinality=lt_data.get("cardinality", "many-to-many"),
            bidirectional=lt_data.get("bidirectional", False),
            same_type_only=lt_data.get("same_type_only", False),
        )

    valid_link_types = data.get("valid_link_types", list(link_types.keys()))

    return link_types, valid_link_types


def load_metadata(meta_dir: Path | None = None, force_reload: bool = False) -> Metadata:
    """
    Load all metadata from YAML files.

    Args:
        meta_dir: Path to metadata directory. Defaults to project META_DIR.
        force_reload: Force reload even if cached.

    Returns:
        Metadata object with all loaded data.
    """
    global _metadata_cache

    if _metadata_cache is not None and not force_reload:
        return _metadata_cache

    if meta_dir is None:
        meta_dir = META_DIR

    # Load hierarchy
    hierarchy_data = _load_yaml(meta_dir / "hierarchy.yaml")
    (
        project_id,
        project_name,
        project_description,
        systems,
        valid_system_paths,
        valid_l3_codes,
    ) = _parse_hierarchy(hierarchy_data)

    # Load people
    people_data = _load_yaml(meta_dir / "people.yaml")
    people, valid_person_ids = _parse_people(people_data)

    # Load vocabularies
    vocab_dir = meta_dir / "vocab"
    status_vocab = _parse_vocab("status", _load_yaml(vocab_dir / "status.yaml"))
    req_category_vocab = _parse_vocab(
        "req_category", _load_yaml(vocab_dir / "req_category.yaml")
    )
    risk_category_vocab = _parse_vocab(
        "risk_category", _load_yaml(vocab_dir / "risk_category.yaml")
    )
    ifc_type_vocab = _parse_vocab("ifc_type", _load_yaml(vocab_dir / "ifc_type.yaml"))

    # Load link types
    link_types_data = _load_yaml(vocab_dir / "link_types.yaml")
    link_types, valid_link_types = _parse_link_types(link_types_data)

    # Load glossary
    glossary_data = _load_yaml(meta_dir / "glossary.yaml")
    glossary = glossary_data.get("terms", {})

    metadata = Metadata(
        project_id=project_id,
        project_name=project_name,
        project_description=project_description,
        systems=systems,
        valid_system_paths=valid_system_paths,
        valid_l3_codes=valid_l3_codes,
        people=people,
        valid_person_ids=valid_person_ids,
        status_vocab=status_vocab,
        req_category_vocab=req_category_vocab,
        risk_category_vocab=risk_category_vocab,
        ifc_type_vocab=ifc_type_vocab,
        link_types=link_types,
        valid_link_types=valid_link_types,
        glossary=glossary,
    )

    _metadata_cache = metadata
    return metadata


def get_dynamic_enum(name: str, values: list[str]) -> type[Enum]:
    """
    Get or create a dynamic enum from a list of values.

    Args:
        name: Name for the enum class.
        values: List of valid values.

    Returns:
        Dynamically created Enum class.
    """
    cache_key = f"{name}:{','.join(sorted(values))}"
    if cache_key in _dynamic_enums:
        return _dynamic_enums[cache_key]

    # Create enum members: normalize values to valid Python identifiers
    members = {}
    for value in values:
        # Replace special characters with underscores
        member_name = value.upper().replace("/", "_").replace("-", "_").replace(" ", "_")
        members[member_name] = value

    enum_class = Enum(name, members)
    _dynamic_enums[cache_key] = enum_class
    return enum_class


def get_person_enum(metadata: Metadata | None = None) -> type[Enum]:
    """Get enum of valid person IDs."""
    if metadata is None:
        metadata = load_metadata()
    return get_dynamic_enum("PersonID", metadata.valid_person_ids)


def get_system_path_enum(metadata: Metadata | None = None) -> type[Enum]:
    """Get enum of valid system paths."""
    if metadata is None:
        metadata = load_metadata()
    return get_dynamic_enum("SystemPath", metadata.valid_system_paths)


def get_l3_enum(metadata: Metadata | None = None) -> type[Enum]:
    """Get enum of valid L3 codes."""
    if metadata is None:
        metadata = load_metadata()
    return get_dynamic_enum("L3Code", metadata.valid_l3_codes)


def get_link_type_enum(metadata: Metadata | None = None) -> type[Enum]:
    """Get enum of valid link types."""
    if metadata is None:
        metadata = load_metadata()
    return get_dynamic_enum("LinkType", metadata.valid_link_types)


def validate_metadata(meta_dir: Path | None = None) -> list[str]:
    """
    Validate metadata files for consistency.

    Args:
        meta_dir: Path to metadata directory.

    Returns:
        List of validation error messages. Empty list means valid.
    """
    errors: list[str] = []

    if meta_dir is None:
        meta_dir = META_DIR

    # Check required files exist
    required_files = [
        "hierarchy.yaml",
        "people.yaml",
        "glossary.yaml",
        "vocab/status.yaml",
        "vocab/req_category.yaml",
        "vocab/risk_category.yaml",
        "vocab/ifc_type.yaml",
        "vocab/link_types.yaml",
    ]

    for fname in required_files:
        fpath = meta_dir / fname
        if not fpath.exists():
            errors.append(f"Missing required metadata file: {fname}")

    if errors:
        return errors

    # Load and validate metadata
    try:
        metadata = load_metadata(meta_dir, force_reload=True)
    except Exception as e:
        errors.append(f"Failed to load metadata: {e}")
        return errors

    # Validate owner references in hierarchy
    for sys_id, system in metadata.systems.items():
        if system.owner and system.owner not in metadata.valid_person_ids:
            errors.append(
                f"Invalid owner '{system.owner}' for system '{sys_id}'"
            )
        for sub_id, subsystem in system.subsystems.items():
            if subsystem.owner and subsystem.owner not in metadata.valid_person_ids:
                errors.append(
                    f"Invalid owner '{subsystem.owner}' for subsystem '{sys_id}/{sub_id}'"
                )

    # Validate system paths match hierarchy
    for path in metadata.valid_system_paths:
        parts = path.split("/")
        if len(parts) != 2:
            errors.append(f"Invalid system path format: {path}")
            continue
        l1, l2 = parts
        if l1 not in metadata.systems:
            errors.append(f"System path references unknown L1: {path}")
        elif l2 not in metadata.systems[l1].subsystems:
            errors.append(f"System path references unknown L2: {path}")

    # Validate L3 codes match hierarchy
    for l3 in metadata.valid_l3_codes:
        found = False
        for system in metadata.systems.values():
            for subsystem in system.subsystems.values():
                if l3 in subsystem.tasks:
                    found = True
                    break
            if found:
                break
        if not found:
            errors.append(f"L3 code '{l3}' not found in any subsystem tasks")

    # Validate link type definitions
    valid_item_types = {"REQ", "RSK", "IFC", "DOC", "DAT", "NOTE"}
    for lt_name, lt_def in metadata.link_types.items():
        for src_type in lt_def.allowed_source_types:
            if src_type not in valid_item_types:
                errors.append(
                    f"Link type '{lt_name}' has invalid source type: {src_type}"
                )
        for dst_type in lt_def.allowed_target_types:
            if dst_type not in valid_item_types:
                errors.append(
                    f"Link type '{lt_name}' has invalid target type: {dst_type}"
                )

    return errors


def clear_cache() -> None:
    """Clear the metadata cache."""
    global _metadata_cache, _dynamic_enums
    _metadata_cache = None
    _dynamic_enums = {}

