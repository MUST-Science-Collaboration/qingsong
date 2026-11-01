# qingsong: specification

Version 0.2 (rebuild), 2026-11-01, revised after the first independent review.

This document is the architecture source of truth for the qingsong engine.
- **Accepted:** decisions of the Project Scientist, dated in §16.
- **Proposed:** recommendations that implementation may refine. Changes are recorded here.

The first project to use qingsong is the MUST telescope. Its record repository is private. This public repository never holds MUST content, so the examples here use a fictional project called DEMO.

## 1. Purpose and scope (accepted)

qingsong keeps a project's requirements as the **authoritative engineering record** and generates every human-readable form of it.

- **The record.** Each requirement, interface, decision and related item is a small structured text file in a git repository, the **vault**.
- **Who edits.** AI agents do most of the editing. Authorized people review and approve through pull requests.
- **What is generated.** Documents, mainly a static HTML site and Word files for formal distribution, are produced from the record and never edited by hand.

Out of scope:
- schedules (user, 2026-11-01);
- risk management (later);
- raw source documents, which stay in the project's document store and are cited by path and hash;
- a server, a database or a browser editor.

## 2. Principles (accepted)

1. **The record governs.** An issued document is a snapshot generated at a git tag. Comments on a document return as changes to records.
2. **Identity is permanent** once a record reaches the main branch. An ID never changes and is never reused. The file path is a function of the ID only.
3. **No silent behaviour.**
   - Unreadable files, unknown references and missing required fields are errors.
   - Nothing is filled in by default when a file is read.
   - Every check result is reported.
4. **No hidden state.** The vault location is passed explicitly or discovered from the working directory. The engine never writes environment variables or global caches.
5. **One interface for people and agents.** Every command can emit JSON. Error messages name the rule, the record and a fix.
6. **Words for people.** Generated pages are written for engineers and scientists in plain language.

## 3. The vault (accepted structure; proposed details)

A vault is a git repository with a `qingsong.toml` file at its root.

```
<vault>/
  qingsong.toml           configuration (§3.1)
  pyproject.toml          pins the qingsong version (uv)
  AGENTS.md               agent rules for this vault
  people.yaml             people and approvers (§3.2)
  glossary.yaml           bilingual terms and acronyms
  tree/                   product tree and WBS, one file per top-level branch (§4.1)
  quantities/<key>.yaml   named physical quantities (§5.2)
  requirements/<SYSTEM>/<ID>.yaml
  conditions/<ID>.yaml    facts about context nodes (§5.3)
  interfaces/ issues/ decisions/ verifications/ waivers/ sources/ baselines/
  documents/<DOC>.yaml    generated-document definitions (§5.5)
  figures/<SYSTEM>/      figure records and image files (§5.4)
  templates/              reference style for Word output
```

### 3.1 Configuration

| Key | Meaning |
|---|---|
| `[project] code`, `names` | project code (`DEMO`); `{en, zh}` names |
| `[languages] reference`, `second` | `en`, `zh` |
| `[languages] bilingual_fields` | fields required in both languages from `draft` maturity upward. Default: `title`, `statement`, `rationale`, `verification.criteria` |
| `[languages] default_text_origin` | language in which requirements are normally first written (`en`); nodes and documents may override it (§7) |
| `[[levels]] name`, `names` | ordered list of requirement levels, highest first (§4.2) |
| `[top_namespaces]` | namespace → level for requirements allocated to the root, e.g. `DEMO-SCI = "science"` |
| `[related] <name> = <path>` | optional local paths of related repositories, used by the `external` checks |

### 3.2 People and approval

`people.yaml` lists, for each person:
- an ID in `snake_case`;
- name and organisation;
- GitHub handle;
- the languages the person reads (`[en, zh]`);
- `approver: true` for authorized members of the vault repository.

Approvals are enforced on two layers:
- **The git host** protects the main branch, requires a review and requires the check to pass.
- **qingsong** records each approval and checks that it came from an approver.

Proposed hardening:
- `people.yaml` gets a code-owner rule, so changes to the approver list need an existing approver.
- A CI step compares recorded approvals with the pull-request reviews (Phase 6).

## 4. Structure

