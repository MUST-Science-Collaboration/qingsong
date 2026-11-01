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
| R0-008 | Draft MUST tree and vault configuration in `must_req` | [x] Drafted | From the FPS and SPG breakdown workbooks |
| R0-009 | Roadmap page (HTML) for the Project Scientist's check of levels, codes and systems | [ ] Pending | Generated from `must_req/tree/` |

## Next: Phase 1 (core engine)

Schemas, vault I/O, IDs and aliases, hashing, operations, check groups `integrity`, `structure`, `change`, `content`; synthetic demo vault; 10,000-record benchmark. Starts after the Project Scientist has checked the roadmap.
