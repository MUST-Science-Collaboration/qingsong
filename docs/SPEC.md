# Qingsong Technical Specification

## 1. Overview
Qingsong (青松) is a requirements management system for the MUST telescope project. It leverages Doorstop for item storage and Pydantic for schema validation.

## 2. Architecture
### 2.1 Storage Layer (Doorstop)
- Each item is a YAML file.
- Documents are directories containing `.doorstop.yml`.
- Structure: `doorstop/<TYPE>/<L1>/<L2>/[L3]/`.

### 2.2 Intelligence Layer (Qingsong Core)
- **Metadata-Driven**: Project hierarchy, people, and vocabularies are defined in `meta/`.
- **Strict Validation**: Pydantic models enforce the schema at runtime.
- **SQLite Cache**: A derived SQLite database (including FTS5) for high-performance querying and reporting.

### 2.3 Interface Layer
- **CLI**: Primary interface for engineers and automated checks. Supports a global `--root` flag for multi-vault management.
- **Python API**: For advanced scripting and data analysis.
- **Web UI**: Streamlit-based viewer/editor (Stage 2).

### 2.4 Vault Portability
- Qingsong is a portable engine. Any directory with a `meta/` and `doorstop/` structure is a valid **Vault**.
- The `qingsong init` command scaffolds a new vault with default metadata templates.
- The `QINGSONG_ROOT` environment variable (set via `--root`) ensures all validation layers use the correct project context.

## 3. Data Model
### 3.1 Item Types
- `REQ`: Requirement (Performance, Functional, etc.)
- `RSK`: Risk (Technical, Schedule, Cost)
- `IFC`: Interface Control (Mechanical, Electrical, Data)
- `DOC`: Document reference
- `DAT`: Data/Test record
- `NOTE`: Technical note/decision

### 3.2 ID Convention
`MUST-<L1>-<L2>-<TYPE>-NNN`
- `L1`: Major system (e.g., FPS, SPS)
- `L2`: Subsystem (e.g., FID, DET)
- `TYPE`: 3-letter type code
- `NNN`: 3-digit sequential number

## 4. Hierarchy Rules
- **L0**: Project (MUST)
- **L1**: Major System
- **L2**: Sub-system
- **L3**: Sub-assembly or Task. 
- *Rule*: If an L2 system is complex, it can be decomposed into L3 folders. Items in L3 folders follow the ID pattern of their L2 parent or a specialized L3 code if defined in `hierarchy.yaml`.

## 5. Staging & Persistence
- All edits must be staged in-memory.
- Persistence to YAML is an explicit `flush()` operation.
- Validation must pass before a `flush()` is allowed in "Strict Mode".

## 6. Migration & Refactoring
- IDs are logically linked to their system path.
- Renaming a system or moving an item triggers an ID update.
- The system must provide a `migrate` tool to update all incoming links when an ID changes.

## 7. Collaboration & Discussion
- All items support a `discussions` field.
- Comments record author, timestamp, and design rationale.
- Discussions are stored directly in the item YAML to preserve history alongside technical requirements.

## 8. Analytical Intelligence
- **Impact Analysis**: Recursive traversal of the link graph to identify transitive dependencies affected by a change.
- **Orphan Detection**: Automated identification of requirements without parents (root orphans) or implementation evidence (leaf orphans).
- **Coverage Metrics**: Real-time calculation of traceability and verification completion percentages.