### 4.1 Nodes: product tree and WBS (accepted)

A node is one element of the project breakdown. Nodes are defined in tree files, one per top-level branch (`tree/<CODE>.yaml`), because the structure is reviewed as a whole. This is the one exception to one-record-per-file.

| Field | Meaning |
|---|---|
| `node` | Short code, matching `[A-Z][A-Z0-9]{1,5}`. Permanent. Unique within its top-level system. Top-level codes are unique among themselves. Reserved words are not allowed: `REQ`, `SYS`, `COND`, `IFC`, `ISS`, `DEC`, `WVR`, `VER`, `SRC`, `BL`, `RD`, `ICD`, and the suffixes of the top-level namespaces. |
| `structural_code` | optional position code, e.g. `IN.02.1`; may change |
| `names` | `{en, zh}` |
| `kind` | `product`: something built, so requirements are allocated here. `work`: a work package, never a requirement target. `context`: something recorded but not specified, such as a site; it carries conditions only. |
| `status` | `active`, `placeholder` (reserved, not yet worked out) or `retired` |
| `text_origin` | optional default for requirements of this node and its descendants (§7) |
| `description`, `owners`, `design_stage` | optional |
| `note` | optional plain-text remark for reviewers, e.g. a correction made on import or a name to confirm |
| `children` | nested nodes |

A tree file states its parent, as `parent: DEMO`. The root file has no parent.

**Node references.** Elsewhere, a node is written `<SYSTEM>-<NODE>`, e.g. `INS-DET`. For the root or a top-level system, the code alone is used (`DEMO`, `INS`). The same string prefixes requirement IDs (§4.3).

Nodes follow the same permanence rule as records. A node is never removed, renamed or moved to another top-level system. Instead it is retired, and a new node is created.

### 4.2 Levels (accepted)

Requirement levels are ordered. The vault lists them in its configuration, and each requirement states its level.

| Level | Written in terms of | Typical allocation |
|---|---|---|
| `science` | goals of the science programme | root |
| `survey` | what the data must achieve independent of hardware: numbers of targets, depth, S/N, success rates, wavelength range, resolution, calibration accuracy | root |
| `system` | what the facility as built must achieve: collecting area, field of view, budgets, efficiency, design environment, lifetime | root |
| `element` | each top-level system's own specification | top-level system |
| `subsystem` | each subsystem's specification | node inside a system |
| `component` | optional, when a document needs it | lower node |

The `survey` level is the layer between science and engineering. 4MOST introduced it as "user requirements", after going directly from science to system requirements proved error-prone. Competing science cases are reconciled there into one set of measurable numbers, and analysis tools verify it.

Flow-down rules (checked):
- **Direction.** `derives_from` points only to requirements at a higher level. Levels may be skipped.
- **Siblings.** A budget shared between siblings is expressed by each share deriving from the higher-level budget requirement, never by sibling-to-sibling derivation.
- **Science.** `science` requirements have no parent. They carry a `justification`.
- **Parentless requirements below science.** They must cite a decision in `justified_by`. Otherwise the check raises a **TBJ** ("to be justified") issue.
- **Allocation.** The children of one parent may be allocated to different branches of the tree.

### 4.3 Namespaces (accepted)

The ID prefix of a requirement is its **namespace**. The namespace records where the requirement was first issued. It does not change if the requirement is later reallocated.

| Namespace | Used for | Expected level | Example |
|---|---|---|---|
| keys of `[top_namespaces]` | requirements allocated to the root | as configured | `DEMO-SCI`, `DEMO-SRV`, `DEMO-SYS` |
| `<SYSTEM>-SYS` | a top-level system's own requirements | `element` | `INS-SYS` |
| `<SYSTEM>-<NODE>` | requirements of a node inside a system | `subsystem` or `component` | `INS-DET` |

A requirement whose level differs from its namespace's expected level produces a warning (`structure.level_namespace`).

## 5. Records

Every record is one YAML file, apart from nodes (§4.1).

**Fields common to all record types:**

