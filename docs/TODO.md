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
| P3-001 | Advanced Search CLI | agent | [ ] Pending | Implement `qingsong find` command. |
| P3-002 | Migration Utility | agent | [ ] Pending | Build `qingsong migrate` for refactoring. |
| P3-003 | Multi-format Export | agent | [ ] Pending | Improve Markdown/PDF/CSV formatting. |
| P4-001 | Traceability Matrix | agent | [ ] Pending | Implement automated UTM/DTM generation. |
| P4-002 | Verification Tracking | agent | [ ] Pending | Implement verification status roll-ups. |
| P4-003 | Production Hardening | agent | [ ] Pending | Final docs and >80% test coverage. |

## Current Session Slice Plan (Resilience & Testing)

| Step | Status | Notes |
| --- | --- | --- |
| [x] S1 | Done | Refactor `load_item` and `save_item` for resilience. |
| [x] S2 | Done | Add pre-save integrity checks in `core.py`. |
| [x] S3 | Done | Create `tests/test_validation.py` for edge cases. |
| [x] S4 | Done | Create `tests/test_doorstop_io.py` for I/O operations. |
| [x] S5 | Done | Achieve >60% test coverage. |

## Review Notes

- 2026-02-24: Phase 1 documentation and environment baseline established.
- 2026-02-24: Refactored Core API for staging logic.
- 2026-02-25: Phase 2 initiated. Completed Flexible L3 Hierarchy (P2-001) implementation and validation.
- 2026-02-25: Transitioned `PLAN.md` and `TODO.md` to professional "Phase" and "ID" tracking system.
- 2026-02-25: Completed Phase 2 (P2-002, P2-003, P2-004). Implemented circular dependency detection, resilient I/O, and achieved 60% test coverage.
