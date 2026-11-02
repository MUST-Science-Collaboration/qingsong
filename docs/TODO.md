# qingsong TODO

The architecture is in [SPEC.md](SPEC.md). The rebuild plan and the project-specific conventions of the first user live in its private record repository (`docs/PLAN.md`, `docs/CONVENTIONS.md`), because they contain project-internal structure. The task list of the earlier version 0.1 is archived in [journal/2026-02_legacy_todo.md](journal/2026-02_legacy_todo.md).

Status: `[x]` done, `[ ]` open, `[~]` partly done. "Next" items come first in their phase.

## Phase 0: specification and reset (done 2026-11-01)

| ID | Task | Status | Notes |
| --- | --- | --- | --- |
| R0-001 | Review of the legacy build | [x] Done | Lessons in `lessons.md` §6 |
| R0-002 | Research: tools, systems-engineering frameworks, observatory practice | [x] Done | in the record repository (`docs/RESEARCH.md`) |
| R0-003 | Rebuild plan and interview | [x] Done | in the record repository (`docs/PLAN.md`); decisions of 2026-11-01 in SPEC §16 |
| R0-004 | Remove project names, emails and schedule from public history | [x] Done | filter-repo and force push, 2026-11-01 (a07af95 → 692d1af) |
| R0-005 | Engine specification `SPEC.md` v0.2 and the record repository's conventions | [x] Done | Independent review: 24 findings, all addressed or put to the Project Scientist |
| R0-006 | Tag `legacy-0.1`; remove the legacy package | [x] Done | tag pushed |
| R0-007 | New package skeleton, uv lock, pre-commit, CI | [x] Done | CI runs on GitHub on every push |
| R0-008 | Draft product tree and vault configuration in the record repository | [x] Done | 82 nodes; merged there |
| R0-009 | Roadmap page (HTML) of the record repository, for checking levels, codes and systems | [x] Done | generated from the tree, in the record repository |

## Phase 1: core engine (done 2026-11-02)

| ID | Task | Status | Notes |
| --- | --- | --- | --- |
| R1-001 | Schemas, strict vault I/O, IDs and aliases, stamps, operations, CLI | [x] Done | |
| R1-002 | Check rules, each with a triggering fixture | [x] Done | 35 at first; 43 now |
| R1-003 | Demo vault; benchmark (10,000 records: load 4.9 s, check 3.6 s) | [x] Done | SPEC §13 |
| R1-004 | Independent code review, all findings fixed | [x] Done | 13 groups of findings |

## Phase 2: first real vault (done 2026-11-02, in the record repository)

| ID | Task | Status | Notes |
| --- | --- | --- | --- |
| R2-001 | Tree, people, glossary and quantities of the first project | [x] Done | |
| R2-002 | Import of the first requirement document, every requirement accounted for | [x] Done | by a script of the record repository; `qingsong import docx` is not built (SPEC §11) |

## Phase 3: HTML (first slice done 2026-11-02)

| ID | Task | Status | Notes |
| --- | --- | --- | --- |
| R3-001 | Site: home, interactive tree, flow-down diagram, documents with figures, requirement pages, registers, checks, search, language switch | [x] Done | `qingsong render html` |
| R3-002 | Change views between releases | [x] Done 2026-11-02 | `documents/<DOC>-changes.html`, linked from the document page |
| R3-003 | Review: labelled issues raised from findings, proposed fixes with differences, approver decisions (`qingsong issue …`), review page, marks in documents (SPEC §5.6) | [x] Done 2026-11-02 | the Project Scientist's request of 2026-11-02 |
| R3-006 | Review page: choose the person from people.yaml instead of typing an ID | [x] Done 2026-11-02 | decisions had come out with a placeholder ID |
| R3-007 | Submitting review decisions without copying commands | [x] Done 2026-11-02 | "Save decisions" downloads a decisions file; `qingsong issue apply FILE` applies it all or nothing, refuses proposals changed since they were read, starts a review branch on main, and keeps the file in `reviews/`. No local server (SPEC §5.6) |
| R3-004 | The "EN + 中文" view is crowded | [~] Eased | Chinese set off by a rule and spacing; a side-by-side layout is left for later |
| R3-005 | Review packages for a node's design review; N² interface matrix | [ ] Later | needs interfaces in a real vault |

