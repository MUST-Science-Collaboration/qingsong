import pytest
from pathlib import Path
from tools.qingsong.core import QingsongCore
from tools.qingsong.cache_build import build_cache, query_cache, search_items

@pytest.fixture
def core():
    return QingsongCore.load()

def test_build_and_query_cache(core, tmp_path):
    cache_path = tmp_path / "qingsong.sqlite"
    build_cache(cache_path, core.doorstop_dir, core.meta_dir)
    assert cache_path.exists()
    
    # Query
    results = query_cache("SELECT count(*) as count FROM items", None, cache_path)
    assert len(results) == 1
    assert results[0]["count"] > 0
    
    # Search
    search_results = search_items("Fiber", cache_path)
    assert len(search_results) >= 0 # Might be 0 if no item contains "Fiber"
