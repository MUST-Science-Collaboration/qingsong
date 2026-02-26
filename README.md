# Qingsong 🔭

**Project Management Engine for the MUST Telescope**

Qingsong (青松) is a lightweight, file-based requirements/risk/interface management system designed for the MUltiplexed Survey Telescope (MUST) project. Named after the Chinese astronomer **Yu Qingsong (余青松)**, a Tsinghua alumnus.

## Philosophy

- **"Requirements/risk/interface as code"**: Items are stored as small structured YAML files in a Git repository
- **"Single source of truth + derived artifacts"**: Doorstop YAML files are the source; SQLite cache and exports are derived
- **One canonical schema**: Pydantic models define and enforce the schema (no separate JSON Schema)
- **Strict validation is mandatory**: No silent drift allowed

## Features

- 📋 **Requirements Management**: Track and trace requirements with verification status
- ⚠️ **Risk Management**: Identify, assess, and mitigate project risks
- 🔗 **Interface Control**: Define and manage system interfaces
- 🏠 **Multi-Vault Support**: Point to any project directory using the `--root` flag
- ✨ **Project Scaffolding**: Bootstrap new projects instantly with `qingsong init`
- 🔍 **Full-text Search**: SQLite FTS5 for fast searching
- 🕸️ **Graph Visualization**: Visualize item relationships
- 🖥️ **Web UI**: Streamlit-based browser interface

## Documentation

