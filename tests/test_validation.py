import pytest
from tools.qingsong.core import QingsongCore
from tools.qingsong.models import ItemType
from tools.qingsong.validate import validate_all

@pytest.fixture
def core():
    return QingsongCore.load()

def test_invalid_id_format(core):
    # This should be caught by Pydantic first if we use model_validate
    with pytest.raises(Exception):
        core.create_item(
            item_type=ItemType.REQ,
            system_path="FPS/FID",
            id_full="INVALID-ID",
            title="Invalid",
            text="Invalid",
            owner="eng001"
        )

def test_circular_dependency(core):
    a = core.create_item(
        item_type=ItemType.REQ,
        system_path="FPS/FID",
        title="A",
        text="A",
        owner="eng001",
        category_path="performance/accuracy"
    )
    b = core.create_item(
        item_type=ItemType.REQ,
        system_path="FPS/FID",
        title="B",
        text="B",
        owner="eng001",
        category_path="performance/accuracy",
        links=[{"target_id": a.id_full, "link_type": "related_to"}]
    )
    core.update_item(a.id_full, links=[{"target_id": b.id_full, "link_type": "related_to"}])
    
    # Global validation should find it
    # We need to use core.items because validate_all loads from disk
    from tools.qingsong.validate import validate_circular_dependencies
    errors = validate_circular_dependencies(core.items)
    assert any("Circular dependency" in e.message for e in errors)

def test_invalid_owner(core):
    item = core.create_item(
        item_type=ItemType.REQ,
        system_path="FPS/FID",
        title="Invalid Owner",
        text="Text",
        owner="nonexistent",
        category_path="performance/accuracy"
    )
    result = core.validate_item(item.id_full)
    assert not result.valid
    assert any("Owner 'nonexistent' not found" in e.message for e in result.errors)

def test_invalid_system_path(core):
    item = core.create_item(
        item_type=ItemType.REQ,
        system_path="UNK/UNK",
        title="Invalid System",
        text="Text",
        owner="eng001",
        category_path="performance/accuracy"
    )
    result = core.validate_item(item.id_full)
    assert not result.valid
    assert any("System path 'UNK/UNK' not found" in e.message for e in result.errors)
