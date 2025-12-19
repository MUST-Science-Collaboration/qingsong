"""Tests for Qingsong core functionality."""

import pytest
from pathlib import Path


def test_import():
    """Test that the package can be imported."""
    import qingsong
    assert qingsong.__version__ == "0.1.0"


def test_models_import():
    """Test that models can be imported."""
    from qingsong.models import (
        ItemType,
        Requirement,
        Risk,
        Interface,
        Document,
        DataRecord,
        Note,
    )
    assert ItemType.REQ.value == "REQ"


def test_requirement_model():
    """Test Requirement model validation."""
    from qingsong.models import Requirement
    from datetime import datetime

    req = Requirement(
        type="REQ",
        id_full="MUST-FPS-FID-REQ-001",
        title="Test Requirement",
        text="This is a test requirement",
        system_path="FPS/FID",
        owner="eng001",
        status="draft",
        category_path="functional/observation",
    )

    assert req.id_full == "MUST-FPS-FID-REQ-001"
    assert req.type.value == "REQ"
    assert req.status.value == "draft"


def test_risk_model():
    """Test Risk model validation."""
    from qingsong.models import Risk

    risk = Risk(
        type="RSK",
        id_full="MUST-FPS-FID-RSK-001",
        title="Test Risk",
        text="This is a test risk",
        system_path="FPS/FID",
        owner="eng001",
        status="active",
        category_path="technical/design",
        likelihood=3,
        consequence=4,
    )

    assert risk.risk_score == 12
    assert risk.risk_level == "Medium"


def test_link_validation():
    """Test Link model validation."""
    from qingsong.models import Link

    # Valid internal link
    link = Link(
        target_id="MUST-FPS-FID-REQ-001",
        link_type="related_to",
    )
    assert link.target_id == "MUST-FPS-FID-REQ-001"

    # Valid external link
    ext_link = Link(
        target_id="EXT:External Document",
        link_type="references",
    )
    assert ext_link.target_id.startswith("EXT:")


def test_id_format_validation():
    """Test that invalid IDs are rejected."""
    from qingsong.models import Requirement
    import pytest

    with pytest.raises(Exception):  # Pydantic ValidationError
        Requirement(
            type="REQ",
            id_full="INVALID-ID",  # Wrong format
            title="Test",
            text="Test",
            system_path="FPS/FID",
            owner="eng001",
            status="draft",
            category_path="functional/observation",
        )


def test_metadata_loading(tmp_path):
    """Test metadata loading with sample files."""
    # This test would require setting up sample metadata files
    # For now, just verify the loader can be imported
    from qingsong.load_meta import load_metadata, validate_metadata
    # Full test would load from test fixtures


def test_core_api():
    """Test core API can be instantiated."""
    from qingsong.core import QingsongCore
    from dataclasses import fields

    # Check QingsongCore has expected fields
    field_names = [f.name for f in fields(QingsongCore)]
    assert "meta_dir" in field_names
    assert "doorstop_dir" in field_names
    assert "items" in field_names

