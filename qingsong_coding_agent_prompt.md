# Qingsong: Project Management Engine for MUST

**Role & Context**: You are a Senior Systems Architect and Expert Python Engineer with systems-engineering/project-management domain experience. You are tasked with building the foundation of "Qingsong" (named after the astronomer Yu Qingsong), a tailored, lightweight project management system for the MUST Telescope project. `Qingsong` should implement a lightweight, file-based requirements/risk/interface management system for a large scientific instrumentation project. The system must use **Doorstop** as the repository format for item storage and trace links, and add a custom layer consisting of a **Headless Core Python API** + **validators (Pydantic-based)** + **SQLite index/cache** + (later) **local UI**.

---

## 1) Background and context

### Project
- Project name: **MUltiplexed Survey Telescope (MUST)**.
- Nature: a **6.5-meter telescope** designed for next-stage cosmological spectroscopic surveys.
- Project structure: hierarchical, at least four levels:
  - **L0**: MUST
  - **L1**: major systems (examples: Science Working Groups / SWG, Focal Plane System / FPS, Spectrograph System / SPS, Data Management System / DMS)
  - **L2**: sub-systems (engineering) or working groups (science)
  - **L3**: tasks (science) or sub-assemblies (engineering)

### User role
- User is the **Project Scientist** focused on instrumentation and daily technical management.
- User leads three major L1 systems: **SWG**, **FPS**, **SPS**.
- The user needs a lightweight, locally runnable system to track **requirements, interfaces, risks, and related artifacts** with high traceability and low overhead.

### Problem
Current documents are scattered across Word/PDF/Excel with high overhead and unreliable version/update tracking. The new system must treat critical project information as structured code-like records and provide traceability across interconnected subsystems.

---

## 2) Overall architecture and design philosophy

### Philosophy
- “**Requirements/risk/interface as code**”: items are stored as small structured files in a Git repository.
- “**Single source of truth + derived artifacts**”:
  - Source of truth: Doorstop YAML item files + project metadata files
  - Derived artifacts: SQLite index/cache, exports, and visualization outputs
- **One canonical schema:** Pydantic models (not a separate JSON Schema layer).
- Strict validation is mandatory. No silent drift.

### Core components
1. **Doorstop repository** for item storage and basic trace links.
2. **Metadata layer (`meta/`)** defining:
   - hierarchy (L0–L3, acronyms, owners)
   - people/collaborators
   - controlled vocabularies (dropdown lists)
   - link types / relation semantics
3. **Headless Core Python API**
   - load metadata
   - load Doorstop items
   - validate items (Pydantic + cross-file rules)
   - build/refresh SQLite cache
   - stage edits in memory and flush to YAML
4. **Validation**
   - Pydantic model validation per item type
   - referential integrity checks across items and metadata
   - link graph checks (existence, type constraints)
   - lifecycle rules (retire/supersede; no hard delete)
5. **SQLite cache**
   - generated database for unified querying across requirements/risks/interfaces/docs/notes/data
   - include link tables and full-text search where feasible
6. **Local UI (phase 3)**
   - simple GUI for browsing/filtering items like a spreadsheet, viewing details, and showing connected items
   - creation/editing through safe scaffolding commands (avoid manual YAML editing where possible)

### Doorstop document structure decision (Pattern 1)
- Doorstop documents represent **L1/L2**.
- **L3 is an attribute** on items (e.g., `l3: "FID-AIT"`).
- Each item is a single YAML file (Doorstop convention).
- Requirement IDs must follow: `MUST-<L1>-<L2>-<TYPE>-NNN` (e.g., `MUST-FPS-FID-REQ-001`).
  - TYPE codes: `REQ`, `RSK`, `IFC`, `DOC`, `DAT`, `NOTE`.

---

## 3) Key requirements for the repo and tools

### Repository requirements
- Git repository suitable for GitHub.
- Repository name (project root folder): **`qingsong/`**.
  - Note: “qingsong” is named after the modern Pinyin of the Chinese astronomer **Ching Sung Yu (余青松)**, a Tsinghua alumnus.
- Must include:
  - Doorstop repository tree under `doorstop/`
  - metadata under `meta/`
  - Python tooling packaged (pyproject.toml)
  - CI workflow (GitHub Actions) and pre-commit config

### Item categories
Implement at minimum:
- Requirement
- Risk
- Interface
- Document record/reference
- Technical data record/reference
- Technical/science note

### Mandatory capabilities
- Controlled vocabularies (“dropdown lists”) sourced from `meta/`:
  - single-select fields (e.g., `status`)
  - multi-select fields (e.g., `collaborators`, `related_systems`)
