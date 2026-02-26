import pytest
from pathlib import Path
from tools.qingsong.doorstop_io import (
    create_doorstop_document, 
    get_next_item_number, 
    create_new_item, 
    list_documents,
    _infer_item_type
)
from tools.qingsong.models import ItemType

@pytest.fixture
def tmp_doorstop_dir(tmp_path):
    d = tmp_path / "doorstop"
    d.mkdir()
    return d

def test_get_next_item_number(tmp_doorstop_dir):
    doc_dir = create_doorstop_document("REQ", "FPS", "FID", base_dir=tmp_doorstop_dir)
    assert get_next_item_number(doc_dir) == 1
    
    # Create an item
    create_new_item(ItemType.REQ, "FPS/FID", "Title", "Text", "eng001", category_path="performance/accuracy", base_dir=tmp_doorstop_dir)
    assert get_next_item_number(doc_dir) == 2

def test_list_documents(tmp_doorstop_dir):
    create_doorstop_document("REQ", "FPS", "FID", base_dir=tmp_doorstop_dir)
    create_doorstop_document("RSK", "SPS", "DET", base_dir=tmp_doorstop_dir)
    
    docs = list_documents(base_dir=tmp_doorstop_dir)
    assert len(docs) == 2
    prefixes = [d["prefix"] for d in docs]
    assert "MUST-FPS-FID-REQ" in prefixes
    assert "MUST-SPS-DET-RSK" in prefixes

def test_infer_item_type():
    assert _infer_item_type({"type": "RSK"}, {}) == ItemType.RSK
    assert _infer_item_type({}, {"prefix": "MUST-FPS-FID-REQ"}) == ItemType.REQ
    assert _infer_item_type({}, {"prefix": "MUST-FPS-FID-IFC"}) == ItemType.IFC
    assert _infer_item_type({}, {"prefix": "MUST-FPS-FID-DOC"}) == ItemType.DOC
    assert _infer_item_type({}, {"prefix": "MUST-FPS-FID-DAT"}) == ItemType.DAT
    assert _infer_item_type({}, {"prefix": "MUST-FPS-FID-NOTE"}) == ItemType.NOTE
    assert _infer_item_type({}, {}) == ItemType.REQ # Default

def test_create_new_item_variants(tmp_doorstop_dir):
    # Test different types
    create_new_item(ItemType.RSK, "FPS/FID", "Risk", "Text", "eng001", base_dir=tmp_doorstop_dir)
    create_new_item(ItemType.IFC, "FPS/FID", "IFC", "Text", "eng001", base_dir=tmp_doorstop_dir)
    create_new_item(ItemType.DOC, "FPS/FID", "DOC", "Text", "eng001", base_dir=tmp_doorstop_dir)
    create_new_item(ItemType.DAT, "FPS/FID", "DAT", "Text", "eng001", base_dir=tmp_doorstop_dir)
    create_new_item(ItemType.NOTE, "FPS/FID", "NOTE", "Text", "eng001", base_dir=tmp_doorstop_dir)
    
    assert (tmp_doorstop_dir / "RSK" / "FPS" / "FID" / "001.yml").exists()
    assert (tmp_doorstop_dir / "IFC" / "FPS" / "FID" / "001.yml").exists()
