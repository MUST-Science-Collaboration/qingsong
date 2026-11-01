# qingsong TODO

The architecture is in [SPEC.md](SPEC.md). The rebuild plan and the MUST-specific conventions live in the private record repository `must_req` (`docs/PLAN.md`, `docs/CONVENTIONS.md`), because they contain MUST-internal structure. The task list of the earlier version 0.1 is archived in [journal/2026-02_legacy_todo.md](journal/2026-02_legacy_todo.md).

## Phase 0: specification and reset (branch `feature/rebuild-plan`)

| ID | Task | Status | Notes |
| --- | --- | --- | --- |
| R0-001 | Review of the legacy build | [x] Done | Lessons in `lessons.md` §6 |
| R0-002 | Research: tools, systems-engineering frameworks, observatory practice | [x] Done | `must_req/docs/RESEARCH.md` |
| R0-003 | Rebuild plan and interview | [x] Done | `must_req/docs/PLAN.md`; decisions of 2026-11-01 in SPEC §16 |
| R0-004 | Remove MUST names, emails and schedule from public history | [x] Done | filter-repo and force push, 2026-11-01 (a07af95 → 692d1af) |
| R0-005 | Engine specification `SPEC.md` v0.2 and `must_req/docs/CONVENTIONS.md` | [x] Done | Independent review: 24 findings, all addressed or put to the Project Scientist |
| R0-006 | Tag `legacy-0.1`; remove the legacy package | [x] Done | Tag local only until a push is approved |
| R0-007 | New package skeleton, uv lock, pre-commit, CI | [x] Done (local) | Lint, format, tests, build and pre-commit pass locally; CI runs on GitHub after a push is approved |
| R0-008 | Draft MUST tree and vault configuration in `must_req` | [x] Done | 82 nodes; FPS and SPG from their breakdown workbooks; committed on `must_req` branch `feature/phase0-conventions` |
| R0-009 | Roadmap page (HTML) for the Project Scientist's check of levels, codes and systems | [x] Done | `must_req/docs/roadmap/index.html`, generated from the tree; awaiting the Project Scientist's check |

## Phase 1: core engine (done 2026-11-02)

| ID | Task | Status | Notes |
| --- | --- | --- | --- |
| R1-001 | Schemas, strict vault I/O, IDs and aliases, stamps, operations, CLI | [x] Done | |
| R1-002 | 35 check rules, each with a triggering fixture | [x] Done | |
| R1-003 | Demo vault; benchmark (10,000 records: load 4.9 s, check 3.6 s) | [x] Done | SPEC §13 |
| R1-004 | Independent code review, all findings fixed | [x] Done | 13 groups of findings |

## Phase 3: HTML (first slice done 2026-11-02)

| ID | Task | Status | Notes |
| --- | --- | --- | --- |
| R3-001 | Site: home, interactive tree, flow-down diagram, documents with figures, requirement pages, registers, checks, search, language switch | [x] Done | `qingsong render html` |
| R3-002 | Change views between releases; review packages; N² matrix | [ ] Next | |

## Phase 4: Word (first slice done 2026-11-02)

| ID | Task | Status | Notes |
| --- | --- | --- | --- |
| R4-001 | `qingsong render docx`: MUST layout, bilingual requirements, figures, tables, TOC field, header/footer | [x] Done | pilot: 610 of 612 body units of v1.1 reproduced; 2 intended differences |
| R4-002 | Confirm the generated file opens in Word without repair | [ ] Project Scientist | not possible unattended |
| R4-003 | `qingsong release` with tracked changes against the previous release | [ ] Next | |
