# Examples

This directory contains example scripts and usage patterns for Qingsong.

## Python API Examples

### Loading and Querying Items

```python
from qingsong.core import QingsongCore

# Load the core
core = QingsongCore.load()

# Get all requirements
reqs = core.get_items_by_type("REQ")
print(f"Found {len(reqs)} requirements")

# Filter by system
fps_items = core.get_items_by_system("FPS/FID")
print(f"FPS/FID has {len(fps_items)} items")

# Get linked items
linked = core.get_linked_items("MUST-FPS-FID-RSK-001")
print(f"Outgoing links: {len(linked['outgoing'])}")
print(f"Incoming links: {len(linked['incoming'])}")
```

### Creating Items

```python
from qingsong.core import QingsongCore
from qingsong.models import ItemType

core = QingsongCore.load()

# Create a new requirement
item = core.create_item(
    item_type=ItemType.REQ,
    system_path="FPS/FID",
    title="New Requirement",
    text="Description of the requirement",
    owner="eng001",
    category_path="functional/observation",
)

print(f"Created: {item.id_full}")
```

### Using DataFrames

```python
from qingsong.core import QingsongCore
import pandas as pd

core = QingsongCore.load()

# Get items as DataFrame
df = core.items_to_dataframe()
print(df.head())

# Filter and analyze
active_items = df[df['status'] == 'active']
by_type = active_items.groupby('type').size()
print(by_type)

# Get links as DataFrame
links_df = core.links_to_dataframe()
print(links_df.groupby('link_type').size())
```

### Validation

```python
from qingsong.core import QingsongCore

core = QingsongCore.load()

# Validate all items
result = core.validate()
if result.valid:
    print("All items valid!")
else:
    for error in result.errors:
        print(f"Error: {error}")

# Validate metadata
meta_errors = core.validate_metadata()
for error in meta_errors:
    print(f"Metadata error: {error}")
```

### Exporting

```python
from qingsong.core import QingsongCore
from qingsong.export import (
    export_requirements_markdown,
    export_risk_register_markdown,
)
from pathlib import Path

core = QingsongCore.load()

# Export requirements for a system
content = export_requirements_markdown(
    core,
    system_path="FPS/FID",
    output_path=Path("fps_fid_requirements.md"),
)

# Export risk register
content = export_risk_register_markdown(
    core,
    output_path=Path("risk_register.md"),
)
```

### Graph Analysis

```python
from qingsong.core import QingsongCore
from qingsong.graph import (
    build_graph,
    get_neighborhood,
    get_graph_stats,
    export_graph_html,
)
from pathlib import Path

core = QingsongCore.load()

# Build full graph
G = build_graph(core)
stats = get_graph_stats(G)
print(f"Nodes: {stats['node_count']}, Edges: {stats['edge_count']}")

# Get neighborhood around an item
neighborhood = get_neighborhood(core, "MUST-FPS-FID-RSK-001", depth=2)
export_graph_html(neighborhood, Path("risk_neighborhood.html"))
```

## CLI Examples

```bash
# Validate everything
qingsong meta validate
qingsong validate

# List items
qingsong list
qingsong list --type req --system FPS/FID
qingsong list --status active --owner eng001

# Show item details
qingsong show MUST-FPS-FID-REQ-001

# Create new item
qingsong new req --title "New Requirement" --system FPS/FID --owner eng001

# Build and query cache
qingsong cache build
qingsong query "SELECT type, COUNT(*) FROM items GROUP BY type"

# Export
qingsong export requirements --system FPS/FID -o fps_reqs.md
qingsong export risks -o risks.md

# Generate graph
qingsong graph MUST-FPS-FID-RSK-001 -o risk_graph.html

# Launch UI
qingsong ui
```

