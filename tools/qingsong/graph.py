"""
Graph visualization module for Qingsong.

Provides network graph visualization of item relationships using networkx.
"""

from pathlib import Path
from typing import Any

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False

from .core import QingsongCore
from .models import ItemType


# Color scheme for item types
TYPE_COLORS = {
    ItemType.REQ: "#4CAF50",   # Green
    ItemType.RSK: "#F44336",   # Red
    ItemType.IFC: "#2196F3",   # Blue
    ItemType.DOC: "#9C27B0",   # Purple
    ItemType.DAT: "#FF9800",   # Orange
    ItemType.NOTE: "#607D8B",  # Gray
}

# Color scheme for link types
LINK_COLORS = {
    "implements": "#4CAF50",
    "verifies": "#8BC34A",
    "mitigates": "#FFEB3B",
    "impacts": "#F44336",
    "defines_interface": "#2196F3",
    "related_to": "#9E9E9E",
    "derives_from": "#673AB7",
    "supersedes": "#795548",
    "references": "#00BCD4",
}


def build_graph(core: QingsongCore, include_external: bool = False) -> "nx.DiGraph":
    """
    Build a NetworkX directed graph from items and links.

    Args:
        core: QingsongCore instance.
        include_external: Whether to include external link targets.

    Returns:
        NetworkX DiGraph.
    """
    if not HAS_NETWORKX:
        raise ImportError("networkx is required for graph functionality")

    G = nx.DiGraph()

    # Add nodes for all items
    for item_id, item in core.items.items():
        G.add_node(
            item_id,
            type=item.type.value,
            title=item.title,
            system_path=item.system_path,
            status=item.status.value,
            owner=item.owner,
            color=TYPE_COLORS.get(item.type, "#000000"),
        )

    # Add edges for all links
    for item in core.items.values():
        for link in item.links:
            target_id = link.target_id

            # Skip external links unless requested
            if target_id.startswith("EXT:"):
                if include_external:
                    if target_id not in G:
                        G.add_node(
                            target_id,
                            type="EXTERNAL",
                            title=target_id[4:],
                            system_path="EXTERNAL",
                            status="external",
                            owner="",
                            color="#BDBDBD",
                        )
                else:
                    continue

            # Skip if target doesn't exist
            if target_id not in G:
                continue

            G.add_edge(
                item.id_full,
                target_id,
                link_type=link.link_type,
                description=link.description or "",
                color=LINK_COLORS.get(link.link_type, "#000000"),
            )

    return G


def get_neighborhood(
    core: QingsongCore,
    item_id: str,
    depth: int = 1,
) -> "nx.DiGraph":
    """
    Get the neighborhood graph around a specific item.

    Args:
        core: QingsongCore instance.
        item_id: Center item ID.
        depth: Number of hops to include.

    Returns:
        Subgraph of the neighborhood.
    """
    if not HAS_NETWORKX:
        raise ImportError("networkx is required for graph functionality")

    G = build_graph(core)

    if item_id not in G:
        return nx.DiGraph()

    # Get nodes within depth
    nodes = {item_id}
    current = {item_id}

    for _ in range(depth):
        next_level = set()
        for node in current:
            # Successors (outgoing links)
            next_level.update(G.successors(node))
            # Predecessors (incoming links)
            next_level.update(G.predecessors(node))
        nodes.update(next_level)
        current = next_level

    return G.subgraph(nodes).copy()


def graph_to_dict(G: "nx.DiGraph") -> dict[str, Any]:
    """
    Convert a NetworkX graph to a dictionary for JSON serialization.

    Args:
        G: NetworkX graph.

    Returns:
        Dictionary representation.
    """
    if not HAS_NETWORKX:
        raise ImportError("networkx is required for graph functionality")

    nodes = []
    for node_id, attrs in G.nodes(data=True):
        nodes.append({
            "id": node_id,
            **attrs,
        })

    edges = []
    for source, target, attrs in G.edges(data=True):
        edges.append({
            "source": source,
            "target": target,
            **attrs,
        })

    return {
        "nodes": nodes,
        "edges": edges,
        "node_count": G.number_of_nodes(),
        "edge_count": G.number_of_edges(),
    }