| Field | Meaning |
|---|---|
| `id`, `type` | permanent ID (§6) and record type |
| `title` | `{en, zh}` |
| `lifecycle` | `current`, `superseded` or `withdrawn`; never deleted |
| `superseded_by` | list of IDs; required when superseded |
| `aliases` | other names of this record (§6.2) |
| `revision` | integer from 1; increases with every recorded change |
| `normative_revision` | integer from 1; increases only with changes of meaning (§8.1) |
| `normative_hash` | hash of the fields whose change is never editorial (values, level, verification method), written by qingsong; `revise` refuses `editorial` when it differs |
| `history` | append-only list of change events (§8.1) |
| `stamp` | hash of every field except `stamp` and `history`, written by qingsong (§8.2) |

**Normative content** is what a change of meaning alters. It differs by type:

| Type | Normative content |
|---|---|
| Requirement | statement, values, level, verification method and criteria |
| Condition | values, conditions of measurement |
| Interface | endpoints, agreed values |
| Quantity | dimension, canonical unit |
| Others | not applicable; they have `revision` only |

### 5.1 Requirement

| Field | Meaning |
|---|---|
| `statement` | `{en, zh}`. Exactly one "shall". Values appear as `{slot}` placeholders. |
| `values` | value slots (§5.2) |
| `rationale` | `{en, zh}` |
| `justification` / `justified_by` | for parentless requirements (§4.2) |
| `level` | §4.2 |
| `allocated_to` | exactly one node reference, of `kind: product` |
| `interface` | optional interface ID, when this requirement belongs to an interface (§5.3) |
| `derives_from` | list of `{id, normative_revision}`: the parent's normative revision when the link was last confirmed |
| `constrained_by` | list of `{id, normative_revision}` pointing to conditions |
| `sources` | list of `{source, locator}`, e.g. the section and table row of an imported document |
| `verification` | `{method, level, criteria: {en, zh}}`. The method is one of `test`, `analysis`, `inspection`, `demonstration`, `review_of_design`, and has bilingual labels from the vocabulary. |
| `maturity` | §9 |
| `approval` | `{by, date, ref, normative_revision}`: the latest maturity approval, and the content it approved |
| `text_origin` | `en` or `zh` (§7) |
| `translation` | per-field tracking (§7) |
| `variants` | (proposed) other versions of this requirement stated elsewhere, e.g. a vendor's wording or value in its specification: `{source, label, statement, values, relation}`, where `relation` is `vendor_stated`, `proposed` or `rejected`. Shown for comparison; excluded from consistency checks. |

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

How each certainty is rendered:
- `eq` with a tolerance: `100 ± 2 µm`.
- `provisional`: in brackets, `[≤ 3 e⁻/pix/h]`.
- `tbc`: the value followed by "(TBC)".
- `tbd`: "TBD", with no value needed.

A **quantity** (`quantities/<key>.yaml`) has:
- a dotted key;
- names `{en, zh}`, a symbol, a dimension and a canonical unit;
- optionally `kpp: true`, which marks a Key Performance Parameter and gets stricter change control;
- optional links to analysis records in other repositories.

Units are parsed with `pint`.

### 5.3 Other record types

| Type | ID pattern | Holds |
|---|---|---|
| Condition | `<NODEREF>-COND-NNN` | A fact about a `context` node (e.g. site temperature statistics): value slots, source, date, evidence basis (`measured`, `modelled`, `assumed`). Never a "shall". |
| Interface | `IFC-<SYSTEM>-NNN` | Numbered within the top-level system that owns the interface. Endpoints `owner_end` and `other_end` (node references) and agreed values. Its requirements are ordinary requirements that name it in `interface`. |
| Issue | `ISS-NNNN` | Open TBD, TBC, provisional value or TBJ; a question; a conflict. Owner, closure plan, due point (a date or a named event), status. |
| Decision | `DEC-NNNN` | Who decided what, when and why; affected records |
| Verification | `VER-<REQUIREMENT>-NN` | Method, level, criteria, status, evidence (§9), and the requirement's `normative_revision` that was verified |
| Waiver | `WVR-NNNN` | Approved departure: requirement and its `normative_revision`, scope, reason, approver, expiry. The requirement itself is unchanged. |
| Source | `SRC-<slug>` | External document: number, version, date, file name, sha256, storage path |
| Baseline | `BL-<slug>` | A named, frozen set of records, its git tag and the review it belongs to |
| Document | document number | §5.5 |
| Figure | `<NAMESPACE>-FIG-NNN` | §5.4 |

