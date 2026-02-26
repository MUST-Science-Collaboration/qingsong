import pytest
from tools.qingsong.core import QingsongCore
from tools.qingsong.models import ItemType, Link
from tools.qingsong.validate import (
    validate_links, 
    validate_category_path, 
    validate_retirement
)
from tools.qingsong.load_meta import validate_metadata

@pytest.fixture
def core():
    return QingsongCore.load()

def test_validate_links_constraints(core):
    # Invalid link type
    item = core.create_item(
        item_type=ItemType.REQ,
        system_path="FPS/FID",
        title="Link Test",
        text="T",
        owner="eng001",
        category_path="performance/accuracy",
        links=[{"target_id": "MUST-FPS-FID-REQ-001", "link_type": "invalid_type"}]
    )
    errors = validate_links(item, core.items, core.metadata)
    assert any("Invalid link type 'invalid_type'" in e.message for e in errors)

def test_validate_category_path(core):
    # Valid
    item = core.get_item("MUST-FPS-FID-REQ-001")
    errors = validate_category_path(item, core.metadata)
    assert len(errors) == 0
    
    # Invalid
    # Bypass pydantic validation for test
    object.__setattr__(item, 'category_path', "invalid/category")
    errors = validate_category_path(item, core.metadata)
    assert len(errors) == 1

def test_validate_retirement(core):
    item = core.get_item("MUST-FPS-FID-REQ-001")
    # Bypass pydantic validation for test
    from tools.qingsong.models.common import LifecycleStatus
    object.__setattr__(item, 'status', LifecycleStatus.RETIRED)
    object.__setattr__(item, 'retirement', None)
    
    errors = validate_retirement(item)
    assert len(errors) == 1

def test_validate_metadata_integrity(core):
    errors = validate_metadata(core.meta_dir)
    assert len(errors) == 0

def test_validate_single_item(core):
    from tools.qingsong.validate import validate_single_item
    result = validate_single_item("MUST-FPS-FID-REQ-001")
    assert result.item_count == 1
    
    result_fail = validate_single_item("NON-EXISTENT")
    assert not result_fail.valid