def export_graph_html(
    G: "nx.DiGraph",
    output_path: Path,
    title: str = "Qingsong Item Graph",
) -> None:
    """
    Export graph to an interactive HTML file using simple SVG.

    Args:
        G: NetworkX graph.
        output_path: Output HTML file path.
        title: Page title.
    """
    if not HAS_NETWORKX:
        raise ImportError("networkx is required for graph functionality")

    # Get layout
    try:
        pos = nx.spring_layout(G, k=2, iterations=50)
    except Exception:
        pos = nx.random_layout(G)

    # Scale positions to SVG coordinates
    width, height = 1200, 800
    margin = 50

    min_x = min(p[0] for p in pos.values()) if pos else 0
    max_x = max(p[0] for p in pos.values()) if pos else 1
    min_y = min(p[1] for p in pos.values()) if pos else 0
    max_y = max(p[1] for p in pos.values()) if pos else 1

    def scale_x(x):
        if max_x == min_x:
            return width / 2
        return margin + (x - min_x) / (max_x - min_x) * (width - 2 * margin)

    def scale_y(y):
        if max_y == min_y:
            return height / 2
        return margin + (y - min_y) / (max_y - min_y) * (height - 2 * margin)

    # Build SVG
    svg_lines = [
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">',
        '  <defs>',
        '    <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto">',
        '      <polygon points="0 0, 10 3.5, 0 7" fill="#666" />',
        '    </marker>',
        '  </defs>',
    ]

    # Draw edges
    for source, target, attrs in G.edges(data=True):
        if source in pos and target in pos:
            x1, y1 = scale_x(pos[source][0]), scale_y(pos[source][1])
            x2, y2 = scale_x(pos[target][0]), scale_y(pos[target][1])
            color = attrs.get("color", "#999")
            svg_lines.append(
                f'  <line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                f'stroke="{color}" stroke-width="1.5" marker-end="url(#arrowhead)" />'
            )

    # Draw nodes
    for node_id, attrs in G.nodes(data=True):
        if node_id in pos:
            x, y = scale_x(pos[node_id][0]), scale_y(pos[node_id][1])
            color = attrs.get("color", "#666")
            label = node_id.split("-")[-1] if "-" in node_id else node_id[:8]
            title_text = attrs.get("title", node_id)

            svg_lines.append(f'  <g class="node" data-id="{node_id}">')
            svg_lines.append(
                f'    <circle cx="{x:.1f}" cy="{y:.1f}" r="20" fill="{color}" '
                f'stroke="#fff" stroke-width="2">'
            )
            svg_lines.append(f'      <title>{node_id}: {title_text}</title>')
            svg_lines.append('    </circle>')
            svg_lines.append(
                f'    <text x="{x:.1f}" y="{y + 4:.1f}" text-anchor="middle" '
                f'fill="white" font-size="10" font-family="Arial">{label}</text>'
            )
            svg_lines.append('  </g>')

    svg_lines.append('</svg>')

    # Build HTML
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background: #f5f5f5;
        }}
        h1 {{
            color: #333;
        }}
        .graph-container {{
            background: white;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 20px;
            overflow: auto;
        }}
        .legend {{
            margin-top: 20px;
            padding: 15px;
            background: white;
            border: 1px solid #ddd;
            border-radius: 8px;
        }}
        .legend-item {{
            display: inline-block;
            margin-right: 20px;
        }}
        .legend-color {{
            display: inline-block;
            width: 16px;
            height: 16px;
            border-radius: 50%;
            margin-right: 5px;
            vertical-align: middle;
        }}
        .stats {{
            margin-top: 20px;
            color: #666;
        }}
        .node:hover circle {{
            stroke: #333;
            stroke-width: 3;
            cursor: pointer;
        }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <div class="stats">
        Nodes: {G.number_of_nodes()} | Edges: {G.number_of_edges()}
    </div>
    <div class="graph-container">
        {''.join(svg_lines)}
    </div>
    <div class="legend">
        <strong>Legend:</strong>
        <div class="legend-item"><span class="legend-color" style="background: #4CAF50"></span>REQ</div>
        <div class="legend-item"><span class="legend-color" style="background: #F44336"></span>RSK</div>
        <div class="legend-item"><span class="legend-color" style="background: #2196F3"></span>IFC</div>
        <div class="legend-item"><span class="legend-color" style="background: #9C27B0"></span>DOC</div>
        <div class="legend-item"><span class="legend-color" style="background: #FF9800"></span>DAT</div>
        <div class="legend-item"><span class="legend-color" style="background: #607D8B"></span>NOTE</div>
    </div>
</body>
</html>
"""

    output_path.write_text(html)


def get_graph_stats(G: "nx.DiGraph") -> dict[str, Any]:
    """
    Get statistics about a graph.

    Args:
        G: NetworkX graph.

    Returns:
        Dictionary of statistics.
    """
    if not HAS_NETWORKX:
        raise ImportError("networkx is required for graph functionality")

    stats = {
        "node_count": G.number_of_nodes(),
        "edge_count": G.number_of_edges(),
        "density": nx.density(G),
    }

    # Node type distribution
    type_counts: dict[str, int] = {}
    for _, attrs in G.nodes(data=True):
        t = attrs.get("type", "UNKNOWN")
        type_counts[t] = type_counts.get(t, 0) + 1
    stats["nodes_by_type"] = type_counts

    # Link type distribution
    link_counts: dict[str, int] = {}
    for _, _, attrs in G.edges(data=True):
        lt = attrs.get("link_type", "unknown")
        link_counts[lt] = link_counts.get(lt, 0) + 1
    stats["edges_by_type"] = link_counts

    # Connectivity
    if G.number_of_nodes() > 0:
        stats["is_weakly_connected"] = nx.is_weakly_connected(G)
        stats["number_weakly_connected_components"] = nx.number_weakly_connected_components(G)

        # Degree statistics
        in_degrees = [d for _, d in G.in_degree()]
        out_degrees = [d for _, d in G.out_degree()]

        if in_degrees:
            stats["avg_in_degree"] = sum(in_degrees) / len(in_degrees)
            stats["max_in_degree"] = max(in_degrees)

        if out_degrees:
            stats["avg_out_degree"] = sum(out_degrees) / len(out_degrees)
            stats["max_out_degree"] = max(out_degrees)

    return stats

