# Qingsong Development Lessons

## 1. Hierarchy & Storage (2026-02-25)
### Flexible L3 Folders
**Decision**: Allow L3 task codes (e.g., `FID-AIT`) to be used as sub-directories under `L1/L2` in the Doorstop storage.
**Rationale**: Complex systems like MUST require more than two levels of organization. Treating L3 folders as first-class Doorstop documents allows for cleaner separation of files and localized `.doorstop.yml` configuration (including custom prefixes).
**Implementation**:
- `_infer_hierarchy_context` in `doorstop_io.py` now extracts both `system_path` (L1/L2) and `l3` from the file path.
- `QingsongCore.create_item` and `flush()` were updated to respect this nested structure.

### Flexible ID Validation
**Decision**: Relaxed the `id_full` regex and validation to support 5 or 6-part IDs.
**Rationale**: Standard Doorstop IDs are typically 4-5 parts. By supporting 6 parts (`MUST-L1-L2-L3-TYPE-NNN`), we accommodate systems where L3 provides its own naming scope.
**Implementation**:
- Updated Pydantic `BaseItem` regex.
- Updated `validate_id_format` to check consistency between ID segments and item attributes (`system_path`, `l3`).

## 3. Project Portability (2026-02-26)
### Dynamic Root Context
**Decision**: Use an environment variable (`QINGSONG_ROOT`) to bridge the gap between CLI arguments and deep Pydantic validation.
**Rationale**: Pydantic's `model_validator` methods are often called in isolated contexts where CLI-level state isn't available. A standardized env var ensures all layers of the engine resolve metadata paths consistently.
**Implementation**: `get_project_root` checks `QINGSONG_ROOT` before falling back to auto-discovery.

## 4. UI Architecture (2026-02-27)
### Multi-Page Dashboard
**Decision**: Transition from a single `app_streamlit.py` to a `pages/` directory structure.
**Rationale**: As features like Impact Analysis and Traceability grew, a single-page layout became cluttered. A multi-page approach improves focus and allows for deeper interactive components (like the Item Editor) without side effects on other views.

## 5. Analytical Intelligence (2026-02-27)
### Transitive Impact Tracing
**Decision**: Implement bi-directional recursive traversal for impact analysis.
**Rationale**: Simple link checking only shows the first level of impact. True system engineering requires seeing the "end-to-end" ripple effect of a change across the parent/child requirement chain.

## 6. Review of the February build (2026-11-01)

The full review is in the conversation of 2026-11-01; the rebuild plan is in the private record repository. These lessons apply to the rebuild.

- **"Done" means verified, not implemented.**
  - Twelve phases were marked Done in four days, yet `main` failed its own `qingsong validate`: `related_to` links declared bidirectional were reported as a cycle.
  - CI hid test failures with `|| echo "No tests yet"`.
  - From now on, a task is done only when its acceptance check has run and passed.
- **Tests must never touch a real vault.**
  - The suite wrote items into `doorstop/REQ/FPS/FID/`. Items 003–012 there are test leftovers.
  - A global environment variable (`QINGSONG_ROOT`) leaked between tests and made them depend on run order.
  - Use only `tmp_path` fixtures and pass the root explicitly; no global state.
- **A location stored twice will drift.**
  - Folder and `system_path`/`l3` attributes both encoded where an item lives, and `migrate` produced duplicate items.
  - A path must be a pure function of the immutable ID.
- **A validator that skips is not a validator.**
  - Unreadable items became warnings and were dropped.
  - Duplicate IDs overwrote each other silently.
  - Missing fields received silent defaults.
  - A Pydantic validator swallowed its own errors.
- **Don't carry dependencies you don't use.** Doorstop was a dependency that nothing imported, and the tree was not Doorstop-valid.
- **Confidential content does not belong in a public repository.** `origin` is public. Team names, emails and the FPS schedule were removed from its history on 2026-11-01, and MUST content now lives in the private record repository.

## 7. Phase 0 (2026-11-01)

- **Check what a cited document is before building on a summary of it.** A research summary called a project workbook (a work breakdown) a requirements document. The draft plan mapped a requirement level onto it until the file itself was checked. Open the source, or its extraction, before placing a document in the specification tree.
- **Independent review before building.** A reviewer given the files, not the author's conclusions, found 24 problems in the first specification draft. The most serious were suspect links triggered by editorial changes, approvals not tied to the approved content, and ID collisions between branches. Review every specification change this way before implementation.

## 8. Overnight run (2026-11-02)

- **Verify that a write survives a read.** YAML line folding silently collapsed repeated spaces and broke a stamp.
  It was found only while importing the first real document. Every write is now parsed back and its stamp
  compared before the file is replaced.
- **Run the oldest supported Python before pushing.** A backslash inside an f-string expression is valid only from
  Python 3.12. Ruff caught it, but only after `target-version` checks ran on the whole tree.
- **Independent reviewers find what automated checks cannot.**
  - The transcription check confirmed every paragraph verbatim. Only the independent reviewer saw English bullets
    duplicated inside the Chinese text, wrong verification methods, and bracketed words that were not tracked.
  - The renderer review found script injection through embedded JSON, and ordinary text ("$5", "~45 m") read as
    markup.
  - Plan a review for every new layer that people will read.
- **A project's own conventions beat generic syntax.** In MUST documents any bracketed text marks a provisional
  value ("[five]"), not only bracketed numbers.
- **Never use `git stash -u` on a working tree with untracked work.** It briefly removes the untracked files.
  Copy the files to a scratch folder instead.
