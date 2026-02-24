# Qingsong Development TODO

## Week 1: Foundation & Alignment
- [x] Migrate to `uv` environment.
- [x] Bootstrap documentation: `SPEC.md`.
- [x] Bootstrap documentation: `PLAN.md`, `TODO.md`, `lessons.md`.
- [x] Fix metadata inconsistencies in `people.yaml` (PM IDs in `valid_person_ids`).
- [x] Refactor `QingsongCore.create_item` to use staging (don't write to disk immediately).
- [x] Expand Pydantic models to use metadata-driven validation (strict mode).

## Week 2: Robustness & Validation
- [ ] Implement circular dependency detection.
- [x] Add support for flexible L3 folder structures.
- [ ] Refactor `doorstop_io` for more resilient I/O.

## Week 3: CLI & Search
- [ ] Add `qingsong find` command.
- [ ] Improve `export` formatting (Markdown/PDF).
- [ ] Implement `qingsong migrate` for system refactoring.

## Week 4: Verification & Graph
- [ ] Implement Traceability Matrix generation.
- [ ] Add interactive graph component to WebUI.
- [ ] Reach >80% test coverage.
