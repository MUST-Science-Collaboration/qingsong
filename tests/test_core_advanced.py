import pytest
from tools.qingsong.core import QingsongCore
from tools.qingsong.models import ItemType

@pytest.fixture
def core():
    return QingsongCore.load()

def test_staged_changes_workflow(core):
    # Create
    item = core.create_item(
        item_type=ItemType.REQ,
        system_path="FPS/FID",
        title="Staged Item",
        text="Staged",
        owner="eng001",
        category_path="performance/accuracy"
    )
    assert item.id_full in core.staged_changes
    assert core.get_item(item.id_full).title == "Staged Item"

    # Update
    core.update_item(item.id_full, title="Updated Title")
    assert core.get_item(item.id_full).title == "Updated Title"
    assert core.staged_changes[item.id_full].action == "update"

    # Discard
    core.discard_changes()
    assert item.id_full not in core.items
    assert item.id_full not in core.staged_changes

def test_retire_item(core):
    # Setup existing item
    item = core.create_item(
        item_type=ItemType.REQ,
        system_path="FPS/FID",
        title="To be retired",
        text="Text",
        owner="eng001",
        category_path="performance/accuracy"
    )
    core.flush()
    
    core.retire_item(item.id_full, reason="Obsolete", retired_by="ps001")
    retired = core.get_item(item.id_full)
    assert retired.status.value == "retired"
    assert retired.retirement.retired_reason == "Obsolete"
    
    # Cleanup
    import os
    os.remove(f"doorstop/REQ/FPS/FID/{item.id_full.split('-')[-1]}.yml")

def test_get_linked_items(core):
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
    
    linked = core.get_linked_items(b.id_full)
    assert a in linked["outgoing"]
    
    linked_a = core.get_linked_items(a.id_full)
    assert b in linked_a["incoming"]

def test_items_to_dataframe(core):
    core.create_item(
        item_type=ItemType.REQ,
        system_path="FPS/FID",
        title="DF Test",
        text="Text",
        owner="eng001",
        category_path="performance/accuracy"
    )
    df = core.items_to_dataframe()
    assert not df.empty
    assert "id_full" in df.columns
    assert "DF Test" in df["title"].values

def test_summary(core):
    summary = core.summary()
    assert "total_items" in summary
    assert "items_by_type" in summary

def test_migrate_item(core):
    # Setup
    item = core.create_item(
        item_type=ItemType.REQ,
        system_path="FPS/FID",
        title="To Migrate",
        text="T",
        owner="eng001",
        category_path="performance/accuracy"
    )
    core.flush()
    old_id = item.id_full
    
    # Migrate
    migrated = core.migrate_item(old_id, "SPS/DET")
    new_id = migrated.id_full
    assert new_id.startswith("MUST-SPS-DET-REQ")
    assert old_id not in core.items
    assert new_id in core.items
    
    # Verify links updated (setup a link first)
    source = core.create_item(
        item_type=ItemType.REQ,
        system_path="FPS/FID",
        title="Source",
        text="T",
        owner="eng001",
        category_path="performance/accuracy",
        links=[{"target_id": new_id, "link_type": "related_to"}]
    )
    # Re-migrate target
    target_migrated_again = core.migrate_item(new_id, "FPS/FID", new_l3="FID-AIT")
    final_id = target_migrated_again.id_full
    assert core.get_item(source.id_full).links[0].target_id == final_id

def test_traceability_matrix(core):
    matrix = core.get_traceability_matrix(direction="upward")
    assert isinstance(matrix, list)
    if matrix:
        assert "id" in matrix[0]
        assert "links" in matrix[0]

def test_verification_summary(core):
    summary = core.get_verification_summary()
    assert "total" in summary
    assert "verified" in summary
    assert "percent" in summary
