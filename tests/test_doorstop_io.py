import pytest
from pathlib import Path
from tools.qingsong.doorstop_io import load_item, save_item, create_doorstop_document, load_all_items
from tools.qingsong.models import Requirement, ItemType

@pytest.fixture
def tmp_doorstop_dir(tmp_path):
    # Setup a temp doorstop directory
    d = tmp_path / "doorstop"
    d.mkdir()
    return d

def test_create_and_load_item(tmp_doorstop_dir):
    # Setup document
    doc_dir = create_doorstop_document("REQ", "FPS", "FID", base_dir=tmp_doorstop_dir)
    assert doc_dir.exists()
    assert (doc_dir / ".doorstop.yml").exists()

    # Create item manually to test save/load
    item = Requirement(
        id_full="MUST-FPS-FID-REQ-001",
        title="Test Item",
        text="Test content.",
        system_path="FPS/FID",
        owner="eng001",
        category_path="performance/accuracy"
    )

    save_path = save_item(item, doc_dir)
    assert save_path.exists()
    assert save_path.name == "001.yml"

    # Load it back
    loaded = load_item(save_path)
    assert loaded.id_full == item.id_full
    assert loaded.title == item.title
    assert loaded.text == item.text

def test_load_all_items(tmp_doorstop_dir):
    create_doorstop_document("REQ", "FPS", "FID", base_dir=tmp_doorstop_dir)
    create_doorstop_document("RSK", "SPS", "DET", base_dir=tmp_doorstop_dir)
    
    # Add an item to each
    item1 = Requirement(
        id_full="MUST-FPS-FID-REQ-001",
        title="R1",
        text="T1",
        system_path="FPS/FID",
        owner="eng001",
        category_path="performance/accuracy"
    )
    save_item(item1, tmp_doorstop_dir / "REQ" / "FPS" / "FID")

    # Verify load_all_items finds it
    items = load_all_items(base_dir=tmp_doorstop_dir)
    assert len(items) == 1
    assert "MUST-FPS-FID-REQ-001" in items

def test_load_malformed_yaml(tmp_doorstop_dir):
    doc_dir = create_doorstop_document("REQ", "FPS", "FID", base_dir=tmp_doorstop_dir)
    bad_file = doc_dir / "bad.yml"
    with open(bad_file, "w") as f:
        f.write("invalid: yaml: : content")
    
    # load_all_items should log but continue
    items = load_all_items(base_dir=tmp_doorstop_dir)
    assert len(items) == 0

def test_nested_l3_structure(tmp_doorstop_dir):
    # Setup doc in L3 folder
    doc_dir = create_doorstop_document("REQ", "FPS", "FID", l3="FID-AIT", base_dir=tmp_doorstop_dir)
    assert doc_dir.parts[-1] == "FID-AIT"
    assert (doc_dir / ".doorstop.yml").exists()
    
    item = Requirement(
        id_full="MUST-FPS-FID-AIT-REQ-001",
        title="L3 Item",
        text="L3 Content",
        system_path="FPS/FID",
        l3="FID-AIT",
        owner="eng001",
        category_path="performance/accuracy"
    )
    save_path = save_item(item, doc_dir)
    
    # Load back and verify inference
    loaded = load_item(save_path)
    assert loaded.l3 == "FID-AIT"
    assert loaded.system_path == "FPS/FID"
