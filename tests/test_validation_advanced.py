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

def test_validate_owner_details(core):
    from tools.qingsong.validate import validate_owner
    item = core.get_item("MUST-FPS-FID-REQ-001")
    # Valid
    assert len(validate_owner(item, core.metadata)) == 0
    # Invalid collab
    object.__setattr__(item, 'collaborators', ["nonexistent"])
    errors = validate_owner(item, core.metadata)
    assert any("Collaborator 'nonexistent' not found" in e.message for e in errors)

def test_validate_system_path_details(core):
    from tools.qingsong.validate import validate_system_path
    item = core.get_item("MUST-FPS-FID-REQ-001")
    # Invalid L3
    object.__setattr__(item, 'l3', "INVALID-L3")
    errors = validate_system_path(item, core.metadata)
    assert any("L3 code 'INVALID-L3' not found" in e.message for e in errors)

def test_validate_link_constraints_advanced(core):
    from tools.qingsong.validate import validate_links
    # 1. Source type mismatch
    # derives_from requires REQ -> REQ. Let's try RSK -> REQ
    risk = core.create_item(ItemType.RSK, "FPS/FID", "R", "T", "eng001")
    object.__setattr__(risk, 'links', [Link(target_id="MUST-FPS-FID-REQ-001", link_type="derives_from")])
    errors = validate_links(risk, core.items, core.metadata)
    assert any("does not allow source type 'RSK'" in e.message for e in errors)
    
    # 2. same_type_only mismatch
    # supersedes requires same type. Let's try REQ -> RSK
    req = core.get_item("MUST-FPS-FID-REQ-001")
    object.__setattr__(req, 'links', [Link(target_id=risk.id_full, link_type="supersedes")])
    errors = validate_links(req, core.items, core.metadata)
    assert any("requires same type" in e.message for e in errors)

def test_validate_id_format_advanced(core):
    from tools.qingsong.validate import validate_id_format
    req = core.get_item("MUST-FPS-FID-REQ-001")
    
    # Wrong prefix
    object.__setattr__(req, 'id_full', "WRONG-FPS-FID-REQ-001")
    assert any("must start with 'MUST'" in e.message for e in validate_id_format(req))
    
    # Wrong type code
    object.__setattr__(req, 'id_full', "MUST-FPS-FID-RSK-001")
    assert any("does not match item type" in e.message for e in validate_id_format(req))
    
    # Wrong digits
    object.__setattr__(req, 'id_full', "MUST-FPS-FID-REQ-1")
    assert any("should be 3 digits" in e.message for e in validate_id_format(req))
    
    # Inconsistent system path (warning)
    object.__setattr__(req, 'id_full', "MUST-SPS-FID-REQ-001")
    errors = validate_id_format(req)
    assert any("ID L1 (SPS) does not match item L1 (FPS)" in e.message for e in errors)
    assert any(e.severity == "warning" for e in errors)
