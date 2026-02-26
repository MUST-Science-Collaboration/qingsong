# Qingsong Project Development Plan

## Strategic Goal
Deliver a robust, production-grade requirements management system (RMS) for the MUST telescope project, enabling a "Requirements as Code" workflow with strict validation and high-performance traceability.

## Phase 1: Foundation & Alignment (Completed)
**Objective**: Establish a standardized development environment, stabilize the core API, and implement the staging/persistence layer.

| ID | Task | Description |
| --- | --- | --- |
| P1-001 | Environment Standardization | Migrate to `uv`, fix broken `.venv`, and sync dependencies. |
| P1-002 | Architectural Specification | Draft `SPEC.md`, `PLAN.md`, and `TODO.md`. |
| P1-003 | Core API Refactoring | Implement in-memory staging and explicit `flush()` logic. |
| P1-004 | Strict Metadata Validation | Expand Pydantic models to enforce referential integrity against `meta/`. |

## Phase 2: Robustness & Validation (Completed)
**Objective**: Ensure data integrity across hierarchical levels and complex link networks.

| ID | Task | Description |
| --- | --- | --- |
| P2-001 | Flexible L3 Hierarchy | Support nested `L1/L2/L3` folder structures as first-class documents. |
| P2-002 | Link Graph Validation | Implement circular dependency detection for derivation and implementation links. |
| P2-003 | Resilient I/O Refactor | Improve `doorstop_io` to handle corrupted YAMLs and missing configs gracefully. |
| P2-004 | Comprehensive Unit Testing | Achieve >60% coverage for core and validation modules. |

## Phase 3: CLI & Search Expansion (Completed)
**Objective**: Enable efficient engineer workflows through advanced CLI tools and refactoring utilities.

| ID | Task | Description |
| --- | --- | --- |
| P3-001 | Advanced Search CLI | Implement `qingsong find` with metadata filters and FTS5 search (Done). |
| P3-002 | Migration Utility | Build `qingsong migrate` to handle ID updates and link refactoring during system moves (Done). |
| P3-003 | Multi-format Export | Enhance Markdown and CSV export capabilities for external reviews (Done). |

## Phase 4: Verification & Traceability (Completed)
**Objective**: Finalize the verification loop and deliver automated compliance reporting.

| ID | Task | Description |
| --- | --- | --- |
| P4-001 | Traceability Matrix | Generate automated Upward/Downward Traceability Matrices (UTM/DTM) (Done). |
| P4-002 | Verification Tracking | Implement verification status roll-ups and compliance dashboard (Done). |
| P4-003 | Production Hardening | Final documentation pass, performance profiling, and >80% test coverage (non-UI) (Done). |

## Phase 5: Project Portability (Completed)
**Objective**: Transform Qingsong from a single-project repository into a portable engine capable of managing multiple independent "vaults" (e.g., MUST vs. Demo).

| ID | Task | Description |
| --- | --- | --- |
| P5-001 | CLI Root Parameter | Allow `qingsong --root ./my-demo ...` to override the default project directory (Done). |
| P5-002 | Path Context Refactor | Refactor `QingsongCore` to dynamically resolve paths based on the specified root rather than hardcoded global paths (Done). |
| P5-003 | Project Scaffolding | Implement `qingsong init` to generate a fresh vault structure (`meta/`, `doorstop/`) with default YAML templates (Done). |

## Phase 6: WebUI Redesign & Integration (Completed)
**Objective**: Transform the read-only Streamlit UI into a full-featured dashboard that exposes all advanced CLI capabilities and introduces interactive editing.

| ID | Task | Description |
| --- | --- | --- |
| P6-001 | UI Architecture Refactor | Upgrade to a Streamlit Multi-Page App structure for better navigation and ensure the UI respects the `QINGSONG_ROOT` environment variable (Done). |
| P6-002 | Verification & Traceability | Build dedicated views for the Verification Dashboard and Traceability Matrices (Upward/Downward) (Done). |
| P6-003 | Advanced Search & Graph | Integrate SQLite FTS5 search into the UI and embed interactive NetworkX graphs for visual dependency tracking (Done). |
| P6-004 | Interactive Editor (Draft) | Implement form components to create, update, and migrate items directly from the browser using the staging API (Done). |

## Phase 7: Stability Tracking (Completed)
**Objective**: Explicitly manage items with "TBD" or "TBC" placeholders to track project maturity.

| ID | Task | Description |
| --- | --- | --- |
| P7-001 | Placeholder Detection | Implement automatic `has_placeholders` detection in the item model (Done). |
| P7-002 | CLI TBD Filter | Add `--tbd` filter to the `find` command for rapid isolation (Done). |
| P7-003 | UI Stability Dashboard | Create a "Stability Watchlist" panel on the UI Dashboard (Done). |
| P7-004 | UI Visual Highlighting | Add visual warnings and filters for unstable items in the Items Explorer (Done). |

## Phase 8: Automated Compliance & Export (Completed)
**Objective**: Transition "Requirements as Code" into formal, review-ready documents and automate repository health checks.

| ID | Task | Description |
| --- | --- | --- |
| P8-001 | PDF Export Engine | Implement a robust PDF generation engine with professional headers/footers (Done). |
| P8-002 | Formal Document Templates | Create "Requirements Specification" and "Risk Register" PDF layouts (Done). |
| P8-003 | Compliance Reporting | Generate a "Project Maturity Report" rolling up verification and stability metrics (Done). |
| P8-004 | CI/CD Automation | Integrate automated validation and cache building into git hooks (Done). |
