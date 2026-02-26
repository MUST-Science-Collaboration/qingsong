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
