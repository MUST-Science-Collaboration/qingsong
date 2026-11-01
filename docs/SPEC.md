# qingsong: specification

Version 0.2 (rebuild), 2026-11-01. This document is the architecture source of truth for the qingsong engine. Sections marked **accepted** reflect decisions of the Project Scientist (dated in §16). Sections marked **proposed** are recommendations that implementation may refine; changes are recorded here.

The first project to use qingsong is the MUST telescope. Its record repository is private. This public repository never holds MUST content: the examples here use a fictional project called DEMO.

## 1. Purpose and scope (accepted)

qingsong maintains a project's requirements as the **authoritative engineering record**. It also generates every human-readable form of that record.

- **Record.** Each requirement, interface, decision and related item is a small structured text file in a git repository, called the **vault**.
- **Authors and reviewers.** AI agents do most of the editing, and authorized people review and approve through pull requests.
- **Outputs.** Documents are generated from the record: a static HTML site first, Word files for formal distribution. They are never edited by hand.

Not in scope:
- schedules (excluded, user 2026-11-01);
- risk management (later);
- raw source documents, which stay in the project's document store and are cited by path and hash;
- a server, database or browser editor.

## 2. Principles (accepted)

1. **The record governs.** An issued document is a snapshot generated at a git tag. Comments on a document return as changes to records.
2. **Identity is permanent.** A record's ID never changes and is never reused. The file path is a function of the ID only.
3. **No silent behavior.**
   - Unreadable files, unknown references and missing required fields are errors.
   - Nothing is filled in by default when a file is read.
   - Every check result is reported.
4. **No hidden state.** The vault location is passed explicitly or discovered from the working directory. The engine never writes environment variables or global caches.
5. **One interface for people and agents.** Every command can emit JSON. Error messages name the rule, the record and a fix.
6. **Words for people.** Generated pages are written for engineers and scientists, in plain language.

## 3. The vault (accepted structure; proposed details)

A vault is a git repository with a `qingsong.toml` file at its root.

```
<vault>/
  qingsong.toml           vault configuration (§3.1)
  pyproject.toml          pins the qingsong version (uv)
  AGENTS.md               agent rules for this vault
  people.yaml             people and approvers (§3.2)
  glossary.yaml           bilingual terms and acronyms
  tree/                   product tree and WBS, one file per top-level branch (§4.1)
  quantities/             named physical quantities (§5.3)
  requirements/<SYSTEM>/<ID>.yaml
  conditions/<ID>.yaml    context facts (§5.4)
  interfaces/ issues/ decisions/ verifications/ waivers/ sources/ baselines/
  documents/<DOC>.yaml    generated-document definitions (§5.5)
  templates/              reference style for Word output
```

### 3.1 Configuration

`qingsong.toml` declares:
- **Project code:** `DEMO` in the examples.
- **Reference language** (`en`) **and second language** (`zh`), plus the fields that must exist in both (§7).
- **Ordered levels** (§4.2). In DEMO: `science`, `survey`, `system`, `element`, `subsystem`, `component`.
- **Top-level namespaces** and their level, e.g. `DEMO-SCI` = science, `DEMO-SRV` = survey, `DEMO-SYS` = system.
- **Optional paths to related repositories,** used by the external checks (§10, group G).

### 3.2 People and approval

`people.yaml` lists each person:
- an ID (`snake_case`);
- name and organisation;
- GitHub handle;
- `approver: true` for authorized members of the vault repository.

Only approvers may approve a maturity change (§9). The vault's git host enforces review: protected main branch, required review, required check. qingsong records the approval and checks that it came from an approver.

## 4. Structure

### 4.1 Nodes: product tree and WBS (accepted)

A node is one element of the project breakdown. Nodes are defined in tree files, one per top-level branch (`tree/<CODE>.yaml`), because the structure is reviewed as a whole. This is the one exception to one-record-per-file.

| Field | Meaning |
|---|---|
| `node` | short code, `[A-Z][A-Z0-9]{1,5}`; permanent; unique **within its top-level system** |
| `structural_code` | optional position code such as `IN.02.1`; may change if the tree is reorganised |
| `names` | `{en, zh}` |
| `kind` | `product` (something built: requirements are allocated here), `work` (a work package: never a requirement target) or `context` (something recorded but not specified, such as a site: carries conditions only) |
| `status` | `active`, `placeholder` (reserved, not yet worked out) or `retired` |
| `description`, `owners`, `design_stage` | optional |
| `note` | optional plain-text remark for reviewers, e.g. a correction made on import or a name to confirm |
| `children` | nested nodes |

