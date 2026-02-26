# Qingsong Development TODO

## Planning & Foundation (Phase 1 Completed)

| ID | Task | Owner | Status | Notes |
| --- | --- | --- | --- | --- |
| P1-001 | Environment Standardization | agent | [x] Done | `uv` migration and fixed `.venv` synced. |
| P1-002 | Architectural Specification | agent | [x] Done | `SPEC.md`, `PLAN.md`, `TODO.md`, `lessons.md`. |
| P1-003 | Core API Refactoring | agent | [x] Done | Staging/Persistence logic (`create_item`, `flush()`). |
| P1-004 | Strict Metadata Validation | agent | [x] Done | Strict validation against `meta/` via Pydantic. |

## Implementation Backlog (Phase 2 Current)

| ID | Task | Owner | Status | Notes |
| --- | --- | --- | --- | --- |
| P2-001 | Flexible L3 Hierarchy | agent | [x] Done | Support nested `L1/L2/L3` folder structures. |
| P2-002 | Link Graph Validation | agent | [x] Done | Implement circular dependency detection. |
| P2-003 | Resilient I/O Refactor | agent | [x] Done | Improve `doorstop_io` for more resilient I/O. |
| P2-004 | Comprehensive Unit Testing | agent | [x] Done | Achieve >60% coverage for core and validation. |

## Implementation Backlog (Phase 3 & 4)

| ID | Task | Owner | Status | Notes |
| --- | --- | --- | --- | --- |
| P3-001 | Advanced Search CLI | agent | [x] Done | Implement `qingsong find` command. |
| P3-002 | Migration Utility | agent | [x] Done | Build `qingsong migrate` for refactoring. |
| P3-003 | Multi-format Export | agent | [x] Done | Improve Markdown/PDF/CSV formatting. |
| P4-001 | Traceability Matrix | agent | [x] Done | Implement automated UTM/DTM generation. |
| P4-002 | Verification Tracking | agent | [x] Done | Implement verification status roll-ups. |
| P4-003 | Production Hardening | agent | [x] Done | Final docs and >80% test coverage. |

## Implementation Backlog (Phase 5 Completed)

| ID | Task | Owner | Status | Notes |
| --- | --- | --- | --- | --- |
| P5-001 | CLI Root Parameter | agent | [x] Done | Allow `--root` argument for Vault selection. |
| P5-002 | Path Context Refactor | agent | [x] Done | Refactor Core to eliminate hardcoded globals. |
| P5-003 | Project Scaffolding | agent | [x] Done | Build `qingsong init` command. |

## Implementation Backlog (Phase 6 Current)

| ID | Task | Owner | Status | Notes |
| --- | --- | --- | --- | --- |
| P6-001 | UI Architecture Refactor | agent | [x] Done | Multi-page layout and `QINGSONG_ROOT` support. |
| P6-002 | Verification & Traceability | agent | [x] Done | UI views for `get_verification_summary` and `get_traceability_matrix`. |
| P6-003 | Advanced Search & Graph | agent | [x] Done | FTS5 integration and HTML graph embedding. |
| P6-004 | Interactive Editor (Draft) | agent | [x] Done | Web forms for `create_item` and `flush`. |

## Current Session Slice Plan (UI Architecture Refactor)

| Step | Status | Notes |
| --- | --- | --- |
| [x] S1 | Done | Restructure `tools/qingsong/ui/` to support Streamlit multi-page (`pages/`). |
| [x] S2 | Done | Ensure `load_core()` in UI respects the `QINGSONG_ROOT` environment variable. |
| [x] S3 | Done | Create the main Dashboard landing page (`app_streamlit.py`). |
| [x] S4 | Done | Create the Items Explorer page (`pages/1_Items.py`). |
| [x] S5 | Done | Verify UI launches successfully with new structure. |

## Review Notes

- 2026-02-24: Phase 1 documentation and environment baseline established.
- 2026-02-24: Refactored Core API for staging logic.
- 2026-02-25: Phase 2 initiated. Completed Flexible L3 Hierarchy (P2-001) implementation and validation.
- 2026-02-25: Transitioned `PLAN.md` and `TODO.md` to professional "Phase" and "ID" tracking system.
- 2026-02-25: Completed Phase 2 (P2-002, P2-003, P2-004). Implemented circular dependency detection, resilient I/O, and achieved 60% test coverage.
- 2026-02-26: Completed Phase 3 (P3-001, P3-002, P3-003). Implemented `find`, `migrate` commands and enhanced export capabilities.
- 2026-02-26: Completed Phase 4 (P4-001, P4-002, P4-003). Implemented traceability matrices, verification tracking, and achieved 83% non-UI test coverage.
- 2026-02-26: Completed Phase 5 (P5-001, P5-002, P5-003). Refactored core to support dynamic project roots and implemented `qingsong init` for multi-vault support.
