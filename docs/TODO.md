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

## Implementation Backlog (Phase 7 Current)

| ID | Task | Owner | Status | Notes |
| --- | --- | --- | --- | --- |
| P7-001 | Placeholder Detection | agent | [x] Done | `has_placeholders` property in BaseItem. |
| P7-002 | CLI TBD Filter | agent | [x] Done | `qingsong find --tbd` filter. |
| P7-003 | UI Stability Dashboard | agent | [x] Done | "Stability Watchlist" on main dashboard. |
| P7-004 | UI Visual Highlighting | agent | [x] Done | Warning icons and TBD filter in Explorer. |

## Implementation Backlog (Phase 10 Completed)

| ID | Task | Owner | Status | Notes |
| --- | --- | --- | --- | --- |
| P10-001 | Impact Logic | agent | [x] Done | Recursive traversal for transitive dependencies. |
| P10-002 | Impact CLI | agent | [x] Done | `qingsong impact` command. |
| P10-003 | Impact UI | agent | [x] Done | "Impact Explorer" in WebUI item details. |

## Implementation Backlog (Phase 11 Completed)

| ID | Task | Owner | Status | Notes |
| --- | --- | --- | --- | --- |
| P11-001 | Gap Detection Logic | agent | [x] Done | Logic for root/leaf orphans and unverified items. |
| P11-002 | Coverage Analytics | agent | [x] Done | Traceability and verification percentage metrics. |
| P11-003 | Reporting CLI | agent | [x] Done | `qingsong report` command group. |
| P11-004 | UI Insights Page | agent | [x] Done | New "Insights" page in WebUI. |

## Implementation Backlog (Phase 12 Completed)

| ID | Task | Owner | Status | Notes |
| --- | --- | --- | --- | --- |
| P12-001 | Direct Item Editing | agent | [x] Done | Web forms for updating item content. |
| P12-002 | In-Place Linking | agent | [x] Done | Tool for adding/removing links in UI. |
| P12-003 | Interactive Migrations | agent | [x] Done | UI form for `migrate_item`. |
| P12-004 | UX Polish | agent | [x] Done | Styling, colors, and quick-actions. |

## Current Session Slice Plan (Enhanced UI)

| Step | Status | Notes |
| --- | --- | --- |
| [x] S1 | Done | Add "Edit Mode" toggle and form to `1_Items.py`. |
| [x] S2 | Done | Implement link management UI in item details. |
| [x] S3 | Done | Add "Migrate Item" expander to item details. |
| [x] S4 | Done | Add "Quick Links" to Dashboard for common tasks. |
| [x] S5 | Done | Verify all interactive flows in browser. |

## Review Notes

- 2026-02-24: Phase 1 documentation and environment baseline established.
- 2026-02-24: Refactored Core API for staging logic.
- 2026-02-25: Phase 2 initiated. Completed Flexible L3 Hierarchy (P2-001) implementation and validation.
- 2026-02-25: Transitioned `PLAN.md` and `TODO.md` to professional "Phase" and "ID" tracking system.
- 2026-02-25: Completed Phase 2 (P2-002, P2-003, P2-004). Implemented circular dependency detection, resilient I/O, and achieved 60% test coverage.
- 2026-02-26: Completed Phase 3 (P3-001, P3-002, P3-003). Implemented `find`, `migrate` commands and enhanced export capabilities.
- 2026-02-26: Completed Phase 4 (P4-001, P4-002, P4-003). Implemented traceability matrices, verification tracking, and achieved 83% non-UI test coverage.
- 2026-02-26: Completed Phase 5 (P5-001, P5-002, P5-003). Refactored core to support dynamic project roots and implemented `qingsong init` for multi-vault support.
- 2026-02-26: Completed Phase 6 (P6-001, P6-002, P6-003, P6-004). Redesigned WebUI into a multi-page dashboard with advanced insights and interactive item creation.
- 2026-02-27: Completed Phase 7 (P7-001, P7-002, P7-003, P7-004). Implemented TBD/TBC placeholder tracking and integrated it into the CLI and WebUI.
- 2026-02-27: Completed Phase 8 (P8-001, P8-002, P8-003, P8-004). Implemented PDF export engine and formal document templates, and updated pre-commit hooks for CI/CD automation.
- 2026-02-27: Completed Phase 9 (P9-001, P9-002, P9-003, P9-004). Implemented design discussions, enhanced FTS5 search with snippets, and added collaborator management to the WebUI.
- 2026-02-27: Completed Phase 10 (P10-001, P10-002, P10-003). Implemented recursive impact analysis in core, CLI, and WebUI.
- 2026-02-27: Completed Phase 11 (P11-001, P11-002, P11-003, P11-004). Implemented orphan detection and coverage reporting in core, CLI, and a new WebUI "Insights" page.
- 2026-02-27: Completed Phase 12 (P12-001, P12-002, P12-003, P12-004). Enhanced WebUI with in-place editing, link management, interactive migrations, and dashboard quick-actions.