A tree file states its parent (`parent: DEMO`). The root file has none.

**Node references.** Elsewhere, a node is written as `<SYSTEM>-<NODE>`, e.g. `INS-DET`. For a top-level system or the root, it is written as the code alone (`INS`, `DEMO`). This is the same string that prefixes requirement IDs (§6).

Short codes are unique within a top-level system, not across the whole tree. Every system's management work package can then use the same codes without a clash.

### 4.2 Levels (accepted)

Requirement levels are ordered. The vault lists them in its configuration, and each requirement states its level.

| Level | Written in terms of | Typical allocation |
|---|---|---|
| `science` | goals of the science programme | root |
| `survey` | what the data must achieve, independent of hardware: numbers of targets, depth, S/N, success rates, wavelength range, resolution, calibration accuracy | root |
| `system` | what the facility as built must achieve: collecting area, field of view, budgets, efficiency, design environment, lifetime | root |
| `element` | each top-level system's own specification | top-level system node |
| `subsystem` | each subsystem's specification | subsystem node |
| `component` | optional, when a document needs it | lower nodes |

The `survey` level is the layer between science and engineering. 4MOST introduced it (as "user requirements") after going directly from science to system requirements proved error-prone. It is where competing science cases are reconciled into one set of measurable numbers, and analysis tools verify it.

Flow-down rules (checked):
- `derives_from` points only to requirements at a higher level. Levels may be skipped.
- `science` requirements have no parent; they carry a `justification`.
- Below `science`, a requirement without a parent must cite a decision in `justified_by`. Otherwise the check raises a **TBJ** ("to be justified") issue.
- A parent's children may be allocated to different branches of the tree.

### 4.3 Namespaces (accepted)

The ID prefix of a requirement is a **namespace**:

| Namespace | Used for | Example |
|---|---|---|
| top-level namespaces from `qingsong.toml` | science, survey and system requirements | `DEMO-SCI`, `DEMO-SRV`, `DEMO-SYS` |
| `<SYSTEM>-SYS` | a top-level system's own requirements (`element` level) | `INS-SYS` |
| `<SYSTEM>-<NODE>` | requirements of a node inside a system | `INS-DET` |

A namespace records where a requirement was **first issued**. It does not change if the requirement is later reallocated.

## 5. Records

Every record is one YAML file, except nodes (§4.1). Common fields:

| Field | Meaning |
|---|---|
| `id` | permanent ID (§6) |
| `type` | record type |
| `title` | `{en, zh}` |
| `lifecycle` | `current`, `superseded` or `withdrawn`; never deleted |
| `superseded_by` | list of IDs; required when superseded |
| `aliases` | other names of this record (§6.2) |
| `history` | append-only list of changes (§8) |
| `revision` | integer, starts at 1 |
| `stamp` | hash of the whole content, written by qingsong (§8.2) |

### 5.1 Requirement

| Field | Meaning |
|---|---|
| `statement` | `{en, zh}`; one "shall"; values appear as `{slot}` placeholders |
| `values` | value slots (§5.2) |
| `rationale` | `{en, zh}` |
| `justification` / `justified_by` | for parentless requirements (§4.2) |
| `level` | §4.2 |
| `allocated_to` | exactly one node reference, of `kind: product` |
| `derives_from` | list of `{id, fingerprint}`, where the fingerprint is the parent's normative fingerprint when the link was last confirmed |
| `constrained_by` | list of `{id, fingerprint}` pointing to conditions (§5.4) |
| `sources` | list of `{source, locator}`, e.g. the section and table row of an imported document |
| `verification` | `{method, level, criteria: {en, zh}}`; method is one of `test`, `analysis`, `inspection`, `demonstration`, `review_of_design` |
| `maturity` | §9 |
| `approval` | `{by, date, ref}` for the latest maturity approval |
| `text_origin` | `en` or `zh`: the language the requirement was first written in (§7) |
| `translation` | `{source_fingerprint, status}` (§7) |
| `fingerprint` | hash of the normative content (§8.2) |

### 5.2 Value slots and quantities (accepted principle; proposed format)

Numbers live in slots, not in prose. Both languages then render the same value, and checks can compare values across requirements.

