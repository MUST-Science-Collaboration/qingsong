"""
Data record model for Qingsong.

Data records track technical data products, measurements, and test results.
"""

from enum import Enum
from typing import Literal

from pydantic import Field

from .common import BaseItem, ItemType


class DataType(str, Enum):
    """Types of technical data."""

    MEASUREMENT = "measurement"
    TEST_RESULT = "test_result"
    SIMULATION = "simulation"
    CALIBRATION = "calibration"
    ANALYSIS = "analysis"
    MODEL = "model"
    DATASET = "dataset"
    OTHER = "other"


class DataRecord(BaseItem):
    """
    Data record model.

    Data records track technical data products with metadata
    for provenance and retrieval.

    ID format: MUST-<L1>-<L2>-DAT-NNN
    """

    type: Literal[ItemType.DAT] = Field(
        default=ItemType.DAT,
        description="Item type (always DAT for data records)",
    )

    # Data-specific fields
    category_path: str = Field(
        default="other",
        description="Data type category",
    )
    data_type: DataType = Field(
        default=DataType.OTHER,
        description="Type of data",
    )

    # Data identification
    data_id: str | None = Field(
        default=None,
        description="Unique data identifier or reference number",
    )
    version: str = Field(
        default="1.0",
        description="Data version",
    )
    acquisition_date: str | None = Field(
        default=None,
        description="Date data was acquired (ISO 8601)",
    )

    # Storage location
    file_path: str | None = Field(
        default=None,
        description="Relative path to data file(s) in assets/",
    )
    external_url: str | None = Field(
        default=None,
        description="External URL if data is hosted elsewhere",
    )
    file_format: str | None = Field(
        default=None,
        description="File format (e.g., fits, csv, hdf5)",
    )
    file_size_mb: float | None = Field(
        default=None,
        description="File size in megabytes",
    )

    # Provenance
    instrument: str | None = Field(
        default=None,
        description="Instrument or equipment used",
    )
    conditions: str | None = Field(
        default=None,
        description="Environmental/test conditions",
    )
    processing_level: str | None = Field(
        default=None,
        description="Level of data processing (raw, reduced, calibrated)",
    )
    processing_notes: str | None = Field(
        default=None,
        description="Notes on data processing",
    )

    # Quality
    quality_flag: str | None = Field(
        default=None,
        description="Data quality indicator",
    )
    validation_status: str | None = Field(
        default=None,
        description="Validation status",
    )
    uncertainty: str | None = Field(
        default=None,
        description="Measurement uncertainty or error estimate",
    )

    # Results summary
    key_results: dict[str, str] = Field(
        default_factory=dict,
        description="Key results as key-value pairs",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "type": "DAT",
                    "id_full": "MUST-FPS-FID-DAT-001",
                    "title": "Fiber Positioner Accuracy Test Results",
                    "text": "Measurement results from fiber positioner accuracy testing.",
                    "system_path": "FPS/FID",
                    "category_path": "test_result",
                    "owner": "eng001",
                    "status": "active",
                    "data_type": "test_result",
                    "acquisition_date": "2024-03-15",
                    "instrument": "Coordinate Measuring Machine",
                    "key_results": {
                        "rms_accuracy": "3.2 μm",
                        "max_error": "8.1 μm",
                        "samples": "500",
                    },
                }
            ]
        }
    }

