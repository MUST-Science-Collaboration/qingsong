"""
Risk model for Qingsong.

Risks represent potential problems that could impact the project.
"""

from enum import Enum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .common import BaseItem, ItemType


class RiskStatus(str, Enum):
    """Risk-specific status values."""

    IDENTIFIED = "identified"
    ANALYZING = "analyzing"
    MITIGATING = "mitigating"
    MONITORING = "monitoring"
    CLOSED = "closed"
    REALIZED = "realized"


class Risk(BaseItem):
    """
    Risk item model.

    Risks identify potential problems, their likelihood and consequences,
    and mitigation strategies.

    ID format: MUST-<L1>-<L2>-RSK-NNN
    """

    type: Literal[ItemType.RSK] = Field(
        default=ItemType.RSK,
        description="Item type (always RSK for risks)",
    )

    # Risk-specific fields
    category_path: str = Field(
        ...,
        description="Category path from risk_category taxonomy (e.g., technical/design)",
    )

    # Risk assessment (1-5 scale)
    likelihood: int = Field(
        ...,
        ge=1,
        le=5,
        description="Likelihood rating (1=Rare to 5=Almost Certain)",
    )
    consequence: int = Field(
        ...,
        ge=1,
        le=5,
        description="Consequence rating (1=Negligible to 5=Catastrophic)",
    )

    # Risk score is computed but can be stored
    risk_score: int | None = Field(
        default=None,
        description="Risk score (likelihood × consequence)",
    )

    # Risk handling
    risk_status: RiskStatus = Field(
        default=RiskStatus.IDENTIFIED,
        description="Current status in risk handling process",
    )
    mitigation_strategy: str | None = Field(
        default=None,
        description="Description of mitigation approach",
    )
    mitigation_owner: str | None = Field(
        default=None,
        description="Person ID responsible for mitigation",
    )
    contingency_plan: str | None = Field(
        default=None,
        description="Contingency plan if risk is realized",
    )

    # Residual risk after mitigation
    residual_likelihood: int | None = Field(
        default=None,
        ge=1,
        le=5,
        description="Likelihood after mitigation",
    )
    residual_consequence: int | None = Field(
        default=None,
        ge=1,
        le=5,
        description="Consequence after mitigation",
    )

    # Triggers and monitoring
    trigger_conditions: list[str] = Field(
        default_factory=list,
        description="Conditions that would trigger this risk",
    )
    monitoring_approach: str | None = Field(
        default=None,
        description="How this risk is being monitored",
    )

    # Impact
    cost_impact: str | None = Field(
        default=None,
        description="Estimated cost impact if realized",
    )
    schedule_impact: str | None = Field(
        default=None,
        description="Estimated schedule impact if realized",
    )
    technical_impact: str | None = Field(
        default=None,
        description="Description of technical impact",
    )

    # Timeline
    identified_date: str | None = Field(
        default=None,
        description="When the risk was identified (ISO 8601)",
    )
    target_closure_date: str | None = Field(
        default=None,
        description="Target date for risk closure",
    )
    closed_date: str | None = Field(
        default=None,
        description="Actual closure date if closed",
    )

    @model_validator(mode="after")
    def compute_risk_score(self) -> "Risk":
        """Compute risk score from likelihood and consequence."""
        if self.risk_score is None:
            self.risk_score = self.likelihood * self.consequence
        return self

    @property
    def risk_level(self) -> str:
        """Get risk level based on score."""
        score = self.risk_score or (self.likelihood * self.consequence)
        if score <= 6:
            return "Low"
        elif score <= 14:
            return "Medium"
        else:
            return "High"

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "type": "RSK",
                    "id_full": "MUST-FPS-FID-RSK-001",
                    "title": "Fiber Positioner Motor Failure",
                    "text": "Risk that fiber positioner motors may fail prematurely due to thermal cycling.",
                    "system_path": "FPS/FID",
                    "category_path": "technical/design",
                    "owner": "eng001",
                    "status": "active",
                    "likelihood": 3,
                    "consequence": 4,
                    "risk_status": "mitigating",
                    "mitigation_strategy": "Implement redundant motors and thermal management system.",
                }
            ]
        }
    }

