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

## 9. Review items and the Word prompt (2026-11-02)

- **A field added to a schema must default to `None`, not to an empty list.** The stamp hashes the record's
  dump without `None` values, so a new `proposals: []` default changed the stamp of every existing issue and
  made them all "unrecorded". Fields added later are optional and absent until used.
- **A mapping keyed by language is not necessarily text.** Hashes stored per language (`base`, `accepted`)
  had the same type as bilingual text, so the language checks read them as prose and reported "empty text".
  They now have their own type.
- **Word's "fields that may refer to other files" prompt comes from `updateFields`.** Both v1.1 and the
  generated file asked Word to update every field on opening. A written-out table of contents avoids it;
  page numbers then come from one field update in Word.
- **Keep content and traceability apart in severities.** Approving the fibre requirements turned 23
  "no parent" warnings into errors, although approval concerns the requirement's content. Traceability is
  now required at baseline, and tracked by an issue until then.
- **Group review items by the decision they need.** 24 wording findings became three issues: seven
  statements with one rewording proposal, one vague statement, and fifteen compound procedures with a
  keep-as-written proposal. One decision per issue is easier to review than 24 near-identical cards.

## 10. Releases (2026-11-02)

- **Review a workflow design against how git is used, not only against the code.** The first release design tagged
  HEAD after the merge. An independent review pointed out that with a squash merge followed by another merge, HEAD
  holds later, unreviewed changes. The tag now goes on the commit of the main branch's first-parent history that
  first contains the release entry, and the gate runs on that commit.
- **Dry-run a new gate on the real record before declaring it done.** The release gate, run on a copy of the record,
  found that the pilot document's figure captions had never been marked as reviewed translations: the bilingual check had
  covered requirements only.
- **Check the data a feature needs before building on it.** The consistency rules and the export's value index read
  value slots, but the pilot record keeps every number in prose. The engine works; the record has to catch up.
- **An independent code review found seven defects that 130 passing tests did not.** The worst:
  - an open-ended limit (`< 10`) carried its "open" flag onto the infinite end, so `≤ 5` did not count as
    inside `< 10`;
  - `--until` at a release compared that release with itself;
  - reordering a document was reported as "no changes".

  Each now has a regression test. Interval code needs tests at every combination of open, closed and infinite
  ends.
- **CI has no git identity.** Five release tests passed locally and failed on every CI runner: `git tag -a` and
  merge commits need a committer, which macOS derives from the host and a Linux runner does not. Reproduce CI
  locally with `GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=user.useConfigOnly
  GIT_CONFIG_VALUE_0=true`; test repositories set their own local identity.

## 11. Moving numbers into slots (2026-11-02)

- **A proof by comparison is only as good as its normalisation.** The first version of the slot move lower-cased
  everything, so "5 Mm" matched a slot in mm. It also removed spaces before reading thousands separators, so
  "5, 100 mm" matched 5100. And a unit-repeat rule without a boundary read "140 m ± 2 mm" as "140 ± 2 mm".
  An independent reviewer built each case. Normalise only what is known to be formatting, keep units exactly,
  and test every named difference against a near miss.
- **Guard every re-binding the same way.** The approval was re-bound only if it was current, but the
  translation hash was re-bound unconditionally, which marked a stale translation current. Anything that carries
  a review forward must check that the review was valid before.
- **Prefer the renderer over a second parser.** The design review replaced a planned literal grammar with "the
  slot must read the same". There is one rule for both writing and reading values, and one less parser to
  get wrong.
- **Run a new operation on the real record before calling it done.** The first real slot moves found three gaps that
  the demo did not:
  - "longer than" passed the neighbour check, so any comparative now counts;
  - the closing `~` of a subscript ("n~d~ ≥ 20") was read as "approximately";
  - an "accepted as written" decision did not survive a move that kept the meaning.

  Each was fixed with a test before the record was changed.

## 12. Decisions files (2026-11-02)

- **Record what was read when it was read.** Marks on the review page outlive a re-rendered page. Taking a
  proposal's hash when the file is saved would vouch for a version the reviewer may never have seen. The hash is
  taken when the proposal is marked, and a mark whose proposal has changed since is dropped on loading.
- **Check everything before writing anything, then still be ready to undo.** The decisions file checks every
  decision first and reports all problems at once. It also restores every file if a step fails later, because
  the checks repeat only part of what the operations enforce.
- **Run the page's own script, not a copy of its logic.** Running `review.js` in Node against a rendered page,
  then applying the downloaded file, tested the format the page actually writes, quotes and Chinese text
  included.

## 13. Documentation review (2026-11-03)

- **A specification drifts quietly.** Read against the code, it still listed `qingsong serve`, which
  the decision against a local server had made moot, and `qingsong import docx`, which was never built.
  It also had a rule catalogue mixing built and planned rules, a module map from before half the modules
  existed, and a rendering example that contradicted its own rule. Generated references (commands, rules,
  modules) cannot drift. The handwritten parts need a review against the code at each milestone.
- **Run the examples you document.** Writing the how-to on a copy of the demo found a false positive (a
  preposition after a slot read as a relation) and a check the specification promised but the code
  lacks (a requirement left out of its document).
- **A test that mixes the real date with a fixed one is a time bomb.** It passed the day it was written
  and failed the next, because history dates must not go backwards. Every call in a test takes the
  fixed date.
- **Generated text must not depend on the Python that generates it.** The API reference passed on
  3.11 to 3.13 and failed CI on 3.14. Python 3.14 no longer keeps a class's annotations in its
  `__dict__`, so the field tables vanished, and it prints `Optional[X]` as `X | None`. The builder now
  uses `inspect.get_annotations` and writes `X | None` everywhere. Compare the output on every
  supported version before pushing.

## 14. Word copies of a release (2026-11-10)

- **Read the issued pages, not only the package check.** The Word copy of a real release passed every
  test and the package check, yet its change record was hard to read:
  - the columns shared the width equally;
  - two long bilingual entries took most of a page each;
  - "Changed by" showed a person ID instead of the name.

  Render the PDF's pages to images and read them before a copy is issued. The change record now has
  fixed column widths and names from the people file. An entry too long for its cell goes to Appendix A,
  cited in its row.
- **The PDF route decides the fonts and where the document goes.** A PDF saved through Word's
  scripting interface was made by Microsoft's online service, the "Best for electronic distribution"
  export. That service replaced the document's fonts with Cambria and a Traditional Chinese font. The
  substitute's lines were taller than the document grid's pitch, so every Chinese line took two grid
  lines, which looked like double spacing. The same export also sent the document off the machine.
  With the document's own fonts each line fits one grid line. Make PDFs in Word with "Best for
  printing", and check every PDF with `pdfinfo` (a local export names Quartz as producer) and
  `pdffonts` before it is delivered.
- **Show names in documents people read.** IDs belong in the record and its history. Documents for
  readers resolve them through the people file, as the responsibilities table already did.