- Required vs optional keys enforced by Pydantic models
- Defaults applied during item creation (scaffolding)
- Retirement without deletion:
  - items can be `draft|active|retired|superseded`
  - retired/superseded must include metadata: timestamp, actor, reason, and optional `superseded_by`
- Link validation:
  - every linked ID must exist OR be explicitly marked as an external entity
  - enforce link type constraints from `meta/vocab/link_types.yaml`
- Build SQLite cache:
  - tables for items, links, metadata snapshots
  - full-text search (FTS5 if available)
- Provide CLI commands (Typer recommended) for:
  - `qingsong meta validate`
  - `qingsong validate`
  - `qingsong new <type>`
  - `qingsong cache build`
  - `qingsong query "<SQL>"`
  - `qingsong ui` (launch local UI)
- Provide a minimal Streamlit UI (phase 3) for browsing and item detail view.

### Constraints
- Locally runnable on macOS/Linux with Python 3.11+.
- Avoid heavy enterprise platforms; keep dependencies minimal.
- Do not embed binary media in YAML/JSON; store binaries in `assets/` and reference them.

---

## 4) Feasible and specific development plan (with priority)

Implement in phases. Priority is correctness and governance before UI.

### Phase 0 (bootstrap)
- Create repository skeleton and minimal Doorstop + metadata.
- Provide demo content for two L1/L2 nodes:
  - FPS/FID and SPS/DET (or similar)
- Ensure IDs match the required format.

### Phase 1 (Headless Core + validation) — highest priority
- Implement metadata loader.
- Implement Pydantic models for:
  - Requirement, Risk, Interface, Document, Data, Note
  - Link object (typed relations)
- Implement dynamic enum enforcement sourced from metadata:
  - status, people IDs, category paths, system paths, L3 codes
  - Approach: generate a Python module `tools/qingsong/generated/enums.py` at runtime (or at build step) OR build Enums dynamically in memory; document the choice.
- Implement validators:
  - Pydantic validation per item type
  - referential integrity checks (owner exists, system path exists, categories exist)
  - link existence checks and link-type constraints
  - “no hard delete” policy enforced in CI (detect removed Doorstop item files)
- Add pre-commit and GitHub Actions CI to run:
  - `qingsong meta validate`
  - `qingsong validate`

### Phase 2 (SQLite cache + query)
- Implement cache builder to generate `index/qingsong.sqlite` (do not commit by default).
- Include tables:
  - `items` (current items)
  - `links`
  - `meta_hierarchy`, `meta_people`, `meta_vocab_*`
  - optional `items_fts` FTS table
- Implement `qingsong query "<SQL>"`.
- Implement the “interactive database” separation:
  - load items → in-memory objects → optional manipulation layer → flush-to-YAML explicitly

### Phase 3 (CLI ergonomics + UI)
- Ensure CLI is a thin wrapper over Core API.
- Implement Streamlit UI:
  - filter by system_path, type, status, owner, category
  - table view + detail view
  - show linked neighbors (list first; graph optional)
- Add basic graph visualization command `qingsong graph <ID>` (networkx + export to HTML or simple plot).

### Phase 4 (exports)
- Implement exports to create “communication documents” (Markdown/HTML first; Word/PDF later):
  - generate grouped requirement documents by `category_path` for a selected system node
  - export risk register and interface list subsets

---

## 5) Implementation instructions and specific commands

### Tech stack
- Python 3.11+
- doorstop (dependency)
- typer (CLI)
- pydantic v2 (schema + validation; canonical source of truth)
- ruamel.yaml (preferred for safe YAML round-tripping and formatting)
- sqlite3 (stdlib)
- streamlit (phase 3)
- networkx (phase 3)
- rich (optional, for better CLI UX)

### Tasks for you (the coding agent)

#### 5.1 Initialize repository with the directory structure exactly as below:

```
qingsong/
  README.md
  pyproject.toml
  .gitignore
  .pre-commit-config.yaml
  .github/workflows/ci.yml

  doorstop/
    REQ/
    RSK/
    IFC/
    DOC/
    DAT/
    NOTE/

  meta/
    hierarchy.yaml
    people.yaml
    glossary.yaml
    vocab/
      status.yaml
      req_category.yaml
      risk_category.yaml
      ifc_type.yaml
      link_types.yaml

  tools/
    qingsong/
      __init__.py
      cli.py
      core.py
      load_meta.py
      doorstop_io.py
      validate.py
      cache_build.py
      export.py
      graph.py
      models/
        __init__.py
        common.py
        requirement.py
        risk.py
        interface.py
        document.py
        data.py
        note.py
      generated/
        __init__.py
        enums.py              # generated OR dynamically created; choose and document
      ui/
        app_streamlit.py

  index/
    .gitkeep                 # keep folder in git; sqlite output not committed

  assets/
    README.md

  examples/
    README.md
```