## Phase 4: Word and releases (first slice done 2026-11-02)

| ID | Task | Status | Notes |
| --- | --- | --- | --- |
| R4-001 | `qingsong render docx`: the project's layout, bilingual requirements, figures, tables, TOC, header and footer | [x] Done | pilot: 610 of 612 body units of the pilot document reproduced; 2 intended differences |
| R4-002 | Confirm the generated file opens in Word without repair | [x] Done 2026-11-02 | opens; the "fields that may refer to other files" prompt came from updateFields |
| R4-004 | No prompt on opening: the table of contents is written out, with links; `--update-fields` restores update-on-open | [x] Done 2026-11-02 | page numbers appear after a field update in Word |
| R4-003 | Releases: `release prepare` (branch), `release tag` (after the merge, at the commit that brought the entry in), `release changes`; `render docx --release V` from the tag | [x] Done 2026-11-02 | SPEC §5.5, revised after an independent review; dry run on a copy of the record |
| R4-006 | Revision marks in the Word copy of a release | [x] Not needed | the Project Scientist, 2026-11-02: Word is a snapshot; it shows the current version |
| R4-005 | The project's standard style and front page | [ ] Later | the Project Scientist, 2026-11-02: not critical |

## Phase 5: upper levels and expansion (engine side)

| ID | Task | Status | Notes |
| --- | --- | --- | --- |
| R5-009 | Slot moves as proposals on the review page, so the approver sees each move before it is applied | [ ] Next | until then, moves are made on a content branch; the changes page shows each move as a reader sees it |
| R5-011 | A relation word after a slot is often a preposition ("{x} over one night", "≥ 40 % over the band"), yet it is warned about as a relation said twice | [ ] Next | found while writing the how-to, 2026-11-03; after a slot, only phrases such as "or more" repeat a relation |
| R5-012 | A check that every current requirement in a document's scope appears in its outline | [ ] Next | in SPEC §10 but not built; a new requirement can be left out of its document unnoticed |
| R5-001 | `consistency` rules: conflicting values, a child looser than its parent (reversed for environmental quantities), overdue issues | [x] Done 2026-11-02 | SPEC §10; interval semantics tested |
| R5-002 | `documents` rules: release entries well formed; release tags mark the entry; entries append-only against main | [x] Done 2026-11-02 | |
| R5-003 | `qingsong export json`, with value intervals, for analysis codes | [x] Done 2026-11-02 | SPEC §12.3 |
| R5-004 | Forms of requirement (qualitative / quantitative, marked and exported); slot goals; `qingsong slot` moves numbers into slots keeping the meaning and the approval | [x] Done 2026-11-02 | decided by the Project Scientist; design reviewed independently before coding |
| R5-005 | `qingsong new issue\|decision\|waiver\|interface\|condition\|source\|verification --file draft.yaml` | [x] Done 2026-11-02 | IDs allocated per type, also against main; the draft is left as written |
| R5-007 | CI for a record repository: check against main on every pull request, site as an artifact | [x] Done 2026-11-02 | the record repository pins the engine commit it checks with |
| R5-008 | Translation review of figure captions and document text | [x] Done 2026-11-02 | the release gate found captions not yet reviewed; they were reviewed before the release |
| R5-006 | N² interface matrix | [ ] Later | interfaces and conditions already appear in the registers |
| R5-010 | Units for attenuation (dB/km) and stress (kpsi); a statement that gives one limit twice | [ ] Later | why some values of the pilot document stay in prose |

## Documentation (done 2026-11-03)

| ID | Task | Status | Notes |
| --- | --- | --- | --- |
| D-001 | How to use qingsong (`docs/howto.md`): concepts, rules, workflow and worked examples for people and agents | [x] Done | every example run on a copy of the demo vault |
| D-002 | API reference (`docs/api.md`): architecture, invariants, extending; commands, rules and modules generated from the code | [x] Done | |
| D-003 | `tools/build_docs.py`: HTML pages of every document, the entrance `docs/index.html`, and the generated reference; a test fails when they are out of date | [x] Done | |
| D-004 | Review of every document against the code | [x] Done | SPEC: the rule catalogue, commands, module map, rendering, quantities and `revise` corrected |
