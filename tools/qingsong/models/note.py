"""
Technical/science note model for Qingsong.

Notes capture technical analyses, trade studies, and informal documentation.
"""

from enum import Enum
from typing import Literal

from pydantic import Field

from .common import BaseItem, ItemType


class NoteType(str, Enum):
    """Types of notes."""

    TECHNICAL = "technical"
    SCIENCE = "science"
    TRADE_STUDY = "trade_study"
    ANALYSIS = "analysis"
    MEETING = "meeting"
    ACTION = "action"
    DECISION = "decision"
    OTHER = "other"


class Note(BaseItem):
    """
    Technical/science note model.

    Notes capture informal documentation, trade studies,
    technical analyses, and decisions.

    ID format: MUST-<L1>-<L2>-NOTE-NNN
    """

    type: Literal[ItemType.NOTE] = Field(
        default=ItemType.NOTE,
        description="Item type (always NOTE for notes)",
    )

    # Note-specific fields
    category_path: str = Field(
        default="other",
        description="Note type category",
    )
    note_type: NoteType = Field(
        default=NoteType.OTHER,
        description="Type of note",
    )

    # Note identification
    note_number: str | None = Field(
        default=None,
        description="Internal note number (if any)",
    )
    version: str = Field(
        default="1.0",
        description="Note version",
    )

    # Authorship
    authors: list[str] = Field(
        default_factory=list,
        description="List of author person IDs",
    )

    # Content
    summary: str | None = Field(
        default=None,
        description="Brief summary or abstract",
    )
    conclusions: str | None = Field(
        default=None,
        description="Key conclusions",
    )
    recommendations: str | None = Field(
        default=None,
        description="Recommendations if any",
    )
    action_items: list[str] = Field(
        default_factory=list,
        description="Action items arising from this note",
    )

    # For trade studies
    options_considered: list[str] = Field(
        default_factory=list,
        description="Options considered (for trade studies)",
    )
    selected_option: str | None = Field(
        default=None,
        description="Selected option (for trade studies)",
    )
    selection_rationale: str | None = Field(
        default=None,
        description="Rationale for selection",
    )

    # For decisions
    decision: str | None = Field(
        default=None,
        description="The decision made (for decision notes)",
    )
    decision_date: str | None = Field(
        default=None,
        description="Date decision was made",
    )
    decision_authority: str | None = Field(
        default=None,
        description="Authority that made the decision",
    )

    # Attachments
    attachments: list[str] = Field(
        default_factory=list,
        description="List of attachment file paths",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "type": "NOTE",
                    "id_full": "MUST-FPS-FID-NOTE-001",
                    "title": "Fiber Type Trade Study",
                    "text": "Trade study comparing different fiber types for the positioner system.",
                    "system_path": "FPS/FID",
                    "category_path": "trade_study",
                    "owner": "eng002",
                    "status": "active",
                    "note_type": "trade_study",
                    "authors": ["eng001", "eng002"],
                    "options_considered": [
                        "Standard silica fiber",
                        "High-OH silica fiber",
                        "Fluoride fiber",
                    ],
                    "selected_option": "High-OH silica fiber",
                    "selection_rationale": "Best UV transmission while maintaining acceptable FRD.",
                }
            ]
        }
    }

