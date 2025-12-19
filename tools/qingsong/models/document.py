"""
Document record model for Qingsong.

Documents represent formal project documents, reports, and publications.
"""

from enum import Enum
from typing import Literal

from pydantic import Field

from .common import BaseItem, ItemType


class DocumentType(str, Enum):
    """Types of documents."""

    REPORT = "report"
    SPECIFICATION = "specification"
    DESIGN = "design"
    PROCEDURE = "procedure"
    PLAN = "plan"
    REVIEW = "review"
    PUBLICATION = "publication"
    PRESENTATION = "presentation"
    MEMO = "memo"
    OTHER = "other"


class Document(BaseItem):
    """
    Document record model.

    Documents track formal project documentation with metadata
    for traceability and retrieval.

    ID format: MUST-<L1>-<L2>-DOC-NNN
    """

    type: Literal[ItemType.DOC] = Field(
        default=ItemType.DOC,
        description="Item type (always DOC for documents)",
    )

    # Document-specific fields
    category_path: str = Field(
        default="other",
        description="Document type category",
    )
    document_type: DocumentType = Field(
        default=DocumentType.OTHER,
        description="Type of document",
    )

    # Document identification
    document_number: str | None = Field(
        default=None,
        description="Official document number (if any)",
    )
    version: str = Field(
        default="1.0",
        description="Document version",
    )
    revision_date: str | None = Field(
        default=None,
        description="Date of current revision (ISO 8601)",
    )

    # Authorship
    authors: list[str] = Field(
        default_factory=list,
        description="List of author person IDs",
    )
    approver: str | None = Field(
        default=None,
        description="Person ID who approved the document",
    )
    approval_date: str | None = Field(
        default=None,
        description="Approval date (ISO 8601)",
    )

    # Storage location
    file_path: str | None = Field(
        default=None,
        description="Relative path to document file in assets/",
    )
    external_url: str | None = Field(
        default=None,
        description="External URL if document is hosted elsewhere",
    )
    file_format: str | None = Field(
        default=None,
        description="File format (e.g., pdf, docx, md)",
    )
    file_size_kb: int | None = Field(
        default=None,
        description="File size in kilobytes",
    )

    # Classification
    access_level: str = Field(
        default="internal",
        description="Access level (public, internal, restricted)",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="Keywords for search",
    )
    abstract: str | None = Field(
        default=None,
        description="Document abstract or summary",
    )

    # Review status
    review_status: str | None = Field(
        default=None,
        description="Current review status",
    )
    review_comments: str | None = Field(
        default=None,
        description="Summary of review comments",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "type": "DOC",
                    "id_full": "MUST-FPS-FID-DOC-001",
                    "title": "Fiber Positioner Design Report",
                    "text": "Detailed design report for the MUST fiber positioner system.",
                    "system_path": "FPS/FID",
                    "category_path": "design",
                    "owner": "eng001",
                    "status": "active",
                    "document_type": "design",
                    "document_number": "MUST-FPS-FID-DDR-001",
                    "version": "2.1",
                    "authors": ["eng001", "eng002"],
                    "file_path": "docs/FPS/FID/design_report_v2.1.pdf",
                }
            ]
        }
    }