ID syntax (checked):

| Type | Regular expression |
|---|---|
| Requirement | `^[A-Z][A-Z0-9]*(-[A-Z][A-Z0-9]*)+-REQ-\d{3,}$` |
| Condition | `^[A-Z][A-Z0-9]*(-[A-Z][A-Z0-9]*)*-COND-\d{3,}$` |
| Interface | `^IFC-[A-Z][A-Z0-9]*-\d{3,}$` |
| Issue, decision, waiver | `^(ISS\|DEC\|WVR)-\d{4,}$` |
| Verification | `^VER-<requirement ID>-\d{2,}$` |
| Source, baseline | `^(SRC\|BL)-[A-Za-z0-9][A-Za-z0-9._-]*$` |
| Document | `^[A-Z][A-Z0-9]*(-[A-Za-z0-9.]+)+$` |

Numbers sort numerically, not lexically.

### 5.4 Text, figures and document content (proposed; from the first pilot document, 2026-11-01)

**Text format.** Every prose field (`statement`, `rationale`, `notes`, `suggestions`, criteria, captions, document text) is Markdown (CommonMark) per language, with the following additions:
- **Sub- and superscript:** `~x~` and `^x^`, as in pandoc.
- **Inline mathematics:** `$…$` in LaTeX.
- **Cross-references:** `[[ID]]`. A requirement ID renders as the ID. A figure ID renders as "Figure 3.2" / "图3.2", numbered by the document being rendered (outside a document, as the figure's ID). `[[DOC#key]]` renders as the number of that section, e.g. "Section 4.1".

Cross-references are checked like any other reference. Numbers written by hand ("Figure 3.2", "Section 4") are avoided, because numbering belongs to documents.

**Requirement parts.** Besides `statement`, `rationale` and `verification`, a requirement may carry `notes` and `suggestions`, both `{en, zh}` and informative. Renderers show them in a fixed order: requirement, rationale, notes, suggestions, verification.

**Figure.** Figures are records with ID `<NAMESPACE>-FIG-NNN` and file `figures/<SYSTEM>/<ID>.yaml`, next to the image files (`<ID>.png`, optionally `.svg` and `.pdf`). A figure record holds:
- the caption `{en, zh}` and the alt text;
- the image files with their sha256;
- provenance: the generating script and its repository, version or commit, data, and date.

Images are shared by both languages; captions are translated. Image files are part of the stamp through their hashes, so a changed image is a recorded change.

**Glossary.** `glossary.yaml` lists:
- acronyms and terms, with expansions `{en, zh}`;
- optional definitions `{en, zh}`;
- symbols, with meanings `{en, zh}`.

Documents select from it.

**Document outline.** An ordered list of blocks:

| Block | Holds |
|---|---|
| `section` | key, title `{en, zh}`, nested blocks |
| `text` | `{en, zh}` Markdown |
| `requirement` | a requirement ID |
| `figure` | a figure ID |
| `table` | header and rows of bilingual cells, optional caption |
| `definitions` | glossary terms or symbols to list |

Front matter holds:
- the title `{en, zh}`;
- roles, as `{role {en, zh}, person}` for authors, checkers and approvers;
- reference documents, as source IDs;
- the bibliography;
- the change record of releases made before qingsong.

### 5.5 Documents and releases (proposed)

A document record holds:
- its number and title;
- its **scope**, a list of namespaces;
- an ordered outline of sections and the requirement IDs in each;
- front matter;
- roles (authors, checkers, approvers);
- releases.

Section numbers and order belong to the document, never to requirement IDs. Earlier document numbers are kept as aliases.

A **release** is cut by `qingsong release <DOC> <version>`. It:
1. checks that no errors exist;
2. writes a release entry: version, date, approvals and git tag `release/<DOC>/<version>`;
3. renders the Word and HTML copies.

The **change summary** compares the document's requirements at the previous release tag with the current ones:
- added and removed IDs;
- revised IDs, with the classes and summaries of the history entries in between;
- superseded and withdrawn IDs, with their successors.

## 6. Identity (accepted)

### 6.1 IDs

- **Format.** Requirements are `<NAMESPACE>-REQ-<NNN>`, e.g. `INS-DET-REQ-012`. There is one continuous series per namespace, starting at 001.
- **Allocation.** `qingsong new` allocates above the highest number in the working tree **and** on the main branch, counting superseded and withdrawn IDs.
- **When permanence starts.** An ID becomes permanent once its record reaches the main branch. Two branches may still collide before merging. `qingsong renumber --unmerged OLD NEW` moves a record that is not yet on main to a free number and rewrites references to it.
- **What the check enforces.** With `--against REF` (normally `origin/main`), the check reads REF through the `git` command line and reports:
  - an ID present at REF and now missing, or now of a different type;
  - a node removed or moved;
  - a `history` whose earlier entries were altered;
  - a lifecycle that moved backwards.
- **File path.** `requirements/<SYSTEM>/<ID>.yaml`, where `<SYSTEM>` is the first segment of the ID. Other types use `<type folder>/<ID>.yaml`.

### 6.2 Aliases

An alias is another name of the same record: an earlier ID in our own documents, or a vendor's number for the same requirement.

```yaml
aliases:
  - {id: REQ-007, kind: legacy, document: DEMO-INS-DET-RD, from_version: "0.1", to_version: "1.1"}
  - {id: "3.2.4", kind: vendor, document: "Vendor X compliance matrix", from_version: "2026-09"}
```

Checks:
- **No overlap.** Aliases sharing the same `kind`, `document` and `id` must not have overlapping version ranges. One old number used for two different requirements in different versions therefore gets an alias on each, with its own range.
- **No collision with an ID.** An alias may not equal any record's ID.

Aliases are searchable, shown on the requirement's page, and can be printed as a column in generated documents. A vendor's different *wording or value* is a variant (§5.1), not an alias.

## 7. Languages (accepted)

- **English is the reference language.** Checks, values and approvals refer to the English text.
- **Required Chinese.** From `draft` maturity upward, the fields in `bilingual_fields` must exist in both languages. These are the title, statement, rationale and verification criteria. The verification method uses bilingual vocabulary labels. A `concept` requirement may exist in one language.
- **Text origin.** `text_origin` records the language a requirement was first written in. The default comes from the document, then the node or its nearest ancestor, then the configuration.
- **Respecting a Chinese original.** When `text_origin` is `zh`:
  - the Chinese text is kept as its authors wrote it, and the English is a faithful translation;
  - agents never regenerate the origin-language text from the other language;
  - a change of meaning updates both texts, and the origin-language text must be reviewed by a person who reads it before the requirement can be `agreed`.
- **Translation tracking, per field.** For each bilingual field, `translation.<field>` holds:
  - `source_hash`: the hash of the origin-language text when the other language was written;
  - `status`: `machine` (written by an agent) or `reviewed` (checked by a person);
  - `by` and `date`.

  Editing the origin-language text makes that field's translation stale, and its status returns to `machine`. A formal release requires `reviewed` translations, by a person who reads both languages.
- **Values never appear in prose** (§5.2), so both languages always show the same numbers.

## 8. Change control (accepted)

### 8.1 Change classes

Content is edited in the file. `qingsong revise <ID> --class <class> --summary "…"` then records the change:
- it bumps `revision`, and `normative_revision` when the class changes meaning;
- it rewrites `stamp`;
- it appends a history event with the date, the person, the class, the summary and, where required, a decision.

`revise` compares the file with its version on the main branch. It refuses `editorial` when values, the level or the verification method changed.

| Class | Example | `normative_revision` | Effect |
|---|---|---|---|
| `editorial` | wording, punctuation, translation, rationale | unchanged | children unaffected |
| `value` | value, tolerance, condition or criteria changed; same intent | +1 | children, verifications and waivers become stale; the approval becomes stale |
| `reallocate` | `allocated_to` changed | unchanged | documents affected; the ID is unchanged |
| `intent` | the requirement asks for something different | — | new ID; `qingsong supersede OLD --by NEW` |
| `split` / `merge` | one becomes several, or several become one | — | new IDs; originals superseded and pointing to all successors |
| `withdraw` | no longer needed | — | `qingsong withdraw ID --reason … --decision …`; the ID is retired |

**Other events.** `approve`, `confirm` and lifecycle changes also append history events and rewrite the stamp. A hand edit of any field, including `maturity`, without a recorded event fails the check as "changed since stamp".

**Requirements on the change, by maturity:**
- `concept` and `draft`: the history event only.
- `agreed`: a summary that states the reason.
- `baselined`: a decision record whose affected records include the impact list qingsong generates (parents, children, interfaces, verifications, waivers, documents).

A party that cannot meet a baselined requirement gets a waiver, not an edit.

### 8.2 Stamps and suspect links

- **`stamp`** is the SHA-256 of the canonical JSON of all fields except `stamp` and `history`, shortened to 16 hexadecimal characters.
- **Suspect links.** A `derives_from` or `constrained_by` link stores the target's `normative_revision`. If the target's current normative revision is higher, the link is suspect until someone reviews the child and runs `qingsong confirm <child> <parent>`, which records who confirmed it and when.
- **Superseded targets.** A link to a superseded record must be re-pointed to a successor.
- **Verifications and waivers** store the normative revision they apply to and become stale the same way.

## 9. Maturity: four separate axes (accepted)

This follows a principle established in the companion simulation project: describe a record on separate axes rather than one grade, and do not treat superseded or withdrawn as a rank. In that project, how a value was obtained (evidence basis) and how far the hardware has progressed are graded separately.

Here:
- evidence basis applies to **conditions** and to **verification evidence**;
- the hardware-maturity scale of analysis inputs decides whether verification by analysis counts as `predicted` or `compliant`.

| Axis | Values | Meaning |
|---|---|---|
| **Requirement maturity** | `concept`, `draft`, `agreed`, `baselined` | how settled the requirement is |
| **Lifecycle** | `current`, `superseded`, `withdrawn` | whether it is in force; not a maturity rank |
| **Value certainty** (per slot) | `firm`, `provisional`, `tbc`, `tbd` | how settled each value is; non-firm values need an issue |
| **Verification status** | `not_planned`, `planned`, `predicted`, `compliant`, `partially_compliant`, `non_compliant`, `waived` | how far evidence shows compliance |

The maturity levels:
- **`concept`:** a need is captured; wording and values may be missing.
- **`draft`:** a verifiable statement exists in both languages; values may be non-firm.
- **`agreed`:** an approver approved this normative revision, and every non-firm value has an issue with an owner and a due point.
- **`baselined`:** the requirement belongs to a named baseline, and change control applies.

Transitions:

| From | To | How |
|---|---|---|
| `concept` | `draft` | `revise`, when the draft criteria are met |
| `draft` | `agreed` | `qingsong approve ID --to agreed --by P --ref R`; P must be an approver |
| `agreed` | `baselined` | baseline creation (Phase 6); before then, `baselined` is not used |
| `agreed` / `baselined` | `draft` | `approve --to draft` (reopen), by an approver |

A `value` revision of an `agreed` or `baselined` requirement leaves its maturity in place but makes the approval stale (`change.approval_stale`) until it is approved again. Agents run `approve` only on an approver's instruction.

**Verification:**
- `compliant` needs at least one evidence item that resolves: a file in the vault, a source record, or an analysis record identified by repository and commit.
- Analysis whose inputs are placeholders or derived from requirements yields `predicted`, never `compliant`.
- Requirement maturity is named in words, so it is never confused with numeric hardware-maturity scales.

## 10. Checks (accepted principle; proposed catalogue)

`qingsong check` runs in pre-commit, in CI (with `--against origin/main`), and by agents after every edit.

- Every rule has an ID such as `integrity.duplicate_id` and a severity (`error`, `warning` or `info`), which may depend on the record's maturity.
- `--json` prints a list of `{rule, severity, record, file, message, fix}` objects, and the command exits non-zero on any error.
- Every rule has a test fixture that triggers it.

| Group | Rules (initial) |
|---|---|
| `integrity` | YAML and schema; ID syntax (§5.3); duplicate IDs; file path matches ID; unresolved references; against REF: IDs removed or retyped, nodes removed or moved, history rewritten, lifecycle reversed |
| `structure` | One allocation, to a `product` node. Level order of `derives_from`. Level against namespace. Parentless below `science` without `justified_by` (TBJ). Cycles. Superseded without successors. Link to a withdrawn or superseded target. Interfaces with two endpoints. Node codes unique within a system and not reserved. Alias overlap or collision. |
| `change` | Unrecorded change (stamp). Suspect links. Stale approval, verification or waiver. Expired waiver. Baselined change without decision. Approval by a non-approver. Stale or unreviewed translation. |
| `content` | Exactly one "shall". Vague terms (English and Chinese lists). Bare numbers in a statement (at `agreed` and above). Units valid and matching the quantity's dimension. Tolerance, rationale and verification present according to maturity. Required bilingual fields. |
| `consistency` | One quantity with conflicting values in current requirements under the same conditions. A child limit looser than its parent's. An environmental range not covering its parent's. An issue past its due point. TBD in a baselined requirement. |
| `documents` | Each current requirement in a namespace that some document scopes appears in exactly one document's outline. Acronyms resolve to the glossary. A release is blocked while errors exist. |
| `external` | Sources carry sha256 and a path. Cited analysis records and files exist when the related repositories are configured. |

## 11. Commands (proposed)

All commands accept `--vault PATH`. Without it, qingsong uses the nearest parent directory containing `qingsong.toml`. All commands accept `--json`.

| Command | Purpose | Phase |
|---|---|---|
| `qingsong init PATH` | create an empty vault | 1 |
| `qingsong check [--against REF]` | run the rules (§10) | 1 |
| `qingsong new <type> --namespace NS` | allocate an ID and write a skeleton | 1 |
| `qingsong revise ID --class C --summary S [--decision D]` | record a change (§8.1) | 1 |
| `qingsong adopt FILE --summary S` | take a hand-written record file in: adds revision, history and stamp | 1 |
| `qingsong supersede OLD --with NEW…`, `qingsong withdraw ID --reason R` | lifecycle changes | 1 |
| `qingsong rules` | list the check rules | 1 |
| `qingsong approve ID --to M --by P --ref R` | record a maturity change | 1 |
| `qingsong confirm CHILD PARENT` | clear a suspect link after review | 1 |
| `qingsong renumber --unmerged OLD NEW` | move a record not yet on main to a free number | 1 |
| `qingsong show ID`, `qingsong list [filters]`, `qingsong find TEXT` | read | 1 |
| `qingsong schema [TYPE]` | print the JSON Schema for editors and agents | 1 |
| `qingsong import docx FILE --document DOC` | draft records from a Word requirement table, with source locators | 2 |
| `qingsong render html OUT`, `qingsong serve` | HTML site (§12.1) | 3 |
| `qingsong render docx DOC --release V`, `qingsong release DOC V` | Word output and releases (§12.2) | 4 |
| `qingsong baseline create NAME --review REF` | baselines | 6 |
| `qingsong export json`, `qingsong export reqif` | exchange | later |

## 12. Outputs (accepted principle; proposed design)

### 12.1 HTML

A static site that works offline from a folder: no server, all JavaScript vendored. Every record has a stable address, e.g. `r/INS-DET-REQ-012.html`.

Views:
- **Home:** status counts, open issues, recent changes, check status.
- **Product tree:** owners, design stage, documents, counts, and an N² interface matrix.
- **Document:** reads like the formal document, with an English / Chinese / both switch, non-firm values highlighted, and a view per release.
- **Requirement:** statement and values, rationale, flow-down up and down, interfaces, verification and evidence, issues, decisions, revision timeline with differences, aliases and variants, and the documents it appears in.
- **Trace:** an interactive graph filtered by link type.
- **Registers:** open values, issues, decisions, waivers, verification matrix, conditions.
- **Changes:** between any two baselines or releases.
- **Review package:** for a node's design review.
- **Search:** in both languages.
- **Check report.**

Pages follow a light, print-friendly style written for scientists and engineers.

GitHub Pages is not used for private vaults: its sites are public unless the host offers private publishing. The site is distributed as a CI artifact, or opened locally with `qingsong serve`.

### 12.2 Word

`qingsong render docx` reproduces the project's document layout from a reference style file in `templates/`:
- cover, change record, responsibilities;
- acronyms from the glossary;
- reference documents;
- bilingual requirement tables, with an optional alias column.

A release may carry tracked changes against the previous release, written per requirement. The package must open in Word without repair: no ZIP directory entries, integer table widths, fonts covering Chinese.

### 12.3 Exchange

- JSON export of all records.
- ReqIF later, for partners using DOORS or Polarion. This also keeps the data portable to other requirement tools.

## 13. Engine (accepted)

The engine is a small core of its own. Doorstop is not used: it has untyped links, no validation interface and no Word output. Its useful ideas, one file per item and links that detect parent changes, are reimplemented here.

```
src/qingsong/
  schema/        pydantic models; JSON Schema generation
  vault.py       discovery, load and save (ruamel.yaml round trip, preserving comments and order)
  ids.py         namespaces, allocation, aliases
  hashing.py     stamps
  operations.py  new, revise, supersede, withdraw, approve, confirm, renumber, release
  checks/        rule registry and rules
  render/        html/ (Jinja2), docx/ (python-docx)
  importers/     Word requirement tables
  cli.py         Typer
```

- **Python and tooling.** Python 3.11–3.14; build with `uv_build`; dependencies through `uv` only.
- **Runtime dependencies,** added as the phases need them: pydantic, ruamel.yaml, typer, jinja2, pint, python-docx.
- **Development dependencies:** pytest, ruff, pre-commit. Ruff is the single source of truth for lint and format, with pep8-naming rules on.
- **Tests** build synthetic vaults in temporary directories only. They never read or write a real vault and never set environment variables globally.
  - Every check rule has a fixture that must trigger it.
  - The defect classes found in the 2026-11-01 review of the earlier version are regression tests: duplicate IDs, unreadable files, dangling links, deleted files and silent defaults.
- **CI** (GitHub Actions) runs `uv sync --locked`, `ruff check`, `ruff format --check` and `pytest`. Failures are never masked.
- **Performance.** Load and check time is measured on a synthetic vault of 10,000 records in Phase 1, and the measurement is recorded here. A cache is introduced only if the measurement shows a need.
  - Measured 2026-11-02 (`tools/benchmark.py`, Apple silicon, Python 3.13): loading 10,000 requirements takes 4.9 s with the C YAML parser (19.9 s with the pure-Python parser), and all checks take 3.6 s. 500 records: about 0.5 s in total. No cache is needed at MUST's expected size (hundreds to a few thousand records).
- **Writing YAML by hand.** A text that starts with `[` or `{` must be quoted, or YAML reads it as a list or a mapping: `zh: "[[ID]]的…"`. `adopt` reports this case explicitly.

## 14. Development sequence

| Phase | Content | Acceptance |
|---|---|---|
| 0 | This specification; reset of the package; tooling and CI | Specification accepted; CI green on the empty package |
| 1 | Schemas, vault I/O, IDs and aliases, stamps, operations, check groups `integrity`, `structure`, `change` and `content`, JSON output; synthetic demo vault | Every rule's fixture fails as intended; the clean demo passes; review regressions caught; benchmark recorded |
| 2 | First real vault: tree, people, glossary, quantities; import of one requirement document | Every requirement of the source accounted for; check clean apart from tracked issues |
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
| 2026-11-01 | IDs `<NAMESPACE>-REQ-NNN`, permanent, one continuous series per namespace; other numbers kept as aliases, including vendor numbers. |
| 2026-11-01 | Six levels: science, survey, system, element, subsystem, component. The `survey` name is accepted. |
| 2026-11-01 | Context nodes (e.g. a site) carry conditions, never requirements. |
| 2026-11-01 | Authorized members of the vault repository approve maturity changes; authorized collaborators propose changes by pull request. |
| 2026-11-01 | English is the reference language. Title, statement, rationale and verification also exist in Chinese. Text originally written in Chinese is respected (§7). |
| 2026-11-01 | Schedules are out of scope; risks later. |
| 2026-11-01 | HTML is first-class and Word is for formal distribution. HTML is distributed as an artifact or served locally. |
| 2026-11-01 | Record content lives in a private vault repository. This public repository holds only the engine and synthetic examples. |