#### 5.2 Create minimal metadata files with realistic content
- `meta/hierarchy.yaml` must contain:
  - MUST (L0)
  - FPS (L1) → FID (L2) with example L3 tasks: `FID-AIT`, `FID-CAL`
  - SPS (L1) → DET (L2) with example L3 tasks: `DET-CRYO`, `DET-CAL`
- `meta/people.yaml`: at least 3 people entries including a placeholder for the user as owner.
- `meta/vocab/status.yaml`: `draft, active, retired, superseded`
- `meta/vocab/link_types.yaml`: define at least these link types with allowed src/dst types:
  - `implements` (DOC|DAT|NOTE → REQ)
  - `verifies` (DOC|DAT|NOTE → REQ)
  - `mitigates` (NOTE|DOC → RSK)
  - `impacts` (RSK → REQ|IFC|DOC)
  - `defines_interface` (DOC → IFC)
  - `related_to` (any ↔ any)

#### 5.3 Implement Pydantic models (canonical schema)
- For each item type, enforce:
  - required fields vs optional fields
  - single-select enums and multi-select lists with `uniqueItems`-like behavior
  - timestamp format (ISO 8601)
  - links as typed objects
- Required common fields across all item types:
  - `type` (REQ/RSK/IFC/DOC/DAT/NOTE)
  - `title`
  - `text` (markdown; long text allowed)
  - `system_path` (from hierarchy; enum/validated)
  - `l3` (optional; validated against hierarchy if provided)
  - `category_path` (validated against type-specific taxonomy)
  - `status` (enum)
  - `owner` (enum)
  - `collaborators` (list enum; unique)
  - `links` (list of link objects)
  - lifecycle/retirement fields
  - timestamps: `created_at`, `updated_at`
- Do not maintain standalone JSON Schema files as enforcement; Pydantic is enforcement.

#### 5.4 Implement the Headless Core API
- `core.py` must expose functions/classes that:
  - load metadata
  - load all Doorstop items into typed Pydantic objects
  - validate everything (item-level + cross-file + link graph rules)
  - build SQLite cache
  - stage edits and flush changes back to YAML files explicitly (do not auto-write on load)

#### 5.5 Implement `qingsong` CLI
- Entry point executable: `qingsong`
- Commands (thin wrappers over core):
  - `qingsong meta validate`
  - `qingsong validate`
  - `qingsong new req|rsk|ifc|doc|dat|note --system MUST/FPS/FID --title "..."`  
    - Must create a new Doorstop item in the correct document folder using Doorstop mechanisms.
    - Populate defaults: `status=draft`, timestamps, empty `links`, etc.
  - `qingsong cache build` → writes `index/qingsong.sqlite`
  - `qingsong query "<SQL>"`
  - `qingsong ui` (Phase 3; may be stub initially)

#### 5.6 Set up Doorstop documents for demo
- Create `.doorstop.yml` files under:
  - `doorstop/REQ/FPS/FID/`
  - `doorstop/RSK/FPS/FID/`
  - `doorstop/IFC/FPS/FID/`
  - `doorstop/REQ/SPS/DET/` (and corresponding RSK/IFC)
- Configure prefixes:
  - REQ/FPS/FID: `MUST-FPS-FID-REQ`
  - RSK/FPS/FID: `MUST-FPS-FID-RSK`
  - IFC/FPS/FID: `MUST-FPS-FID-IFC`
  - etc.
- Add at least:
  - 2 demo requirements, 1 demo risk, 1 demo interface for FPS/FID
  - 1 demo requirement for SPS/DET
- Create links showing cross-system interconnection:
  - a risk in FPS/FID that impacts a requirement in SPS/DET via `impacts` link.

#### 5.7 Provide developer documentation in README
Include:
- install steps
- how to run meta validation and full validation
- how to add a new item
- how to build the cache and query it
- how to run the UI

### Commands to execute (must be included in README and must work)
- Repo init steps:
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install -e .`
  - `qingsong meta validate`
  - `qingsong validate`
  - `qingsong cache build`
  - `qingsong query "SELECT type, id_full, system_path, status FROM items LIMIT 20;"`
  - `qingsong ui`

### Output expectations
- All files created; repo is runnable locally.
- CI passes on a clean checkout.
- Demo items exist and validate.
- SQLite cache is generated successfully.


### Requirements for Integration & Extensibility

- Ensure the code is typed (using Python `TypeHints`) and documented.
- Design the system so that `Doorstop` is used for storage and linking, but Qingsong owns the validation logic.
- Leave architectural hooks for a future `Streamlit` UI (e.g., ensure `Qingsong` can return data as Pandas DataFrames).

Proceed to implement the above repository in full. Do not ask clarifying questions; make reasonable defaults and document them.