```yaml
values:
  dark_current:
    quantity: detector.dark_current
    relation: le                     # eq | le | lt | ge | gt | range | approx
    value: 3
    unit: electron / pixel / hour
    certainty: provisional           # firm | provisional | tbc | tbd
    issue: ISS-0007                  # required unless firm
    condition: {en: "at 163 K", zh: "163 K 时"}
```

Rendering:
- `eq` with a tolerance prints `100 ± 2 µm`.
- `provisional` prints in brackets, `[≤ 3 e⁻/pix/h]`.
- `tbc` appends "(TBC)".
- `tbd` prints "TBD" and needs no value.

A **quantity** (`quantities/<key>.yaml`) has:
- a dotted key;
- names `{en, zh}`, a symbol, a dimension and a canonical unit;
- an optional `kpp: true`, which marks a Key Performance Parameter and gets stricter change control;
- optional links to analysis records in other repositories.

Units are parsed with `pint`.

### 5.3 Other record types

| Type | ID pattern | Holds |
|---|---|---|
| Condition | `<NODE>-COND-NNN` | A fact about a `context` node (e.g. site temperature statistics): value slots, source, date, evidence basis (`measured`, `modelled`, `assumed`). Never a "shall". |
| Document | document number | Definition of a generated document: title, scope node(s), ordered outline of sections and requirement IDs, front matter, roles, releases. Earlier document numbers are kept as aliases. |
| Interface | `IFC-<SYSTEM>-NNN` | Numbered within the top-level system that owns the interface. Two endpoint nodes as fields (`owner_end`, `other_end`), interface requirements, agreed values. |
| Issue | `ISS-NNNN` | Open TBD, TBC, provisional value or TBJ; a question; a conflict. Owner, closure plan, due point (a date or a named event), status. |
| Decision | `DEC-NNNN` | Who decided what, when and why; affected records |
| Verification | `VER-<REQUIREMENT>-NN` | Method, level, criteria, status, evidence (§9) |
| Waiver | `WVR-NNNN` | Approved departure from a requirement: scope, reason, approver, expiry. The requirement itself is unchanged. |
| Source | `SRC-<slug>` | External document: number, version, date, file name, sha256, storage path |
| Baseline | `BL-<slug>` | A named, frozen set of records, its git tag and the review it belongs to |

### 5.4 Documents and releases (proposed)

A document record lists its sections and the requirement IDs in each, in display order. Section numbers and order belong to the document, never to requirement IDs.

A **release** is cut by `qingsong release <DOC> <version>`, which:
1. checks that no errors exist;
2. writes a release entry with the version, date, approvals, git tag `release/<DOC>/<version>` and a generated change summary against the previous release;
3. renders the Word and HTML copies.

## 6. Identity (accepted)

### 6.1 IDs

- **Requirements:** `<NAMESPACE>-REQ-<NNN>`, e.g. `INS-DET-REQ-012`.
- **Numbering:** one continuous series per namespace, starting at 001; four digits once 999 is passed. `qingsong new` allocates the next number from all existing IDs, including superseded and withdrawn ones.
- **Permanence:** an ID is never renumbered, reordered or reused. The check compares the vault with a previous git reference and reports any ID that disappeared or changed type.
- **File path:** `requirements/<SYSTEM>/<ID>.yaml`, where `<SYSTEM>` is the first segment of the ID. Other types: `<type folder>/<ID>.yaml`.

### 6.2 Aliases

An alias is any other name of a record: an earlier ID, a vendor's number for the same requirement, or a number in another project's document.

```yaml
aliases:
  - {id: REQ-007, kind: legacy, context: "DEMO-INS-DET-RD v0.1–v1.1"}
  - {id: "3.2.4", kind: vendor, context: "Vendor X compliance matrix, 2026-09"}
```

- Aliases are unique within a context.
- They are searchable, shown on the requirement's page, and can be printed as a column in generated documents.
- One old ID used for two different requirements in different versions gets an alias on each, with the version range in its context.

## 7. Languages (accepted)

- **The reference language is English.** Checks, values and approvals refer to the English text.
- **Fields required in both languages from `draft` maturity upward:** `title`, `statement`, `rationale` and `verification.criteria` (configurable in `qingsong.toml`). A `concept` requirement may exist in one language.
- **Text origin.** `text_origin` records which language a requirement was first written in. A vault may set the default per node or per document. A subsystem whose documents were originally written in Chinese, for example, defaults to `zh`.
- **Respecting a Chinese original.**
  - When `text_origin` is `zh`, the Chinese text is kept as its authors wrote it, and the English is a faithful translation.
  - Agents never regenerate origin-language text from the other language.
  - A change of meaning updates both texts. The changed origin-language text then needs `translation.status: reviewed` by a person before the requirement can be `agreed`.
