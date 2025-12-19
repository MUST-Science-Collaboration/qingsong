"""
Requirement model for Qingsong.

Requirements define what the system must do or achieve.
"""

from enum import Enum
from typing import Literal

from pydantic import Field

from .common import BaseItem, ItemType


class VerificationMethod(str, Enum):
    """Methods for verifying requirements."""

    TEST = "test"
    ANALYSIS = "analysis"
    INSPECTION = "inspection"
    DEMONSTRATION = "demonstration"


class RequirementPriority(str, Enum):
    """Priority levels for requirements."""

    MUST = "must"  # Mandatory requirement
    SHOULD = "should"  # Important but not critical
    MAY = "may"  # Nice to have


class Requirement(BaseItem):
    """
    Requirement item model.

    Requirements specify what the system must do, how well it must perform,
    or constraints it must satisfy.

    ID format: MUST-<L1>-<L2>-REQ-NNN
    """

    type: Literal[ItemType.REQ] = Field(
        default=ItemType.REQ,
        description="Item type (always REQ for requirements)",
    )

    # Requirement-specific fields
    category_path: str = Field(
        ...,
        description="Category path from req_category taxonomy (e.g., functional/observation)",
    )
    priority: RequirementPriority = Field(
        default=RequirementPriority.MUST,
        description="Requirement priority level",
    )
    rationale: str | None = Field(
        default=None,
        description="Rationale explaining why this requirement exists",
    )

    # Verification
    verification_method: VerificationMethod | None = Field(
        default=None,
        description="Primary method for verifying this requirement",
    )
    verification_criteria: str | None = Field(
        default=None,
        description="Specific criteria for verification success",
    )
    verified: bool = Field(
        default=False,
        description="Whether the requirement has been verified",
    )
    verified_at: str | None = Field(
        default=None,
        description="When the requirement was verified (ISO 8601)",
    )
    verified_by: str | None = Field(
        default=None,
        description="Person ID who verified the requirement",
    )

    # Traceability
    parent_requirement: str | None = Field(
        default=None,
        description="Parent requirement ID (for derived requirements)",
    )
    allocated_to: list[str] = Field(
        default_factory=list,
        description="System paths this requirement is allocated to",
    )

    # Compliance
    compliance_notes: str | None = Field(
        default=None,
        description="Notes on compliance status or approach",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "type": "REQ",
                    "id_full": "MUST-FPS-FID-REQ-001",
                    "title": "Fiber Positioning Accuracy",
                    "text": "The fiber positioner shall position fibers with an accuracy of ≤5 μm RMS.",
                    "system_path": "FPS/FID",
                    "category_path": "performance/accuracy",
                    "owner": "eng001",
                    "status": "active",
                    "priority": "must",
                    "verification_method": "test",
                }
            ]
        }
    }

