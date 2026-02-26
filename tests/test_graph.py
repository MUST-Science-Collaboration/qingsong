import pytest
from tools.qingsong.core import QingsongCore
from tools.qingsong.models import ItemType
from tools.qingsong.graph import build_graph, find_item_cycles, get_neighborhood, graph_to_dict

@pytest.fixture
def core():
    return QingsongCore.load()

def test_build_graph(core):
    a = core.create_item(
        item_type=ItemType.REQ,
        system_path="FPS/FID",
        title="A",
        text="A",
        owner="eng001",
        category_path="performance/accuracy"
    )
    G = build_graph(core.items)
    assert a.id_full in G.nodes()

def test_find_cycles(core):
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
    
    cycles = find_item_cycles(core.items)
    assert len(cycles) >= 1

def test_get_neighborhood(core):
    a = core.create_item(
        item_type=ItemType.REQ,
        system_path="FPS/FID",
        title="A",
        text="A",
        owner="eng001",
        category_path="performance/accuracy"
    )
    G_sub = get_neighborhood(core.items, a.id_full, depth=1)
    assert a.id_full in G_sub.nodes()

def test_graph_to_dict(core):
    core.create_item(
        item_type=ItemType.REQ,
        system_path="FPS/FID",
        title="A",
        text="A",
        owner="eng001",
        category_path="performance/accuracy"
    )
    G = build_graph(core.items)
    d = graph_to_dict(G)
    assert "nodes" in d
    assert "edges" in d

def test_export_graph_html(core, tmp_path):
    from tools.qingsong.graph import build_graph, export_graph_html
    G = build_graph(core.items)
    output = tmp_path / "graph.html"
    export_graph_html(G, output)
    assert output.exists()
    assert "<svg" in output.read_text()

def test_get_graph_stats(core):
    from tools.qingsong.graph import build_graph, get_graph_stats
    G = build_graph(core.items)
    stats = get_graph_stats(G)
    assert "node_count" in stats
    assert "edge_count" in stats