- **Translation tracking.**
  - `translation.source_fingerprint` is the hash of the origin-language texts at the time the other language was written.
  - When the origin-language text changes, the translation is reported stale.
  - `translation.status` is `machine` (written by an agent) or `reviewed` (checked by a person).
  - A formal release requires reviewed translations.
- Values never appear in prose (§5.2), so both languages always show the same numbers.

## 8. Change control (accepted)

### 8.1 Change classes

Content is edited in the file. `qingsong revise <ID> --class <class> --summary "…"` then records the change: it bumps `revision`, recomputes `stamp` and `fingerprint`, and appends to `history` the date, the person, the class, the summary and, where required, a decision. An edit not followed by `revise` fails the check ("changed since stamp").

| Class | Example | Result |
|---|---|---|
| `editorial` | wording, punctuation, translation, rationale | same ID; children unaffected |
| `value` | a value, tolerance or condition; same intent | same ID; children and verifications become **suspect**; verification status returns to `planned` |
| `intent` | the requirement now asks for something different | new ID; `qingsong supersede OLD --by NEW` |
| `split` / `merge` | one requirement becomes several, or several become one | new IDs; originals superseded, pointing to all successors |
| `withdraw` | no longer needed | `qingsong withdraw ID --reason … --decision …`; the ID is retired |

Requirements for each maturity:
- `concept` and `draft` need only the history entry.
- `agreed` needs a summary that names the reason.
- `baselined` needs a decision record. Its affected-records list must include the impact list that qingsong generates: parents, children, interfaces, verifications and documents.
- A party that cannot meet a baselined requirement gets a waiver, not an edit.

### 8.2 Hashes and suspect links

- **`fingerprint`** is the SHA-256 of the canonical JSON of the normative content, shortened to 16 hexadecimal characters. Normative content means the English statement, the value slots, the level and the verification method and criteria (English).
- **`stamp`** hashes all content fields, including both languages and the rationale. It detects edits that were not recorded.
- **Suspect links.** A `derives_from` or `constrained_by` link stores the fingerprint of its target. If the target's current fingerprint differs, the link is suspect until a person or agent reviews the child and runs `qingsong confirm <child> <parent>`.

## 9. Maturity: four separate axes (accepted)

| Axis | Values | Meaning |
|---|---|---|
| **Requirement maturity** | `concept`, `draft`, `agreed`, `baselined` | how settled the requirement is |
| **Lifecycle** | `current`, `superseded`, `withdrawn` | whether it is in force; not a maturity rank |
| **Value certainty**, per slot | `firm`, `provisional`, `tbc`, `tbd` | how settled each value is; non-firm values need an issue |
| **Verification status** | `not_planned`, `planned`, `predicted`, `compliant`, `partially_compliant`, `non_compliant`, `waived` | how far evidence shows compliance |

The maturity levels:
- **`concept`:** a need is captured; wording and values may be missing.
- **`draft`:** a verifiable statement exists, in both languages; values may be non-firm.
- **`agreed`:** an approver has approved it, and every non-firm value has an issue with an owner and a due point.
- **`baselined`:** it belongs to a named baseline, and change control applies (§8.1).

Moves to `agreed` and `baselined` are recorded by `qingsong approve <ID> --to <maturity> --by <person> --ref <pull request>`. The check confirms that the person is an approver. Agents run it only on an approver's instruction.

Verification rules:
- `compliant` needs at least one evidence item that resolves: a file in the vault, a source record, or an analysis record identified by repository and commit.
- Analysis based on inputs that are only placeholders or derived from requirements gives `predicted`, never `compliant`.
- A `value` revision resets the verification status (§8.1).

Requirement maturity is deliberately named in words. Other tools may grade input data numerically (for example M0–M5), and the two scales must not be confused.

## 10. Checks (accepted principle; proposed catalogue)

`qingsong check` runs:
- in pre-commit;
- in CI, with `--against origin/main`;
- by agents after every edit.