- **[Beginner's Guide](begin_with_qingsong.md)** - Comprehensive guide for system engineers using Qingsong in real project workflows
- **[Examples](examples/README.md)** - Code examples and usage patterns

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/must-telescope/qingsong.git
cd qingsong

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
pip install -e .

# Optional: Install development dependencies
pip install -e ".[dev]"
```

### Verify Installation

```bash
# Initialize a demo project
qingsong init ./demo --name "Demo Project"

# Validate metadata in the demo project
qingsong --root ./demo meta validate

# Validate all items
qingsong --root ./demo validate

# Build SQLite cache
qingsong --root ./demo cache build
```

## Project Structure

```
qingsong/
├── doorstop/           # Doorstop item storage
│   ├── REQ/            # Requirements
│   ├── RSK/            # Risks
│   ├── IFC/            # Interfaces
│   ├── DOC/            # Documents
│   ├── DAT/            # Data records
│   └── NOTE/           # Technical notes
├── meta/               # Metadata definitions
│   ├── hierarchy.yaml  # Project hierarchy (L0-L3)
│   ├── people.yaml     # Team directory
│   ├── glossary.yaml   # Terms and acronyms
│   └── vocab/          # Controlled vocabularies
├── tools/qingsong/     # Python package
│   ├── cli.py          # CLI commands
│   ├── core.py         # Core API
│   ├── models/         # Pydantic models
│   └── ui/             # Streamlit UI
├── index/              # SQLite cache (not committed)
├── assets/             # Binary assets
└── examples/           # Usage examples
```

## Item ID Format

All items follow the format: `MUST-<L1>-<L2>-<TYPE>-NNN`

- **L1**: Major system (e.g., FPS, SPS, DMS)
- **L2**: Subsystem (e.g., FID, DET, PIPE)
- **TYPE**: Item type code (REQ, RSK, IFC, DOC, DAT, NOTE)
- **NNN**: Sequential number (001-999)

Example: `MUST-FPS-FID-REQ-001`

## CLI Commands

### Validation

```bash
# Validate metadata files
qingsong meta validate

# Validate all items
qingsong validate
```

### Listing and Viewing

```bash
# List all items
qingsong list

# Filter by type, system, status, or owner
qingsong list --type req --system FPS/FID --status active

# Show item details
qingsong show MUST-FPS-FID-REQ-001

# Show repository summary
qingsong summary
```

### Creating Items

```bash
# Create a new requirement
qingsong new req --title "Fiber Accuracy" --system FPS/FID --owner eng001

# Create a new risk
qingsong new rsk --title "Motor Failure" --system FPS/FID --owner eng001

# Create with more options
qingsong new req --title "Title" --system FPS/FID --owner eng001 \
  --text "Description" --category functional/observation
```

### Cache Operations

```bash
# Build SQLite cache
qingsong cache build

# Show cache statistics
qingsong cache stats
```

### Querying

```bash
# Execute SQL query
qingsong query "SELECT * FROM items WHERE type = 'RSK'"

# Output as JSON
qingsong query "SELECT * FROM items" --format json

# Output as CSV
qingsong query "SELECT * FROM items" --format csv
```

### Exports

```bash
# Export requirements document
qingsong export requirements --system FPS/FID -o requirements.md

# Export risk register
qingsong export risks -o risk_register.md

# Export interface list
qingsong export interfaces -o interfaces.md

# Export summary
qingsong export summary -o summary.md
```

### Graph Visualization

```bash
# Generate full graph
qingsong graph -o graph.html

# Generate neighborhood around an item
qingsong graph MUST-FPS-FID-RSK-001 --depth 2 -o neighborhood.html
```

### Web UI

```bash
# Launch Streamlit UI
qingsong ui
```

## Python API

### Basic Usage

```python
from qingsong.core import QingsongCore

# Load the core
core = QingsongCore.load()

# Access items
item = core.get_item("MUST-FPS-FID-REQ-001")
print(item.title)

# Get items by filters
reqs = core.get_items_by_type("REQ")
fps_items = core.get_items_by_system("FPS/FID")
active = core.get_items_by_status("active")
```

### Validation

```python
# Validate all items
result = core.validate()
if not result.valid:
    for error in result.errors:
        print(error)

# Validate metadata
errors = core.validate_metadata()
```

### Creating Items

```python
from qingsong.models import ItemType

item = core.create_item(
    item_type=ItemType.REQ,
    system_path="FPS/FID",
    title="New Requirement",
    text="Description here",
    owner="eng001",
)
print(f"Created: {item.id_full}")
```

### DataFrames

```python
# Items as DataFrame
df = core.items_to_dataframe()

# Links as DataFrame
links_df = core.links_to_dataframe()
```

### Querying Cache

```python
# Build cache first
core.build_cache()

# Execute SQL
results = core.query("SELECT * FROM items WHERE status = 'active'")

# Full-text search
results = core.search("fiber positioning")
```

## Metadata

### Hierarchy (`meta/hierarchy.yaml`)

Defines the project structure:
- **L0**: Project (MUST)
- **L1**: Major systems (SWG, FPS, SPS, DMS)
- **L2**: Subsystems
- **L3**: Tasks (stored as item attribute)

### People (`meta/people.yaml`)

Team directory with person IDs used for `owner` and `collaborators` fields.

### Vocabularies (`meta/vocab/`)

Controlled vocabularies for:
- `status.yaml`: Item lifecycle status
- `req_category.yaml`: Requirement categories
- `risk_category.yaml`: Risk categories
- `ifc_type.yaml`: Interface types
- `link_types.yaml`: Relationship types and constraints

## Item Lifecycle

Items follow a lifecycle: `draft` → `active` → `retired|superseded`

- **draft**: Under development, not yet approved
- **active**: Approved and in effect
- **retired**: No longer in effect (preserved for history)
- **superseded**: Replaced by a newer item

**No hard delete**: Items are never deleted; use `retired` or `superseded` status.

## Link Types

| Link Type | Description | Source Types | Target Types |
|-----------|-------------|--------------|--------------|
| `implements` | Satisfies a requirement | DOC, DAT, NOTE | REQ |
| `verifies` | Provides verification evidence | DOC, DAT, NOTE | REQ |
| `mitigates` | Describes risk mitigation | NOTE, DOC, REQ | RSK |
| `impacts` | Risk impacts if realized | RSK | REQ, IFC, DOC |
| `defines_interface` | Document defines interface | DOC | IFC |
| `related_to` | General relationship | Any | Any |
| `derives_from` | Derived requirement | REQ | REQ |
| `supersedes` | Replaces an item | Any | Same type |
| `references` | References for info | Any | DOC, DAT, NOTE |

## Development

### Setup

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Testing

```bash
# Run tests
pytest

# With coverage
pytest --cov=qingsong
```

### Linting

```bash
# Run ruff
ruff check tools/

# Type checking
mypy tools/qingsong
```

## CI/CD

GitHub Actions workflow runs on push/PR:
- Linting and type checking
- Metadata validation
- Item validation
- No-hard-delete check
- Cache build test

## Design Decisions

1. **Dynamic Enums**: Generated at runtime from metadata (not pre-generated) to ensure sync
2. **Pydantic is canonical**: No separate JSON Schema; Pydantic models are the schema
3. **Doorstop for storage**: Leverages Doorstop's file-per-item convention
4. **L3 as attribute**: L3 tasks are item attributes, not separate document levels
5. **SQLite cache**: Generated artifact for efficient querying; not committed to git

## License

MIT License - see [LICENSE](LICENSE)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Run validation: `qingsong validate`
5. Submit a pull request

## Acknowledgments

Named after **Yu Qingsong (余青松)**, a pioneering Chinese astronomer and Tsinghua alumnus who made significant contributions to stellar spectroscopy.
