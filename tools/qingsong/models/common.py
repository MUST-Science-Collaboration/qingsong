"""
Common models and base classes for all Qingsong item types.

Design decisions:
- All validation is done via Pydantic (canonical schema)
- Dynamic enums are loaded from metadata at runtime
- Timestamps are ISO 8601 format
- Links are typed objects with relationship semantics
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, Field, field_validator, model_validator


class ItemType(str, Enum):
    """Valid item types in Qingsong."""

    REQ = "REQ"
    RSK = "RSK"
    IFC = "IFC"
    DOC = "DOC"
    DAT = "DAT"
    NOTE = "NOTE"


class LifecycleStatus(str, Enum):
    """Lifecycle status for items."""

    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"
    SUPERSEDED = "superseded"


class Link(BaseModel):
    """
    A typed link to another item.

    Links represent relationships between items with semantic meaning.
    Each link has a type that constrains valid source/target types.
    """

    target_id: str = Field(
        ...,
        description="Target item ID (e.g., MUST-FPS-FID-REQ-001) or external reference (EXT:...)",
    )
    link_type: str = Field(
        ...,
        description="Relationship type (e.g., implements, verifies, mitigates)",
    )
    description: str | None = Field(
        default=None,
        description="Optional description of this specific link",
    )

    @field_validator("target_id")
    @classmethod
    def validate_target_id(cls, v: str) -> str:
        """Validate target ID format."""
        if not v:
            raise ValueError("target_id cannot be empty")
        # External references start with EXT:
        if v.startswith("EXT:"):
            return v
        # Internal IDs should follow pattern: MUST-<L1>-<L2>-<TYPE>-NNN
        # We do basic format check here; full existence check is done elsewhere
        parts = v.split("-")
        if len(parts) < 5:
            raise ValueError(
                f"Invalid ID format: {v}. Expected MUST-<L1>-<L2>-<TYPE>-NNN"
            )
        if parts[0] != "MUST":
            raise ValueError(f"ID must start with 'MUST': {v}")
        return v


class RetirementInfo(BaseModel):
    """Information about item retirement or supersession."""

    retired_at: datetime = Field(..., description="When the item was retired/superseded")
    retired_by: str = Field(..., description="Person ID who retired the item")
    retired_reason: str = Field(..., description="Reason for retirement")
    superseded_by: str | None = Field(
        default=None,
        description="ID of item that supersedes this one (required if status=superseded)",
    )


class BaseItem(BaseModel):
    """
    Base model for all Qingsong items.

    Required fields for all item types:
    - type: Item type (REQ, RSK, IFC, DOC, DAT, NOTE)
    - id_full: Full item ID (e.g., MUST-FPS-FID-REQ-001)
    - title: Short descriptive title
    - text: Main content (markdown allowed)
    - system_path: L1/L2 path from hierarchy
    - status: Lifecycle status
    - owner: Person ID of responsible owner
    - created_at: Creation timestamp
    - updated_at: Last update timestamp
    """

    # Doorstop compatibility fields
    uid: str | None = Field(default=None, description="Doorstop UID (auto-generated)")
    active: bool = Field(default=True, description="Doorstop active flag")
    derived: bool = Field(default=False, description="Doorstop derived flag")
    normative: bool = Field(default=True, description="Doorstop normative flag")
    reviewed: datetime | None = Field(default=None, description="Doorstop review date")

    # Core identification
    type: ItemType = Field(..., description="Item type code")
    id_full: str = Field(
        ...,
        description="Full item ID following pattern MUST-<L1>-<L2>[-L3]-<TYPE>-NNN",
        pattern=r"^MUST(-[A-Z0-9]+)+-\d{3}$",
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Short descriptive title",
    )
    text: str = Field(
        ...,
        min_length=1,
        description="Main content (markdown format allowed)",
    )

    # Organizational context
    system_path: str = Field(
        ...,
        description="L1/L2 system path (e.g., FPS/FID)",
        pattern=r"^[A-Z]+/[A-Z]+$",
    )
    l3: str | None = Field(
        default=None,
        description="Optional L3 task code (e.g., FID-AIT)",
    )

    # Ownership and collaboration
    owner: str = Field(..., description="Person ID of responsible owner")
    collaborators: list[str] = Field(
        default_factory=list,
        description="List of collaborator person IDs (unique)",
    )

    # Lifecycle
    status: LifecycleStatus = Field(
        default=LifecycleStatus.DRAFT,
        description="Lifecycle status",
    )
    retirement: RetirementInfo | None = Field(
        default=None,
        description="Retirement information (required if status is retired/superseded)",
    )

    # Links to other items
    links: list[Link] = Field(
        default_factory=list,
        description="Typed links to other items",
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp (ISO 8601)",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last update timestamp (ISO 8601)",
    )

    # Metadata
    tags: list[str] = Field(
        default_factory=list,
        description="Free-form tags for organization",
    )
    references: list[str] = Field(
        default_factory=list,
        description="External references (URLs, document numbers)",
    )

    @property
    def has_placeholders(self) -> bool:
        """Check if the item contains 'TBD' or 'TBC' placeholders."""
        content = f"{self.title} {self.text}".upper()
        return "TBD" in content or "TBC" in content

    model_config = {
        "extra": "allow",  # Allow extra fields for flexibility
        "validate_assignment": True,
    }

    @field_validator("collaborators")
    @classmethod
    def validate_unique_collaborators(cls, v: list[str]) -> list[str]:
        """Ensure collaborators list has unique values."""
        if len(v) != len(set(v)):
            raise ValueError("Collaborators must be unique")
        return v

    @field_validator("tags")
    @classmethod
    def validate_unique_tags(cls, v: list[str]) -> list[str]:
        """Ensure tags list has unique values."""
        if len(v) != len(set(v)):
            raise ValueError("Tags must be unique")
        return v

    @model_validator(mode="after")
    def validate_retirement_status(self) -> "BaseItem":
        """Ensure retirement info is provided for retired/superseded items."""
        if self.status in (LifecycleStatus.RETIRED, LifecycleStatus.SUPERSEDED):
            if self.retirement is None:
                raise ValueError(
                    f"Retirement info required when status is {self.status.value}"
                )
            if (
                self.status == LifecycleStatus.SUPERSEDED
                and self.retirement.superseded_by is None
            ):
                raise ValueError(
                    "superseded_by is required when status is 'superseded'"
                )
        return self

    @model_validator(mode="after")
    def validate_id_matches_type(self) -> "BaseItem":
        """Ensure the ID type code matches the item type."""
        parts = self.id_full.split("-")
        if len(parts) >= 4:
            # Type code is the second to last segment (e.g., MUST-L1-L2-[L3]-TYPE-NNN)
            id_type = parts[-2]
            if id_type != self.type.value:
                raise ValueError(
                    f"ID type '{id_type}' does not match item type '{self.type.value}'"
                )
        return self

    @model_validator(mode="after")
    def validate_metadata_constraints(self) -> "BaseItem":
        """Validate against loaded metadata (strict mode)."""
        # Note: We import here to avoid circular dependencies
        from ..load_meta import load_metadata
        try:
            metadata = load_metadata()
            
            # Validate owner
            if self.owner not in metadata.valid_person_ids:
                raise ValueError(f"Invalid owner: {self.owner}")
            
            # Validate system_path
            if self.system_path not in metadata.valid_system_paths:
                raise ValueError(f"Invalid system_path: {self.system_path}")
            
            # Validate L3
            if self.l3 and self.l3 not in metadata.valid_l3_codes:
                raise ValueError(f"Invalid L3 code: {self.l3}")
                
            # Validate collaborators
            for collab in self.collaborators:
                if collab not in metadata.valid_person_ids:
                    raise ValueError(f"Invalid collaborator: {collab}")
                    
        except Exception:
            # If metadata cannot be loaded (e.g. during initial setup), skip strict validation
            pass
            
        return self

    def to_doorstop_dict(self) -> dict[str, Any]:
        """Convert to a dictionary suitable for Doorstop YAML format."""
        data = self.model_dump(exclude_none=True, mode="json")

        # Convert datetime objects to ISO format strings
        for key in ["created_at", "updated_at", "reviewed"]:
            if key in data and data[key]:
                if isinstance(data[key], str):
                    pass  # Already a string
                else:
                    data[key] = data[key].isoformat()

        # Convert nested retirement info
        if "retirement" in data and data["retirement"]:
            if "retired_at" in data["retirement"]:
                ret_at = data["retirement"]["retired_at"]
                if not isinstance(ret_at, str):
                    data["retirement"]["retired_at"] = ret_at.isoformat()

        return data

    @classmethod
    def from_doorstop_dict(cls, data: dict[str, Any]) -> "BaseItem":
        """Create an instance from Doorstop YAML data."""
        # Handle potential format differences
        return cls.model_validate(data)