Every rule has an ID such as `integrity.duplicate_id` and a severity (`error`, `warning`, `info`), which may depend on the record's maturity. `--json` prints a list of `{rule, severity, record, file, message, fix}` objects and exits non-zero on any error. Every rule has a test fixture that triggers it.

| Group | Rules (initial) |
|---|---|
| `integrity` | YAML and schema; ID and namespace format; duplicate IDs; file path matches ID; unresolved references; IDs removed or reused relative to `--against` |
| `structure` | one allocation, to a `product` node; level order of `derives_from`; parentless below `science` without `justified_by` (TBJ); cycles; superseded without successors; parent withdrawn; interfaces with two endpoints and an owner; node codes unique within a system; aliases unique within a context |
| `change` | unrecorded edit (stamp); suspect links; history order; baselined change without decision; approval by a non-approver; stale or unreviewed translation; verification not reset after a value change |
| `content` | exactly one "shall"; vague terms (English and Chinese lists); bare numbers in a statement (at `agreed` and above); units valid and matching the quantity's dimension; tolerance, rationale and verification present according to maturity; required bilingual fields |
| `consistency` | one quantity with conflicting values in current requirements under the same conditions; a child limit looser than its parent's; an environmental range that does not cover its parent's; an issue past its due point; TBD in a baselined requirement |
| `documents` | each current requirement on a specified node appears in exactly one document; acronyms resolve to the glossary; release blocked while errors exist |
| `external` | sources carry sha256 and a path; cited analysis records and files exist when the related repositories are configured |

## 11. Commands (proposed)

All commands accept `--vault PATH`. Without it, qingsong uses the nearest parent directory containing `qingsong.toml`. All commands accept `--json`.

| Command | Purpose | Phase |
|---|---|---|
| `qingsong init PATH` | create an empty vault | 1 |
| `qingsong check [--against REF]` | run the rules (§10) | 1 |
| `qingsong new requirement --namespace NS` | allocate an ID and write a skeleton | 1 |
| `qingsong revise ID --class C --summary S [--decision D]` | record a change (§8.1) | 1 |
| `qingsong supersede OLD --by NEW…`, `qingsong withdraw ID` | lifecycle changes | 1 |
| `qingsong approve ID --to M --by P --ref R` | record a maturity approval | 1 |
| `qingsong confirm CHILD PARENT` | clear a suspect link after review | 1 |
| `qingsong show ID`, `qingsong list [filters]`, `qingsong find TEXT` | read | 1 |
| `qingsong schema [TYPE]` | print the JSON Schema for editors and agents | 1 |
| `qingsong render html OUT`, `qingsong serve` | HTML site (§12.1) | 3 |
| `qingsong render docx DOC --release V`, `qingsong release DOC V` | Word output and releases (§12.2) | 4 |
| `qingsong baseline create NAME --review REF` | baselines | 6 |
| `qingsong import docx FILE --document DOC` | draft records from a Word requirement table, with source locators | 2 |
| `qingsong export json|reqif` | exchange | later |

## 12. Outputs (accepted principle; proposed design)

### 12.1 HTML

A static site that works offline from a folder: no server, all JavaScript vendored. Every record has a stable address, e.g. `r/INS-DET-REQ-012.html`.

Views:
- **Home:** status counts, open issues, recent changes, check status.
- **Product tree:** owners, design stage, documents, counts; N² interface matrix.
- **Document:** reads like the formal document, with an English / Chinese / both switch, non-firm values highlighted, and a view per release.
- **Requirement:** statement and values, rationale, flow-down up and down, interfaces, verification and evidence, issues, decisions, revision timeline with differences, aliases, and the documents it appears in.
- **Trace:** an interactive graph filtered by link type.
- **Registers:** open values, issues, decisions, waivers, the verification matrix and conditions.
- **Changes:** between any two baselines or releases.
- **Review package:** for a node's design review.
- **Search** in both languages.
- **Check report.**

Pages follow a light, print-friendly style. They are written for scientists and engineers.

GitHub Pages is not used for private vaults, because Pages sites are public unless the host offers private publishing. The site is distributed as a CI artifact or opened locally with `qingsong serve`.

### 12.2 Word

`qingsong render docx` reproduces the project's document layout from a reference style file in `templates/`:
- cover, change record, responsibilities;
- acronyms from the glossary;
- reference documents;
- bilingual requirement tables, with an optional alias column.

A release may carry tracked changes against the previous release, written per requirement.

The generated package must open in Word without repair: no ZIP directory entries, integer table widths, fonts covering Chinese.

