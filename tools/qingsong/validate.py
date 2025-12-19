"""
Validation module for Qingsong.

Performs comprehensive validation of items including:
- Pydantic model validation (per-item schema)
- Referential integrity (owners, systems, categories exist)
- Link validation (targets exist, types are valid)
- Lifecycle rules (retirement constraints)
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .doorstop_io import load_all_items
from .load_meta import Metadata, load_metadata
from .models import BaseItem, ItemType


@dataclass
class ValidationError:
    """A single validation error."""

    item_id: str
    field: str
    message: str
    severity: str = "error"  # error, warning

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.item_id} - {self.field}: {self.message}"


@dataclass
class ValidationResult:
    """Result of validation."""

    valid: bool
    errors: list[ValidationError]
    warnings: list[ValidationError]
    item_count: int

    def __str__(self) -> str:
        lines = [
            f"Validation {'PASSED' if self.valid else 'FAILED'}",
            f"Items validated: {self.item_count}",
            f"Errors: {len(self.errors)}",
            f"Warnings: {len(self.warnings)}",
        ]
        if self.errors:
            lines.append("\nErrors:")
            for err in self.errors:
                lines.append(f"  {err}")
        if self.warnings:
            lines.append("\nWarnings:")
            for warn in self.warnings:
                lines.append(f"  {warn}")
        return "\n".join(lines)


def validate_owner(
    item: BaseItem,
    metadata: Metadata,
) -> list[ValidationError]:
    """Validate item owner exists in people metadata."""
    errors = []

    if item.owner not in metadata.valid_person_ids:
        errors.append(ValidationError(
            item_id=item.id_full,
            field="owner",
            message=f"Owner '{item.owner}' not found in people metadata",
        ))

    # Check collaborators
    for collab in item.collaborators:
        if collab not in metadata.valid_person_ids:
            errors.append(ValidationError(
                item_id=item.id_full,
                field="collaborators",
                message=f"Collaborator '{collab}' not found in people metadata",
            ))

    return errors


def validate_system_path(
    item: BaseItem,
    metadata: Metadata,
) -> list[ValidationError]:
    """Validate item system_path exists in hierarchy."""
    errors = []

    if item.system_path not in metadata.valid_system_paths:
        errors.append(ValidationError(
            item_id=item.id_full,
            field="system_path",
            message=f"System path '{item.system_path}' not found in hierarchy",
        ))

    # Validate L3 if provided
    if item.l3 and item.l3 not in metadata.valid_l3_codes:
        errors.append(ValidationError(
            item_id=item.id_full,
            field="l3",
            message=f"L3 code '{item.l3}' not found in hierarchy",
        ))

    return errors


def validate_category_path(
    item: BaseItem,
    metadata: Metadata,
) -> list[ValidationError]:
    """Validate item category_path exists in appropriate vocabulary."""
    errors = []

    # Get the category_path attribute if it exists
    category_path = getattr(item, "category_path", None)
    if category_path is None:
        return errors

    # Determine which vocabulary to check
    if item.type == ItemType.REQ:
        valid_paths = metadata.req_category_vocab.valid_values
        vocab_name = "req_category"
    elif item.type == ItemType.RSK:
        valid_paths = metadata.risk_category_vocab.valid_values
        vocab_name = "risk_category"
    elif item.type == ItemType.IFC:
        valid_paths = metadata.ifc_type_vocab.valid_values
        vocab_name = "ifc_type"
    else:
        # DOC, DAT, NOTE have free-form category paths
        return errors

    if category_path not in valid_paths:
        errors.append(ValidationError(
            item_id=item.id_full,
            field="category_path",
            message=f"Category path '{category_path}' not found in {vocab_name} vocabulary",
        ))

    return errors


def validate_links(
    item: BaseItem,
    all_items: dict[str, BaseItem],
    metadata: Metadata,
) -> list[ValidationError]:
    """Validate item links: targets exist and types are valid."""
    errors = []

    for link in item.links:
        target_id = link.target_id
        link_type = link.link_type

        # Check if link type is valid
        if link_type not in metadata.valid_link_types:
            errors.append(ValidationError(
                item_id=item.id_full,
                field="links",
                message=f"Invalid link type '{link_type}' for link to '{target_id}'",
            ))
            continue

        # External links (EXT:...) are allowed without existence check
        if target_id.startswith("EXT:"):
            continue

        # Check target exists
        if target_id not in all_items:
            errors.append(ValidationError(
                item_id=item.id_full,
                field="links",
                message=f"Link target '{target_id}' does not exist",
            ))
            continue

        # Validate link type constraints
        link_def = metadata.link_types.get(link_type)
        if link_def:
            # Check source type constraint
            if item.type.value not in link_def.allowed_source_types:
                errors.append(ValidationError(
                    item_id=item.id_full,
                    field="links",
                    message=(
                        f"Link type '{link_type}' does not allow source type "
                        f"'{item.type.value}' (allowed: {link_def.allowed_source_types})"
                    ),
                ))

            # Check target type constraint
            target_item = all_items[target_id]
            if target_item.type.value not in link_def.allowed_target_types:
                errors.append(ValidationError(
                    item_id=item.id_full,
                    field="links",
                    message=(
                        f"Link type '{link_type}' does not allow target type "
                        f"'{target_item.type.value}' (allowed: {link_def.allowed_target_types})"
                    ),
                ))

            # Check same_type_only constraint
            if link_def.same_type_only and item.type != target_item.type:
                errors.append(ValidationError(
                    item_id=item.id_full,
                    field="links",
                    message=(
                        f"Link type '{link_type}' requires same type for source and target, "
                        f"but found {item.type.value} -> {target_item.type.value}"
                    ),
                ))

    return errors


def validate_id_format(item: BaseItem) -> list[ValidationError]:
    """Validate item ID follows required format."""
    errors = []

    parts = item.id_full.split("-")
    if len(parts) != 5:
        errors.append(ValidationError(
            item_id=item.id_full,
            field="id_full",
            message=f"ID should have 5 parts (MUST-L1-L2-TYPE-NNN), got {len(parts)}",
        ))
        return errors

    prefix, l1, l2, type_code, num = parts

    if prefix != "MUST":
        errors.append(ValidationError(
            item_id=item.id_full,
            field="id_full",
            message=f"ID must start with 'MUST', got '{prefix}'",
        ))

    if type_code != item.type.value:
        errors.append(ValidationError(
            item_id=item.id_full,
            field="id_full",
            message=f"ID type code '{type_code}' does not match item type '{item.type.value}'",
        ))

    # Check number is 3 digits
    if not num.isdigit() or len(num) != 3:
        errors.append(ValidationError(
            item_id=item.id_full,
            field="id_full",
            message=f"ID number should be 3 digits, got '{num}'",
        ))

    # Check system path consistency
    expected_path = f"{l1}/{l2}"
    if item.system_path != expected_path:
        errors.append(ValidationError(
            item_id=item.id_full,
            field="id_full",
            message=(
                f"ID system path ({expected_path}) does not match "
                f"item system_path ({item.system_path})"
            ),
            severity="warning",
        ))

    return errors


def validate_retirement(item: BaseItem) -> list[ValidationError]:
    """Validate retirement information for retired/superseded items."""
    errors = []

    # This is largely handled by Pydantic model validators,
    # but we add additional checks here
    if item.status.value in ("retired", "superseded"):
        if item.retirement is None:
            errors.append(ValidationError(
                item_id=item.id_full,
                field="retirement",
                message=f"Retirement info required for status '{item.status.value}'",
            ))
        elif item.status.value == "superseded" and not item.retirement.superseded_by:
            errors.append(ValidationError(
                item_id=item.id_full,
                field="retirement.superseded_by",
                message="superseded_by is required for superseded items",
            ))

    return errors


def validate_item(
    item: BaseItem,
    all_items: dict[str, BaseItem],
    metadata: Metadata,
) -> list[ValidationError]:
    """
    Perform all validations on a single item.

    Args:
        item: Item to validate.
        all_items: All items for cross-reference validation.
        metadata: Loaded metadata for vocabulary validation.

    Returns:
        List of validation errors.
    """
    errors = []

    errors.extend(validate_id_format(item))
    errors.extend(validate_owner(item, metadata))
    errors.extend(validate_system_path(item, metadata))
    errors.extend(validate_category_path(item, metadata))
    errors.extend(validate_links(item, all_items, metadata))
    errors.extend(validate_retirement(item))

    return errors


def validate_all(
    base_dir: Path | None = None,
    meta_dir: Path | None = None,
) -> ValidationResult:
    """
    Validate all items in the repository.

    Args:
        base_dir: Doorstop base directory.
        meta_dir: Metadata directory.

    Returns:
        ValidationResult with all errors and warnings.
    """
    # Load metadata
    metadata = load_metadata(meta_dir, force_reload=True)

    # Load all items
    all_items = load_all_items(base_dir)

    errors: list[ValidationError] = []
    warnings: list[ValidationError] = []

    # Validate each item
    for item in all_items.values():
        item_errors = validate_item(item, all_items, metadata)
        for err in item_errors:
            if err.severity == "warning":
                warnings.append(err)
            else:
                errors.append(err)

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        item_count=len(all_items),
    )


def validate_single_item(
    item_id: str,
    base_dir: Path | None = None,
    meta_dir: Path | None = None,
) -> ValidationResult:
    """
    Validate a single item by ID.

    Args:
        item_id: ID of item to validate.
        base_dir: Doorstop base directory.
        meta_dir: Metadata directory.

    Returns:
        ValidationResult for the single item.
    """
    metadata = load_metadata(meta_dir, force_reload=True)
    all_items = load_all_items(base_dir)

    if item_id not in all_items:
        return ValidationResult(
            valid=False,
            errors=[ValidationError(
                item_id=item_id,
                field="id_full",
                message=f"Item '{item_id}' not found",
            )],
            warnings=[],
            item_count=0,
        )

    item = all_items[item_id]
    item_errors = validate_item(item, all_items, metadata)

    errors = [e for e in item_errors if e.severity == "error"]
    warnings = [e for e in item_errors if e.severity == "warning"]

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        item_count=1,
    )

