"""
Interface model for Qingsong.

Interfaces define connections between systems or components.
"""

from enum import Enum
from typing import Literal

from pydantic import Field, model_validator

from .common import BaseItem, ItemType


class InterfaceStatus(str, Enum):
    """Interface-specific status values."""

    PROPOSED = "proposed"
    AGREED = "agreed"
    CONTROLLED = "controlled"
    VERIFIED = "verified"
    OBSOLETE = "obsolete"


class Interface(BaseItem):
    """
    Interface item model.

    Interfaces define the physical, electrical, optical, thermal, or software
    connections between systems or components.

    ID format: MUST-<L1>-<L2>-IFC-NNN
    """

    type: Literal[ItemType.IFC] = Field(
        default=ItemType.IFC,
        description="Item type (always IFC for interfaces)",
    )

    # Interface-specific fields
    category_path: str = Field(
        ...,
        description="Interface type path from ifc_type taxonomy (e.g., mechanical/mounting)",
    )

    # Interface parties
    provider_system: str = Field(
        ...,
        description="System path providing/owning this interface",
    )
    consumer_system: str = Field(
        ...,
        description="System path consuming/using this interface",
    )
    provider_owner: str | None = Field(
        default=None,
        description="Person ID responsible on provider side",
    )
    consumer_owner: str | None = Field(
        default=None,
        description="Person ID responsible on consumer side",
    )

    # Interface status
    interface_status: InterfaceStatus = Field(
        default=InterfaceStatus.PROPOSED,
        description="Interface control status",
    )
    icd_document: str | None = Field(
        default=None,
        description="Reference to Interface Control Document",
    )
    icd_version: str | None = Field(
        default=None,
        description="ICD version number",
    )

    # Technical specification
    specification: str | None = Field(
        default=None,
        description="Detailed technical specification (markdown)",
    )
    parameters: dict[str, str] = Field(
        default_factory=dict,
        description="Key interface parameters as key-value pairs",
    )
    tolerances: dict[str, str] = Field(
        default_factory=dict,
        description="Tolerance specifications as key-value pairs",
    )

    # Verification
    verification_method: str | None = Field(
        default=None,
        description="Method for verifying interface compliance",
    )
    verification_status: str | None = Field(
        default=None,
        description="Current verification status",
    )

    # Change control
    change_control_level: str | None = Field(
        default=None,
        description="Level of change control (e.g., CCB, project, subsystem)",
    )
    last_review_date: str | None = Field(
        default=None,
        description="Date of last interface review",
    )
    next_review_date: str | None = Field(
        default=None,
        description="Scheduled next review date",
    )

    @model_validator(mode="after")
    def validate_different_parties(self) -> "Interface":
        """Ensure provider and consumer are different systems."""
        if self.provider_system == self.consumer_system:
            raise ValueError(
                "Provider and consumer systems must be different"
            )
        return self

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "type": "IFC",
                    "id_full": "MUST-FPS-FID-IFC-001",
                    "title": "Fiber-to-Spectrograph Optical Interface",
                    "text": "Defines the optical interface between fiber positioner output and spectrograph slit.",
                    "system_path": "FPS/FID",
                    "category_path": "optical/fiber",
                    "owner": "eng002",
                    "status": "active",
                    "provider_system": "FPS/FID",
                    "consumer_system": "SPS/OPT",
                    "interface_status": "agreed",
                    "parameters": {
                        "fiber_diameter": "100 μm",
                        "numerical_aperture": "0.22",
                        "wavelength_range": "360-980 nm",
                    },
                }
            ]
        }
    }