### 12.3 Exchange

- **JSON:** an export of all records.
- **ReqIF:** later, for partners using DOORS or Polarion. It also keeps the data portable to other requirement tools.

## 13. Engine (accepted)

The engine is a small core of its own. Doorstop is not used: its links are untyped, it has no validation interface and no Word output. Its useful ideas, one file per item and fingerprinted links, are reimplemented here.

```
src/qingsong/
  schema/        pydantic models; JSON Schema generation
  vault.py       discovery, load and save (ruamel.yaml round trip, preserving comments and order)
  ids.py         namespaces, allocation, aliases
  hashing.py     fingerprint and stamp
  operations.py  new, revise, supersede, withdraw, approve, confirm, release
  checks/        rule registry and rules
  render/        html/ (Jinja2), docx/ (python-docx)
  importers/     Word requirement tables
  cli.py         Typer
```

- **Python** 3.11 to 3.13. **Build** with `uv_build`. **Dependencies** are managed with `uv` only.
- **Runtime dependencies,** added as the phases need them: pydantic, ruamel.yaml, typer, jinja2, pint, python-docx.
- **Development dependencies:** pytest, ruff, pre-commit.
- **Ruff** is the single source of truth for lint and format. Names are `snake_case` (pep8-naming rules on).
- **Tests** use synthetic vaults built in temporary directories only. They never read or write a real vault and never set environment variables globally.
  - Every check rule has a fixture that must trigger it.
  - The defect classes found in the 2026-11-01 review of the earlier version are regression tests: duplicate IDs, unreadable files, dangling links, deleted files and silent defaults.
- **CI** (GitHub Actions) runs `uv sync --locked`, `ruff check`, `ruff format --check` and `pytest`. Failures are never masked.
- **Performance.** Load and check time is measured on a synthetic vault of 10,000 records in Phase 1, and the measurement is recorded here. A cache is introduced only if the measurement shows a need.

## 14. Development sequence

| Phase | Content | Acceptance |
|---|---|---|
| 0 | This specification; reset of the package; tooling and CI | Specification accepted; CI green on the empty package |
| 1 | Schemas, vault I/O, IDs and aliases, hashing, operations, check groups `integrity`, `structure`, `change` and `content`, JSON output; synthetic demo vault | Every rule's fixture fails as intended; the clean demo passes; review regressions caught; benchmark recorded |
| 2 | First real vault: tree, people, glossary, quantities; import of one requirement document | Every requirement of the source document accounted for; check clean apart from tracked issues |
| 3 | HTML site | Usable by the Project Scientist instead of the Word copy; works offline |
| 4 | Word output and releases | Opens without repair; text matches the source apart from intended changes |
| 5 | Upper levels, conditions, interfaces, `consistency` and `documents` checks | Conflicts surface as issues |
| 6 | Verification, waivers, baselines, metrics | One complete verification matrix with resolvable evidence |

## 15. Earlier version

Version 0.1 (February 2026) is tagged `legacy-0.1`. It stored items in a Doorstop-like folder tree and had a Streamlit editor. The 2026-11-01 review found it unsound, so it was rebuilt rather than repaired. Its lessons are in `docs/lessons.md`.

## 16. Accepted decisions

| Date | Decision |
|---|---|
| 2026-11-01 | Rebuild rather than repair. qingsong is the source of documents, not a registry of Word files. |
| 2026-11-01 | No Doorstop; own small core (decision delegated to the assistant). |
| 2026-11-01 | IDs `<NAMESPACE>-REQ-NNN`, permanent, one continuous series per namespace; other names kept as aliases, including vendor numbers. |
| 2026-11-01 | Six levels: science, survey, system, element, subsystem, component. The `survey` name is accepted. |
| 2026-11-01 | Context nodes (e.g. a site) carry conditions, never requirements. |
| 2026-11-01 | Authorized members of the vault repository approve maturity changes; authorized collaborators propose changes by pull request. |
| 2026-11-01 | English is the reference language. Title, statement, rationale and verification criteria also exist in Chinese. Text originally written in Chinese is respected (§7). |
| 2026-11-01 | Schedules are out of scope permanently; risks later. |
| 2026-11-01 | HTML is first-class; Word for formal distribution; HTML distributed as an artifact or served locally. |
| 2026-11-01 | Record content lives in a private vault repository; this public repository holds only the engine and synthetic examples. |
