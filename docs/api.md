# API reference

This is the reference for people and agents who change qingsong itself. To *use* qingsong on a project's
requirements, read [How to use qingsong](howto.md); for the design and its reasons, read the
[specification](SPEC.md).

The first part, written by hand, explains how the code is organised, what every change must preserve,
and how to extend it. The second part is generated from the code by `tools/build_docs.py`: every
command, every check rule, and every module with its classes and functions. Do not edit the second
part; change the docstrings and rebuild.

## How the code is organised

The package lives in `src/qingsong/`. It has four layers. Each layer uses only the ones before it, and
the command line sits on top.

| Layer | Modules | What it does |
| --- | --- | --- |
| Records and the vault | `schema`, `vault`, `ids`, `hashing`, `findings`, `walk` | Pydantic models of every record type; strict loading of a vault into memory; ID syntax and file paths; stamps and text hashes; the `Finding` a check reports |
| Checks | `checks` and its six rule modules | Rules that read a loaded vault and report findings. They never write. |
| Changing the record | `operations`, `review`, `decisions_file`, `slots`, `wording`, `release`, `gitutil` | Every change to a record file, each one recorded: new records, revisions, approvals, lifecycle changes, issues and proposals, decisions files, slot moves, releases. `gitutil` reads earlier states through git. |
| Outputs | `render.model`, `render.text`, `render.html`, `render.word`, `export` | The HTML site, Word documents and the JSON export, all generated from a loaded vault |
| Command line | `cli` | Typer commands. Each one parses its options, calls one function of the layers above, and prints text or JSON. |

**A command, end to end.** `qingsong revise ID --class value --summary S --by P`:
1. `cli.revise` finds the vault root and calls `operations.revise`.
2. `operations.revise` loads the vault (`vault.load`) and checks the request. For example, it refuses
   `editorial` when the values changed.
3. It edits the record's YAML through `operations.edit`. That reads the file with comments kept,
   applies the change, and passes it to `finish`.
4. `finish` validates the result against the schema, writes the normative hash and the stamp, writes
   the file atomically, and reads it back to check that the stamp holds.
5. The command prints the new revision, or a JSON object with `--json`.

`qingsong check` is the read side: `vault.load` collects load findings, `checks.run` runs every rule,
and issues that track a rule's findings are attached to them.

## What every change must preserve

These invariants are what make the record trustworthy. Tests guard each of them.

- **Strict reading.** Unknown fields, unreadable files and missing references are errors. Nothing is
  filled in by default when a file is read (`schema.StrictModel` forbids extra fields).
- **Every write is recorded.** Record files change only through `operations` (`edit`, `finish`,
  `write_atomically`). Each change bumps `revision`, appends to `history` and rewrites `stamp`. A hand
  edit without a recorded event fails `change.unrecorded`.
- **History is append-only, and identity is permanent.** An ID never changes once it is on the main
  branch. A record is superseded or withdrawn, never deleted. `integrity.against` compares with an
  earlier state to enforce this.
- **Files keep their form.** YAML is read and written with ruamel.yaml in round-trip mode, so comments,
  key order and literal blocks survive an edit.
- **Refusals name the fix.** An operation that cannot proceed raises `OperationError` with a message
  that says what to do. The command line prints it and exits with status 2, or prints
  `{"error": …}` with `--json`. `qingsong check` exits with status 1 when any error is found.
- **No hidden state.** The vault root is passed explicitly, or found from the working directory by
  `vault.find_root`. Nothing writes environment variables or global caches.
- **Dates are parameters.** Every operation takes `today`. Tests pass a fixed date to every call in a
  test. History dates must not go backwards (`change.history`), so mixing a fixed date with the real
  date fails on another day.
- **New schema fields default to `None`.** The stamp covers every field that is not `None`. A new field
  with any other default, such as an empty list, would change the stamp of every existing record.

## Extending qingsong

**A new check rule.**
1. Choose the group module in `src/qingsong/checks/`: `integrity`, `structure`, `change`, `content`,
   `consistency` or `documents`.
2. Write a function that takes a `checks.Context` and yields `Finding(rule, severity, message, record,
   file, fix)`. Register it with `@rule("group.name", "one-line summary")`. Use `checks.by_maturity`
   when the severity depends on the requirement's maturity.
3. Add a fixture to `tests/test_rules.py` that triggers the rule. Every rule must have one.
4. Add the rule to the catalogue in the [specification](SPEC.md#10-checks-accepted-principle-proposed-catalogue),
   then rebuild the docs so that it appears in the rule list below.

**A new record type.**
1. Add a model to `schema.py`, with `type: Literal["…"]`, deriving from `RecordBase`.
2. Add it to `Record`, `record_classes` and `record_folders` (its folder). Add its ID pattern to
   `ids.id_patterns`.
3. Add its fields' references to `walk.py`, so that reference checks and renumbering see them.
4. Describe it in the specification (§5.3), and add the checks and fixtures it needs.

**A new command.**
1. Add a Typer function to `cli.py`. Use the shared options `VaultOption`, `JsonOption`,
   `PersonOption` and `ViaOption`.
2. Call one function of the layers above. Catch `OperationError` and pass it to `fail`. Print with
   `emit`, or with `done` for a single record.
3. The function's docstring becomes the command's help and its entry in the command list below.
   Add the command to the specification (§11), and to [How to use qingsong](howto.md) if people or
   agents use it day to day.

**Tests.** `uv run pytest`. Tests build the fictional DEMO vault from `examples/demo_source` with
`examples/build_demo.py`, through the fixtures `demo` (a folder) and `demo_repository` (a git
repository with its own git identity). They never touch a real vault.

**Documentation.** After changing a docstring, a command, a rule or any Markdown document, run
`uv run python tools/build_docs.py`. `tests/test_docs.py` fails while the generated files are out
of date.

<!-- Generated reference: tools/build_docs.py writes everything below this line. Do not edit it by hand. -->

## Commands

Generated from the command-line interface. Every command also accepts `--vault PATH` (default: the nearest folder holding `qingsong.toml`), `--json` (machine-readable output; `init` and `rules` take only `--json`) and `--help`. `--by` names a person in `people.yaml`; `--via` names the agent acting for them.

### `qingsong check`

Run the consistency checks; exit 1 if any error is found.

```bash
qingsong check [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `--against` |  | Git reference to compare with, e.g. origin/main. |
| `--rule` |  | Run only these rules. |

### `qingsong rules`

List the check rules.

```bash
qingsong rules [OPTIONS]
```

### `qingsong init`

Create an empty vault.

```bash
qingsong init PATH [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `PATH` | yes |  |
| `--code` | yes | Project code, e.g. DEMO. |
| `--name` | yes | Project name in English. |

### `qingsong slot`

Move numbers from the statement into value slots without changing the meaning (SPEC §5.2).

```bash
qingsong slot ID [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `ID` | yes | Requirement ID. |
| `--file` | yes | YAML: slot name → its fields (quantity, relation, value, unit, certainty, …) and replaces: {en: …, zh: …}, the text it replaces in each language. |
| `--by` | yes | Person ID (people.yaml) making the change. |
| `--dry-run` |  | Show the statements before and after; write nothing. |
| `--via` |  | Agent acting for the person, if any. |

### `qingsong adopt`

Take a hand-written record file into the record (adds history and stamp).

```bash
qingsong adopt FILE [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `FILE` | yes |  |
| `--summary` | yes | Why the record was written (e.g. its source). |
| `--by` | yes | Person ID (people.yaml) making the change. |
| `--event` |  | created or imported. |
| `--translation` |  | Status of the second-language text: machine or reviewed. |
| `--via` |  | Agent acting for the person, if any. |

### `qingsong revise`

Record a change made to a record file.

```bash
qingsong revise ID [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `ID` | yes |  |
| `--class` | yes | editorial, value or reallocate. |
| `--summary` | yes | What changed and why. |
| `--by` | yes | Person ID (people.yaml) making the change. |
| `--decision` |  | Decision record, required for baselined. |
| `--translation` |  | unchanged, updated or reviewed. |
| `--to-draft` |  | Promote a concept requirement to draft. |
| `--via` |  | Agent acting for the person, if any. |

### `qingsong supersede`

Mark a record as superseded by one or more successors.

```bash
qingsong supersede ID [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `ID` | yes |  |
| `--with` | yes | Successor ID (repeat for a split). |
| `--summary` | yes | Why. |
| `--by` | yes | Person ID (people.yaml) making the change. |
| `--decision` |  | Decision record. |
| `--via` |  | Agent acting for the person, if any. |

### `qingsong withdraw`

Withdraw a record; its ID is retired for good.

```bash
qingsong withdraw ID [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `ID` | yes |  |
| `--reason` | yes | Why the record is no longer needed. |
| `--by` | yes | Person ID (people.yaml) making the change. |
| `--decision` |  | Decision record. |
| `--via` |  | Agent acting for the person, if any. |

### `qingsong approve`

Record an approver's maturity decision.

```bash
qingsong approve ID [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `ID` | yes |  |
| `--to` | yes | agreed, or draft to reopen. |
| `--by` | yes | Person ID (people.yaml) making the change. |
| `--ref` | yes | Pull request or meeting where the approval was given. |
| `--via` |  | Agent acting for the person, if any. |

### `qingsong confirm`

Clear a suspect link after reviewing the child against its changed parent.

```bash
qingsong confirm CHILD PARENT [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `CHILD` | yes |  |
| `PARENT` | yes |  |
| `--by` | yes | Person ID (people.yaml) making the change. |
| `--via` |  | Agent acting for the person, if any. |

### `qingsong renumber`

Move a record that has not reached main to a free number, rewriting references.

```bash
qingsong renumber OLD NEW [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `OLD` | yes |  |
| `NEW` | yes |  |
| `--by` | yes | Person ID (people.yaml) making the change. |
| `--unmerged` |  | Required: the record is not yet on main. |
| `--via` |  | Agent acting for the person, if any. |

### `qingsong show`

Show one record.

```bash
qingsong show ID [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `ID` | yes |  |

### `qingsong list`

List records, optionally filtered.

```bash
qingsong list [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `--type` |  | Record type. |
| `--node` |  | Allocated node reference. |
| `--maturity` |  | Maturity. |

### `qingsong find`

Find records whose ID, aliases or texts contain TEXT (any language).

```bash
qingsong find TEXT [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `TEXT` | yes |  |

### `qingsong schema`

Print the JSON Schema of all records, or of one record type.

```bash
qingsong schema TYPE [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `TYPE` |  |  |

### `qingsong new requirement`

Allocate the next requirement ID in a namespace and write a concept requirement.

```bash
qingsong new requirement [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `--namespace` | yes | Namespace, e.g. INS-DET or DEMO-SRV. |
| `--title` | yes | Title in the reference language. |
| `--statement` | yes | Statement in the reference language. |
| `--by` | yes | Person ID (people.yaml) making the change. |
| `--level` |  | Level; default from the namespace. |
| `--via` |  | Agent acting for the person, if any. |

### `qingsong new issue`

Create an issue, numbered across the project (ISS-NNNN) from a draft file; the draft is left as it is.

```bash
qingsong new issue [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `--file` | yes | Draft YAML: every field except id and bookkeeping. |
| `--by` | yes | Person ID (people.yaml) making the change. |
| `--slug` |  | Sources only: the name after SRC-, e.g. DEMO-RD-v1.0. |
| `--via` |  | Agent acting for the person, if any. |

### `qingsong new decision`

Create a decision, numbered across the project (DEC-NNNN) from a draft file; the draft is left as it is.

```bash
qingsong new decision [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `--file` | yes | Draft YAML: every field except id and bookkeeping. |
| `--by` | yes | Person ID (people.yaml) making the change. |
| `--slug` |  | Sources only: the name after SRC-, e.g. DEMO-RD-v1.0. |
| `--via` |  | Agent acting for the person, if any. |

### `qingsong new waiver`

Create a waiver, numbered across the project (WVR-NNNN) from a draft file; the draft is left as it is.

```bash
qingsong new waiver [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `--file` | yes | Draft YAML: every field except id and bookkeeping. |
| `--by` | yes | Person ID (people.yaml) making the change. |
| `--slug` |  | Sources only: the name after SRC-, e.g. DEMO-RD-v1.0. |
| `--via` |  | Agent acting for the person, if any. |

### `qingsong new interface`

Create an interface, numbered within the system of its owner_end (IFC-SYS-NNN) from a draft file; the draft is left as it is.

```bash
qingsong new interface [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `--file` | yes | Draft YAML: every field except id and bookkeeping. |
| `--by` | yes | Person ID (people.yaml) making the change. |
| `--slug` |  | Sources only: the name after SRC-, e.g. DEMO-RD-v1.0. |
| `--via` |  | Agent acting for the person, if any. |

### `qingsong new condition`

Create a condition of a context node, numbered per node (NODE-COND-NNN) from a draft file; the draft is left as it is.

```bash
qingsong new condition [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `--file` | yes | Draft YAML: every field except id and bookkeeping. |
| `--by` | yes | Person ID (people.yaml) making the change. |
| `--slug` |  | Sources only: the name after SRC-, e.g. DEMO-RD-v1.0. |
| `--via` |  | Agent acting for the person, if any. |

### `qingsong new source`

Create a source document, named by --slug (SRC-slug) from a draft file; the draft is left as it is.

```bash
qingsong new source [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `--file` | yes | Draft YAML: every field except id and bookkeeping. |
| `--by` | yes | Person ID (people.yaml) making the change. |
| `--slug` |  | Sources only: the name after SRC-, e.g. DEMO-RD-v1.0. |
| `--via` |  | Agent acting for the person, if any. |

### `qingsong new verification`

Create a verification of a requirement, numbered per requirement (VER-ID-NN) from a draft file; the draft is left as it is.

```bash
qingsong new verification [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `--file` | yes | Draft YAML: every field except id and bookkeeping. |
| `--by` | yes | Person ID (people.yaml) making the change. |
| `--slug` |  | Sources only: the name after SRC-, e.g. DEMO-RD-v1.0. |
| `--via` |  | Agent acting for the person, if any. |

### `qingsong issue raise`

Raise issues: from the check findings, or one written by hand.

```bash
qingsong issue raise [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `--by` | yes | Person ID (people.yaml) making the change. |
| `--from-checks` |  | Raise issues for untracked check warnings. |
| `--rule` |  | With --from-checks: only these rules. By hand: the rule tracked. |
| `--group` |  | With --from-checks: one issue per rule for all its records. |
| `--kind` |  | Label of a hand-raised issue. |
| `--title` |  | Title (English). |
| `--title-zh` |  | Title (Chinese). |
| `--description` |  | Description (English). |
| `--description-zh` |  | Description (Chinese). |
| `--record` |  | Record concerned (repeat). |
| `--owner` |  | Person who owns the issue. |
| `--due` |  | Due date or named event. |
| `--via` |  | Agent acting for the person, if any. |

### `qingsong issue propose`

Add a proposed fix to an open issue.

```bash
qingsong issue propose ISSUE [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `ISSUE` | yes |  |
| `--by` | yes | Person ID (people.yaml) making the change. |
| `--file` |  | YAML with summary {en, zh}, change_class and changes. |
| `--keep` |  | Propose to keep the text as written. |
| `--summary` |  | With --keep: why (English). |
| `--summary-zh` |  | With --keep: why (Chinese). |
| `--via` |  | Agent acting for the person, if any. |

### `qingsong issue accept`

Accept a proposal (approvers only): apply its changes and close the issue.

```bash
qingsong issue accept ISSUE [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `ISSUE` | yes |  |
| `--proposal` | yes | Number of the proposal to accept. |
| `--by` | yes | Person ID (people.yaml) making the change. |
| `--decision` |  | Decision record, required for baselined targets. |
| `--via` |  | Agent acting for the person, if any. |

### `qingsong issue reject`

Reject a proposal (an approver), or withdraw it (its author).

```bash
qingsong issue reject ISSUE [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `ISSUE` | yes |  |
| `--proposal` | yes | Number of the proposal to reject. |
| `--reason` | yes | Why (English). |
| `--by` | yes | Person ID (people.yaml) making the change. |
| `--reason-zh` |  | Why (Chinese). |
| `--via` |  | Agent acting for the person, if any. |

### `qingsong issue close`

Close an issue without accepting a proposal (approvers only).

```bash
qingsong issue close ISSUE [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `ISSUE` | yes |  |
| `--outcome` | yes | answered, withdrawn or fixed. |
| `--resolution` | yes | How it was resolved (English). |
| `--by` | yes | Person ID (people.yaml) making the change. |
| `--resolution-zh` |  | How (Chinese). |
| `--via` |  | Agent acting for the person, if any. |

### `qingsong issue apply`

Apply a decisions file from the review page: all its decisions, or none.

```bash
qingsong issue apply FILE [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `FILE` | yes | Decisions file saved from the review page. |
| `--via` |  | Agent acting for the person, if any. |

### `qingsong render html`

Generate the static HTML site; open OUTPUT/index.html in a browser.

```bash
qingsong render html OUTPUT [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `OUTPUT` | yes | Folder for the site (replaced if it exists). |

### `qingsong render docx`

Generate a Word document from the records (styles from templates/reference.docx).

```bash
qingsong render docx DOCUMENT OUTPUT [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `DOCUMENT` | yes | Document ID, e.g. DEMO-INS-DET-RD. |
| `OUTPUT` | yes | Path of the .docx file to write. |
| `--version` |  | Version shown on the cover and header. |
| `--update-fields` |  | Ask Word to update all fields on opening (page numbers in the table of contents); Word then shows a prompt. |
| `--release` |  | Render the document as issued: the vault at the tag of this release. |

### `qingsong release prepare`

Write the release entry on a branch, for review; prints the changes since the last release.

```bash
qingsong release prepare DOCUMENT VERSION [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `DOCUMENT` | yes | Document ID. |
| `VERSION` | yes | New version, e.g. 1.2. |
| `--by` | yes | Person ID (people.yaml) making the change. |
| `--summary-en` | yes | What this release changes (English). |
| `--summary-zh` | yes | What this release changes (Chinese). |
| `--note-en` |  | Optional note (English). |
| `--note-zh` |  | Optional note (Chinese). |
| `--date` |  | Date of the release decision (YYYY-MM-DD); default today. |
| `--via` |  | Agent acting for the person, if any. |

### `qingsong release tag`

Tag a merged release at the commit that brought it to the main branch (local tag only).

```bash
qingsong release tag DOCUMENT VERSION [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `DOCUMENT` | yes | Document ID. |
| `VERSION` | yes | Released version. |
| `--at` |  | Only for a release made before qingsong: the commit where the record was verified against the issued document. |

### `qingsong release changes`

Summarise what changed in a document between two states.

```bash
qingsong release changes DOCUMENT [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `DOCUMENT` | yes | Document ID. |
| `--since` |  | A release version or a git reference; default: the last tagged release. |
| `--until` |  | A git reference; default: the working tree. |

### `qingsong export json`

All records, the tree and an index of value slots, as one JSON file (SPEC §12.3).

```bash
qingsong export json [OPTIONS]
```

| Argument or option | Required | Meaning |
| --- | --- | --- |
| `--output` |  | File to write; default: standard output. |
| `--at` |  | Export the vault at this git reference. |
| `--release` |  | Export the state of a release, written DOC/VERSION. |

## Check rules

Generated from the rule registry; `qingsong rules` prints the same list. Severities often depend on the record's maturity. The rules marked *(load)* report problems found while reading the vault.

| Rule | What it checks |
| --- | --- |
| `change.approval` | agreed and baselined requirements carry a current approval by an approver |
| `change.history` | history is complete and in order |
| `change.stale_evidence` | verifications and waivers refer to the current normative revision |
| `change.stale_proposal` | open proposals still match the text they would replace |
| `change.suspect_link` | links are reviewed after their target changed |
| `change.translation` | translations are tracked, current, and reviewed where required |
| `change.unrecorded` | every change is recorded (the stamp matches the content) |
| `consistency.child_looser` | a child allows no values its parent excludes (same quantity) |
| `consistency.conflict` | requirements on one quantity leave a value that meets them all |
| `consistency.issue_due` | open issues are not past their due date |
| `content.bilingual` | required fields exist in both languages from draft maturity upward |
| `content.completeness` | rationale and verification are present according to maturity |
| `content.evidence` | a 'compliant' verification names evidence |
| `content.languages` | texts use the configured languages, are not empty, and exist in the origin language |
| `content.open_values` | provisional, TBD and TBC values are tracked by an open issue |
| `content.references` | [[…]] references are well formed |
| `content.values` | value slots are used, tracked, and have valid units matching their quantity |
| `content.writing` | one 'shall' per statement; no vague terms |
| `documents.release` | release entries are well formed, in order, and made by approvers |
| `documents.release_tag` | release tags mark a commit that holds the same release entry |
| `integrity.against` | compared with an earlier version: nothing removed, retyped, rewritten or reversed |
| `integrity.config` | the configuration file qingsong.toml is valid *(load)* |
| `integrity.duplicate_id` | an ID is defined by one file only |
| `integrity.figure_file` | figure images exist next to their record and match their sha256 |
| `integrity.id_syntax` | every ID follows the pattern of its record type |
| `integrity.missing_file` | people.yaml and glossary.yaml exist *(load)* |
| `integrity.path_mismatch` | each file is stored where its ID says *(load)* |
| `integrity.proposal` | issues name known rules; proposals name known records and fields |
| `integrity.schema` | every record matches its schema; no unknown fields *(load)* |
| `integrity.unresolved_reference` | every referenced record, node, person, quantity and term exists |
| `integrity.yaml_syntax` | every file is valid YAML *(load)* |
| `structure.alias` | aliases do not collide with IDs or overlap within a document |
| `structure.allocation` | a requirement is allocated to one active product node |
| `structure.cycle` | derives_from has no cycles |
| `structure.ends` | interfaces join two different nodes; conditions belong to context nodes |
| `structure.justification` | a parentless requirement is justified (otherwise TBJ) |
| `structure.level` | levels are configured, ordered downward, and match the namespace |
| `structure.lifecycle` | superseded records name successors; links point to current records |
| `structure.namespace` | an ID's namespace exists in the tree or configuration |
| `structure.node_code` | node codes are valid, not reserved, and unique within their system *(load)* |
| `structure.outline` | each requirement and figure appears once in a document outline; section keys are unique |
| `structure.tree_parent` | top-level branches hang from the root *(load)* |
| `structure.tree_root` | the tree has exactly one root file *(load)* |

## Modules: records and the vault

### `qingsong.schema`

Source: [`src/qingsong/schema.py`](../src/qingsong/schema.py)

Record schemas (docs/SPEC.md §4–§5). Unknown fields are errors; nothing is defaulted on reading
except empty lists and absent optional values.

**Types**

- `LocalizedText`: `dict[str, str]`
- `Maturity`: `Literal['concept', 'draft', 'agreed', 'baselined']`
- `Lifecycle`: `Literal['current', 'superseded', 'withdrawn']`
- `Certainty`: `Literal['firm', 'provisional', 'tbc', 'tbd']`
- `VerificationMethod`: `Literal['test', 'analysis', 'inspection', 'demonstration', 'review_of_design']`
- `ChangeClass`: `Literal['editorial', 'value', 'reallocate']`
- `EventKind`: `Literal['created', 'imported', 'revised', 'approved', 'confirmed', 'superseded', 'withdrawn', 'renumbered', 'released', 'slotted']`
- `NodeKind`: `Literal['product', 'work', 'context']`
- `TextHash`: `str` (pattern `^([0-9a-f]{16})?$`)
- `IssueKind`: `Literal['tbd', 'tbc', 'provisional', 'tbj', 'wording', 'translation', 'question', 'conflict']`
- `Record`: `Requirement | Figure | Condition | Quantity | Issue | Decision | Source | Interface | VerificationRecord | Waiver | Baseline | Document` (chosen by `type`)

**Classes**

#### class `StrictModel` (BaseModel)

#### class `HistoryEvent` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `revision` | `int` | `required` |
| `date` | `date` | `required` |
| `by` | `str` | `required` |
| `event` | `Literal['created', 'imported', 'revised', 'approved', 'confirmed', 'superseded', 'withdrawn', 'renumbered', 'released', 'slotted']` | `required` |
| `change_class` | `Optional[Literal['editorial', 'value', 'reallocate']]` | `None` |
| `summary` | `str` | `required` |
| `decision` | `str \| None` | `None` |
| `via` | `str \| None` | `None` |
| `normative_hash_before` | `str \| None` | `None` |
| `normative_hash_after` | `str \| None` | `None` |

#### class `Alias` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `kind` | `Literal['legacy', 'vendor', 'external']` | `required` |
| `document` | `str` | `required` |
| `from_version` | `str \| None` | `None` |
| `to_version` | `str \| None` | `None` |
| `note` | `str \| None` | `None` |

#### class `Link` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `normative_revision` | `int` | `required` |

#### class `SourceCitation` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `source` | `str` | `required` |
| `locator` | `str` | `required` |

#### class `Tolerance` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `plus` | `float` | `required` |
| `minus` | `float` | `required` |

#### class `ValueSlot` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `quantity` | `str \| None` | `None` |
| `relation` | `Literal['eq', 'le', 'lt', 'ge', 'gt', 'range', 'approx']` | `required` |
| `value` | `float \| None` | `None` |
| `minimum` | `float \| None` | `None` |
| `maximum` | `float \| None` | `None` |
| `tolerance` | `Tolerance \| None` | `None` |
| `unit` | `str \| None` | `None` |
| `certainty` | `Literal['firm', 'provisional', 'tbc', 'tbd']` | `required` |
| `issue` | `str \| None` | `None` |
| `condition` | `dict[str, str] \| None` | `None` |
| `goal` | `float \| None` | `None` |

- `check_numbers(self) -> 'ValueSlot'`

#### class `Verification` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `methods` | `list[Literal['test', 'analysis', 'inspection', 'demonstration', 'review_of_design']]` | `required` |
| `level` | `str \| None` | `None` |
| `criteria` | `dict[str, str]` | `required` |

#### class `Approval` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `by` | `str` | `required` |
| `date` | `date` | `required` |
| `ref` | `str` | `required` |
| `normative_revision` | `int` | `required` |
| `text_hash` | `str` | `required` |

#### class `TranslationState` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `source_hash` | `str` | `required` |
| `status` | `Literal['machine', 'reviewed']` | `required` |
| `by` | `str \| None` | `None` |
| `date` | `date \| None` | `None` |

#### class `Variant` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `source` | `str` | `required` |
| `label` | `str` | `required` |
| `relation` | `Literal['vendor_stated', 'proposed', 'rejected']` | `required` |
| `statement` | `dict[str, str] \| None` | `None` |
| `values` | `dict[str, ValueSlot]` | `{}` |

#### class `RecordBase` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `id` | `str` | `required` |
| `type` | `str` | `required` |
| `title` | `dict[str, str]` | `required` |
| `lifecycle` | `Literal['current', 'superseded', 'withdrawn']` | `required` |
| `superseded_by` | `list[str]` | `[]` |
| `aliases` | `list[Alias]` | `[]` |
| `revision` | `int` | `required` |
| `normative_revision` | `int` | `required` |
| `normative_hash` | `str` | `required` |
| `history` | `list[HistoryEvent]` | `required` |
| `stamp` | `str` | `required` |

#### class `Requirement` (RecordBase)

| Field | Type | Default |
| --- | --- | --- |
| `type` | `Literal['requirement']` | `required` |
| `statement` | `dict[str, str]` | `required` |
| `values` | `dict[str, ValueSlot]` | `{}` |
| `rationale` | `dict[str, str] \| None` | `None` |
| `notes` | `dict[str, str] \| None` | `None` |
| `suggestions` | `dict[str, str] \| None` | `None` |
| `justification` | `dict[str, str] \| None` | `None` |
| `justified_by` | `str \| None` | `None` |
| `level` | `str` | `required` |
| `allocated_to` | `str` | `required` |
| `interface` | `str \| None` | `None` |
| `derives_from` | `list[Link]` | `[]` |
| `constrained_by` | `list[Link]` | `[]` |
| `issues` | `list[str]` | `[]` |
| `sources` | `list[SourceCitation]` | `[]` |
| `verification` | `Verification \| None` | `None` |
| `maturity` | `Literal['concept', 'draft', 'agreed', 'baselined']` | `required` |
| `approval` | `Approval \| None` | `None` |
| `text_origin` | `str` | `required` |
| `translation` | `dict[str, TranslationState]` | `{}` |
| `variants` | `list[Variant]` | `[]` |

#### class `FigureFile` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `path` | `str` | `required` |
| `sha256` | `str` | `required` |

- `plain_name(cls, path: str) -> str`

#### class `Provenance` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `script` | `str \| None` | `None` |
| `repository` | `str \| None` | `None` |
| `version` | `str \| None` | `None` |
| `data` | `str \| None` | `None` |
| `date` | `date \| None` | `None` |
| `note` | `str \| None` | `None` |

#### class `Figure` (RecordBase)

| Field | Type | Default |
| --- | --- | --- |
| `type` | `Literal['figure']` | `required` |
| `caption` | `dict[str, str]` | `required` |
| `alt` | `dict[str, str] \| None` | `None` |
| `files` | `list[FigureFile]` | `required` |
| `provenance` | `Provenance \| None` | `None` |
| `text_origin` | `str` | `required` |
| `translation` | `dict[str, TranslationState]` | `{}` |

#### class `Condition` (RecordBase)

| Field | Type | Default |
| --- | --- | --- |
| `type` | `Literal['condition']` | `required` |
| `node` | `str` | `required` |
| `description` | `dict[str, str] \| None` | `None` |
| `values` | `dict[str, ValueSlot]` | `{}` |
| `evidence_basis` | `Literal['measured', 'modelled', 'assumed']` | `required` |
| `date` | `date \| None` | `None` |
| `sources` | `list[SourceCitation]` | `[]` |

#### class `Quantity` (RecordBase)

| Field | Type | Default |
| --- | --- | --- |
| `type` | `Literal['quantity']` | `required` |
| `symbol` | `str \| None` | `None` |
| `dimension` | `str` | `required` |
| `unit` | `str` | `required` |
| `kpp` | `bool` | `False` |
| `description` | `dict[str, str] \| None` | `None` |
| `environmental` | `bool \| None` | `None` |

#### class `ProposedChange` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `record` | `str` | `required` |
| `field` | `Literal['title', 'statement', 'rationale', 'notes', 'suggestions', 'criteria']` | `required` |
| `text` | `dict[str, str]` | `required` |
| `base` | `dict[str, Annotated[str, FieldInfo(annotation=NoneType, required=True, metadata=[_PydanticGeneralMetadata(pattern='^([0-9a-f]{16})?$')])]]` | `{}` |

#### class `Proposal` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `number` | `int` | `required` |
| `date` | `date` | `required` |
| `by` | `str` | `required` |
| `via` | `str \| None` | `None` |
| `summary` | `dict[str, str]` | `required` |
| `change_class` | `Literal['editorial', 'value', 'reallocate']` | `'editorial'` |
| `status` | `Literal['proposed', 'accepted', 'rejected']` | `required` |
| `reason` | `dict[str, str] \| None` | `None` |
| `changes` | `list[ProposedChange]` | `[]` |

#### class `Issue` (RecordBase)

| Field | Type | Default |
| --- | --- | --- |
| `type` | `Literal['issue']` | `required` |
| `kind` | `Literal['tbd', 'tbc', 'provisional', 'tbj', 'wording', 'translation', 'question', 'conflict']` | `required` |
| `status` | `Literal['open', 'closed']` | `required` |
| `description` | `dict[str, str]` | `required` |
| `owner` | `str \| None` | `None` |
| `due` | `str \| None` | `None` |
| `closure_plan` | `dict[str, str] \| None` | `None` |
| `records` | `list[str]` | `[]` |
| `rule` | `str \| None` | `None` |
| `proposals` | `list[Proposal] \| None` | `None` |
| `outcome` | `Optional[Literal['fixed', 'accepted_as_written', 'answered', 'withdrawn']]` | `None` |
| `accepted` | `dict[str, Annotated[str, FieldInfo(annotation=NoneType, required=True, metadata=[_PydanticGeneralMetadata(pattern='^([0-9a-f]{16})?$')])]] \| None` | `None` |
| `resolution` | `dict[str, str] \| None` | `None` |

#### class `Decision` (RecordBase)

| Field | Type | Default |
| --- | --- | --- |
| `type` | `Literal['decision']` | `required` |
| `date` | `date` | `required` |
| `by` | `str` | `required` |
| `statement` | `dict[str, str]` | `required` |
| `rationale` | `dict[str, str] \| None` | `None` |
| `records` | `list[str]` | `[]` |

#### class `Source` (RecordBase)

| Field | Type | Default |
| --- | --- | --- |
| `type` | `Literal['source']` | `required` |
| `kind` | `Literal['project_document', 'standard', 'publication', 'vendor_document', 'dataset']` | `required` |
| `number` | `str \| None` | `None` |
| `version` | `str \| None` | `None` |
| `date` | `date \| None` | `None` |
| `file` | `str \| None` | `None` |
| `sha256` | `str \| None` | `None` |
| `location` | `str \| None` | `None` |
| `url` | `str \| None` | `None` |

#### class `Interface` (RecordBase)

| Field | Type | Default |
| --- | --- | --- |
| `type` | `Literal['interface']` | `required` |
| `owner_end` | `str` | `required` |
| `other_end` | `str` | `required` |
| `description` | `dict[str, str] \| None` | `None` |
| `values` | `dict[str, ValueSlot]` | `{}` |

#### class `Evidence` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `kind` | `Literal['file', 'source', 'analysis', 'report']` | `required` |
| `reference` | `str` | `required` |
| `note` | `str \| None` | `None` |

#### class `VerificationRecord` (RecordBase)

| Field | Type | Default |
| --- | --- | --- |
| `type` | `Literal['verification']` | `required` |
| `requirement` | `str` | `required` |
| `requirement_normative_revision` | `int` | `required` |
| `method` | `Literal['test', 'analysis', 'inspection', 'demonstration', 'review_of_design']` | `required` |
| `status` | `Literal['planned', 'predicted', 'compliant', 'partially_compliant', 'non_compliant', 'waived']` | `required` |
| `evidence` | `list[Evidence]` | `[]` |

#### class `Waiver` (RecordBase)

| Field | Type | Default |
| --- | --- | --- |
| `type` | `Literal['waiver']` | `required` |
| `requirement` | `str` | `required` |
| `requirement_normative_revision` | `int` | `required` |
| `scope` | `dict[str, str]` | `required` |
| `reason` | `dict[str, str]` | `required` |
| `approver` | `str` | `required` |
| `expires` | `date \| None` | `None` |

#### class `Baseline` (RecordBase)

| Field | Type | Default |
| --- | --- | --- |
| `type` | `Literal['baseline']` | `required` |
| `tag` | `str` | `required` |
| `review` | `str` | `required` |
| `records` | `list[str]` | `[]` |

#### class `Role` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `role` | `dict[str, str]` | `required` |
| `person` | `str` | `required` |

#### class `Release` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `version` | `str` | `required` |
| `date` | `date` | `required` |
| `summary` | `dict[str, str]` | `required` |
| `by` | `str \| None` | `None` |
| `note` | `dict[str, str] \| None` | `None` |
| `tag` | `str \| None` | `None` |
| `made_with_qingsong` | `bool` | `required` |
| `engine` | `str \| None` | `None` |

#### class `FrontMatter` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `roles` | `list[Role]` | `[]` |
| `reference_documents` | `list[str]` | `[]` |
| `bibliography` | `list[str]` | `[]` |
| `acronyms` | `list[str]` | `[]` |

#### class `TableBlock` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `caption` | `dict[str, str] \| None` | `None` |
| `header` | `list[dict[str, str]]` | `required` |
| `rows` | `list[list[dict[str, str]]]` | `required` |

- `check_widths(self) -> 'TableBlock'`

#### class `DefinitionsBlock` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `terms` | `list[str]` | `required` |
| `caption` | `dict[str, str] \| None` | `None` |

#### class `Block` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `section` | `Section \| None` | `None` |
| `text` | `dict[str, str] \| None` | `None` |
| `requirement` | `str \| None` | `None` |
| `figure` | `str \| None` | `None` |
| `table` | `TableBlock \| None` | `None` |
| `definitions` | `DefinitionsBlock \| None` | `None` |

- `exactly_one(self) -> 'Block'`

#### class `Section` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `key` | `str` | `required` |
| `title` | `dict[str, str]` | `required` |
| `blocks` | `list[Block]` | `[]` |

#### class `Document` (RecordBase)

| Field | Type | Default |
| --- | --- | --- |
| `type` | `Literal['document']` | `required` |
| `scope` | `list[str]` | `[]` |
| `front` | `FrontMatter` | `FrontMatter(roles=[], reference_documents=[], bibliography=[], acronyms=[])` |
| `outline` | `list[Block]` | `[]` |
| `releases` | `list[Release]` | `[]` |

#### class `Node` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `node` | `str` | `required` |
| `names` | `dict[str, str]` | `required` |
| `kind` | `Literal['product', 'work', 'context']` | `required` |
| `status` | `Literal['active', 'placeholder', 'retired']` | `required` |
| `structural_code` | `str \| None` | `None` |
| `text_origin` | `str \| None` | `None` |
| `description` | `dict[str, str] \| None` | `None` |
| `owners` | `list[str]` | `[]` |
| `design_stage` | `str \| None` | `None` |
| `note` | `str \| None` | `None` |
| `children` | `list[Node]` | `[]` |

#### class `TreeFile` (Node)

| Field | Type | Default |
| --- | --- | --- |
| `parent` | `str \| None` | `None` |

#### class `Person` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `name` | `str` | `required` |
| `organization` | `str \| None` | `None` |
| `github` | `str \| None` | `None` |
| `email` | `str \| None` | `None` |
| `languages` | `list[str]` | `[]` |
| `approver` | `bool` | `False` |

#### class `PeopleFile` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `people` | `dict[str, Person]` | `required` |

- `check_ids(cls, people: dict[str, Person]) -> dict[str, Person]`

#### class `GlossaryEntry` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `kind` | `Literal['acronym', 'term', 'symbol']` | `required` |
| `text` | `str \| None` | `None` |
| `expansion` | `dict[str, str] \| None` | `None` |
| `definition` | `dict[str, str] \| None` | `None` |

#### class `GlossaryFile` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `terms` | `dict[str, GlossaryEntry]` | `{}` |

#### class `ProjectConfig` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `code` | `str` | `required` |
| `names` | `dict[str, str]` | `required` |

#### class `LanguageConfig` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `reference` | `str` | `required` |
| `second` | `str` | `required` |
| `default_text_origin` | `str` | `required` |
| `bilingual_fields` | `list[str]` | `required` |

#### class `LevelConfig` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `name` | `str` | `required` |
| `names` | `dict[str, str]` | `required` |

#### class `VaultConfig` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `project` | `ProjectConfig` | `required` |
| `languages` | `LanguageConfig` | `required` |
| `levels` | `list[LevelConfig]` | `required` |
| `top_namespaces` | `dict[str, str]` | `required` |
| `related` | `dict[str, str]` | `{}` |
| `tree_order` | `list[str]` | `[]` |
| `documents` | `dict[str, str]` | `{}` |

- `check_levels(self) -> 'VaultConfig'`
- property `level_rank`

**Functions**

#### `plain`

```python
def plain(data: Any) -> Any
```

Convert ruamel containers to plain Python containers.

### `qingsong.vault`

Source: [`src/qingsong/vault.py`](../src/qingsong/vault.py)

Vault discovery, strict loading and round-trip saving (docs/SPEC.md §3, §6.1).

**Classes**

#### class `VaultNotFoundError` (Exception)

#### class `NodeInfo`

| Field | Type | Default |
| --- | --- | --- |
| `node` | `Node` | `required` |
| `reference` | `str` | `required` |
| `system` | `str \| None` | `required` |
| `depth` | `int` | `required` |
| `parent` | `str \| None` | `required` |
| `file` | `str` | `required` |

- property `requirement_namespace`

#### class `Vault`

| Field | Type | Default |
| --- | --- | --- |
| `root` | `Path` | `required` |
| `config` | `VaultConfig \| None` | `None` |
| `nodes` | `dict[str, NodeInfo]` | `{}` |
| `root_node` | `str \| None` | `None` |
| `people` | `PeopleFile \| None` | `None` |
| `glossary` | `GlossaryFile \| None` | `None` |
| `records` | `dict[str, RecordBase]` | `{}` |
| `files` | `dict[str, Path]` | `{}` |
| `duplicates` | `list[tuple[str, Path]]` | `[]` |
| `load_findings` | `list[Finding]` | `[]` |

- `relative(self, path: Path) -> str`
- `by_type(self, record_type: str) -> list[RecordBase]`
- `namespaces(self) -> dict[str, str]`
  Requirement namespace → node reference it belongs to.
- `is_approver(self, person: str) -> bool`

**Functions**

#### `find_root`

```python
def find_root(start: Path | None = None) -> Path
```

The nearest folder, from `start` upward, that holds qingsong.toml.

#### `load`

```python
def load(root: Path) -> Vault
```

Load a whole vault strictly. Nothing is defaulted; every unreadable file or schema violation
becomes a load finding, reported by the check.

#### `vault_at`

```python
def vault_at(root: Path, ref: str) -> Iterator[Vault]
```

The vault as stored at a git reference, loaded from a temporary copy of the raw stored files
(docs/SPEC.md §5.5). Raises gitutil.GitError when the reference cannot be read.

#### `save_record`

```python
def save_record(
    path: Path,
    updates: dict[str, Any],
    removals: tuple[str, ...] = (),
) -> None
```

Apply top-level updates to a record file, keeping comments, key order and quoting.

**Helpers**

- `read_yaml(path: Path) -> Any`
- `round_trip_yaml() -> YAML`
- `describe_validation_error(error: ValidationError) -> str`
- `load_config(vault: Vault) -> None`
- `load_tree(vault: Vault) -> None`
- `register_branch(vault: Vault, node: Node, system: str | None, depth: int, parent: str | None, file: str) -> None`
- `load_people_and_glossary(vault: Vault) -> None`
- `load_records(vault: Vault) -> None`
- `load_record_file(vault: Vault, path: Path, expected_type: str) -> None`
- `write_new_record(path: Path, data: dict[str, Any]) -> None`
- `expected_path(vault: Vault, record: RecordBase) -> Path`

### `qingsong.ids`

Source: [`src/qingsong/ids.py`](../src/qingsong/ids.py)

Identifier syntax, namespaces and file paths (docs/SPEC.md §4.3, §5.3, §6).

**Functions**

#### `sort_key`

```python
def sort_key(record_id: str) -> tuple
```

Order IDs with their numbers compared as numbers (REQ-9 before REQ-10).

**Helpers**

- `id_matches(record_type: str, record_id: str) -> bool`
- `namespace_of(record_type: str, record_id: str) -> str | None`
- `number_of(record_type: str, record_id: str) -> int | None`
- `format_id(record_type: str, namespace: str | None, number: int) -> str`
- `relative_path(record_type: str, record_id: str) -> Path`
- `references_in_text(text: str) -> list[tuple[str, str | None]]`

### `qingsong.hashing`

Source: [`src/qingsong/hashing.py`](../src/qingsong/hashing.py)

Stamps and text hashes (docs/SPEC.md §7, §8.2).

**Functions**

#### `normative_hash_of`

```python
def normative_hash_of(record: RecordBase) -> str
```

Hash of the fields whose change can never be editorial (values, level, verification method…).

#### `review_hash`

```python
def review_hash(record: RecordBase) -> str
```

Hash of a record's prose and values in every language: what an issue accepted as written
covers (docs/SPEC.md §5.6).

#### `proposal_hash`

```python
def proposal_hash(proposal: Proposal) -> str
```

Hash of what a reviewer reads of a proposal: its summary, change class and changes. A
decisions file carries it, so that a proposal edited after the review page was made is not
decided unread (docs/SPEC.md §5.6).

#### `field_text_hashes`

```python
def field_text_hashes(record: RecordBase, dotted: str) -> dict[str, str]
```

Hash of each language's text of one field; the base of a proposed change.

#### `approved_text_hash`

```python
def approved_text_hash(record: RecordBase, language: str) -> str
```

Hash of the approved wording: statement and verification criteria in the reference language.

**Helpers**

- `short_hash(data: bytes) -> str`
- `canonical_json(data: Any) -> bytes`
- `stamp_of(record: RecordBase) -> str`
- `text_hash(text: str) -> str`
- `file_sha256(path: Path) -> str`
- `field_value(record: RecordBase, dotted: str) -> Any`

### `qingsong.findings`

Source: [`src/qingsong/findings.py`](../src/qingsong/findings.py)

Check results (docs/SPEC.md §10).

**Classes**

#### class `Finding`

| Field | Type | Default |
| --- | --- | --- |
| `rule` | `str` | `required` |
| `severity` | `str` | `required` |
| `message` | `str` | `required` |
| `record` | `str \| None` | `None` |
| `file` | `str \| None` | `None` |
| `fix` | `str \| None` | `None` |
| `issue` | `str \| None` | `None` |

- `as_dict(self) -> dict`
- `line(self) -> str`

### `qingsong.walk`

Source: [`src/qingsong/walk.py`](../src/qingsong/walk.py)

Walk records for localized texts and references.

**Functions**

#### `localized_texts`

```python
def localized_texts(
    model: BaseModel,
    path: str = '',
) -> Iterator[tuple[str, dict[str, str]]]
```

Yield (field path, {language: text}) for every localized text inside a model.

#### `text_references`

```python
def text_references(model: BaseModel) -> Iterator[tuple[str, str, str | None]]
```

Yield (field path, target ID, section key) for every [[…]] reference in localized texts.

**Helpers**

- `is_localized(annotation: object) -> bool`
- `nested_texts(value: object, path: str) -> Iterator[tuple[str, dict[str, str]]]`

## Modules: checks

### `qingsong.checks`

Source: [`src/qingsong/checks/__init__.py`](../src/qingsong/checks/__init__.py)

Check registry and runner (docs/SPEC.md §10).

**Classes**

#### class `Context`

| Field | Type | Default |
| --- | --- | --- |
| `vault` | `Vault` | `required` |
| `against` | `str \| None` | `required` |

#### class `Rule`

| Field | Type | Default |
| --- | --- | --- |
| `rule_id` | `str` | `required` |
| `summary` | `str` | `required` |
| `function` | `Callable[[Context], Iterable[Finding]]` | `required` |

**Functions**

#### `run`

```python
def run(
    vault: Vault,
    against: str | None = None,
    selected: set[str] | None = None,
) -> list[Finding]
```

Run the rules (all, or the `selected` ones) on a loaded vault and return every finding,
sorted by severity. With `against`, the integrity rules also compare with that git reference.
Findings tracked by an issue name it; findings on records accepted as written become notes.

#### `apply_review`

```python
def apply_review(vault: Vault, findings: list[Finding]) -> list[Finding]
```

Findings that an issue covers (docs/SPEC.md §5.6): an open issue tracking the rule on the
record is named; an acceptance as written turns the finding into a note while the record's
review hash is unchanged.

#### `all_rule_summaries`

```python
def all_rule_summaries() -> dict[str, str]
```

Every rule ID, including those reported while loading, with its one-line summary.

**Helpers**

- `rule(rule_id: str, summary: str) -> Callable`
- `by_maturity(maturity: str | None, concept: str, draft: str, agreed: str, baselined: str) -> str`
- `relative_file(vault: Vault, record_id: str) -> str | None`

### `qingsong.checks.integrity`

Source: [`src/qingsong/checks/integrity.py`](../src/qingsong/checks/integrity.py)

Integrity rules: identifiers, paths, references, and comparison with an earlier version.

**Check rules**

- `integrity.duplicate_id` (`duplicate_ids`): an ID is defined by one file only.
- `integrity.id_syntax` (`id_syntax`): every ID follows the pattern of its record type.
- `integrity.path_mismatch` (`path_mismatch`): each file is stored where its ID says.
- `integrity.unresolved_reference` (`unresolved_references`): every referenced record, node, person, quantity and term exists.
- `integrity.against` (`against_reference`): compared with an earlier version: nothing removed, retyped, rewritten or reversed.
- `integrity.figure_file` (`figure_files`): figure images exist next to their record and match their sha256.
- `integrity.proposal` (`proposals`): issues name known rules; proposals name known records and fields.

**Functions**

#### `references`

```python
def references(vault: Vault) -> Iterator[tuple[str, str, str, str | None]]
```

Yield (record ID, field, target, expected kind) for every reference held in a record.

#### `slotted_since`

```python
def slotted_since(record, earlier_hash: object, earlier_revision: object) -> bool
```

The normative hash changed only by recorded moves of numbers into slots: the `slotted`
events since the reference lead, hash to hash, from the earlier hash to the current one.

#### `changed_releases`

```python
def changed_releases(document: Document, earlier: list, ref: str) -> Iterator[Finding]
```

Release entries are append-only; a release made before qingsong may gain its tag.

**Helpers**

- `section_keys(document: Document) -> set[str]`
- `document_references(document: Document) -> Iterator[tuple[str, str, str, str | None]]`
- `records_at(root: Path, ref: str) -> dict[str, dict]`
- `nodes_at(root: Path, ref: str) -> set[str]`
- `collect_node_references(node: dict, system: str | None, depth: int, found: set[str]) -> None`
- `comparable(value: object) -> object`
- `plain_event(event: dict) -> dict`

### `qingsong.checks.structure`

Source: [`src/qingsong/checks/structure.py`](../src/qingsong/checks/structure.py)

Structure rules: tree codes, allocation, levels, flow-down, lifecycle links, aliases.

**Check rules**

- `structure.node_code` (`node_codes`): node codes are valid, not reserved, and unique within their system.
- `structure.allocation` (`allocation`): a requirement is allocated to one active product node.
- `structure.namespace` (`namespace_known`): an ID's namespace exists in the tree or configuration.
- `structure.level` (`levels`): levels are configured, ordered downward, and match the namespace.
- `structure.justification` (`justification`): a parentless requirement is justified (otherwise TBJ).
- `structure.cycle` (`cycles`): derives_from has no cycles.
- `structure.lifecycle` (`lifecycle`): superseded records name successors; links point to current records.
- `structure.alias` (`aliases`): aliases do not collide with IDs or overlap within a document.
- `structure.ends` (`ends`): interfaces join two different nodes; conditions belong to context nodes.
- `structure.outline` (`outline`): each requirement and figure appears once in a document outline; section keys are unique.

**Helpers**

- `requirements(context: Context) -> Iterator[Requirement]`
- `version_key(version: str | None) -> tuple`
- `ranges_overlap(start_a: str | None, end_a: str | None, start_b: str | None, end_b: str | None) -> bool`
- `outline_counts(blocks, counts: dict[str, int]) -> dict[str, int]`
- `section_keys(blocks, keys: list[str]) -> list[str]`

### `qingsong.checks.change`

Source: [`src/qingsong/checks/change.py`](../src/qingsong/checks/change.py)

Change-control rules: stamps, history, suspect links, approvals, translations, stale evidence.

**Check rules**

- `change.unrecorded` (`unrecorded`): every change is recorded (the stamp matches the content).
- `change.history` (`history`): history is complete and in order.
- `change.suspect_link` (`suspect_links`): links are reviewed after their target changed.
- `change.approval` (`approvals`): agreed and baselined requirements carry a current approval by an approver.
- `change.translation` (`translations`): translations are tracked, current, and reviewed where required.
- `change.stale_evidence` (`stale_evidence`): verifications and waivers refer to the current normative revision.
- `change.stale_proposal` (`stale_proposals`): open proposals still match the text they would replace.

### `qingsong.checks.content`

Source: [`src/qingsong/checks/content.py`](../src/qingsong/checks/content.py)

Content rules: languages, writing rules (INCOSE-derived), references, open values, value slots,
completeness and evidence.

**Check rules**

- `content.languages` (`languages`): texts use the configured languages, are not empty, and exist in the origin language.
- `content.bilingual` (`bilingual`): required fields exist in both languages from draft maturity upward.
- `content.writing` (`writing`): one 'shall' per statement; no vague terms.
- `content.references` (`reference_syntax`): [[…]] references are well formed.
- `content.open_values` (`open_values`): provisional, TBD and TBC values are tracked by an open issue.
- `content.values` (`values`): value slots are used, tracked, and have valid units matching their quantity.
- `content.completeness` (`completeness`): rationale and verification are present according to maturity.
- `content.evidence` (`evidence`): a 'compliant' verification names evidence.

**Functions**

#### `numbers_in_text`

```python
def numbers_in_text(record: Requirement) -> list[str]
```

Numbers written in the reference-language statement rather than in value slots. Years are
left out: a date in a statement is context, not a value to compare.

#### `requirement_form`

```python
def requirement_form(record: Requirement) -> str
```

Quantitative with value slots, qualitative without (docs/SPEC.md §5.2); derived, never
stored.

#### `prose`

```python
def prose(text: str) -> str
```

Text with references, mathematics, code, links and footnotes removed.

**Helpers**

- `requirements(context: Context) -> Iterator[Requirement]`
- `tracking_issues(context: Context, record: Requirement) -> list[str]`
- `parse_unit(text: str)`

### `qingsong.checks.consistency`

Source: [`src/qingsong/checks/consistency.py`](../src/qingsong/checks/consistency.py)

Consistency rules: values that cannot all hold, children looser than their parents, overdue
issues (docs/SPEC.md §10, "Consistency rules in detail").

**Classes**

#### class `Interval`

The values a slot allows, in its quantity's unit.

| Field | Type | Default |
| --- | --- | --- |
| `low` | `float` | `required` |
| `high` | `float` | `required` |
| `low_open` | `bool` | `False` |
| `high_open` | `bool` | `False` |

- `intersection(self, other: 'Interval') -> 'Interval | None'`
- `within(self, other: 'Interval') -> bool`
- `describe(self, unit: str) -> str`

#### class `Constraint`

| Field | Type | Default |
| --- | --- | --- |
| `requirement` | `Requirement` | `required` |
| `quantity` | `Quantity` | `required` |
| `condition` | `str` | `required` |
| `interval` | `Interval` | `required` |
| `slots` | `tuple[str, ...]` | `required` |
| `certainties` | `tuple[str, ...]` | `required` |

- `describe(self) -> str`

**Check rules**

- `consistency.conflict` (`conflicts`): requirements on one quantity leave a value that meets them all.
- `consistency.child_looser` (`child_looser`): a child allows no values its parent excludes (same quantity).
- `consistency.issue_due` (`issue_due`): open issues are not past their due date.

**Functions**

#### `convert`

```python
def convert(number: float, unit: str | None, quantity: Quantity) -> float | None
```

A number in the slot's unit, expressed in the quantity's unit; None if it cannot be.

#### `allowed`

```python
def allowed(slot: ValueSlot, quantity: Quantity) -> Interval | None
```

The interval a slot allows, or None when it is not comparable.

#### `condition_key`

```python
def condition_key(slot: ValueSlot, reference: str) -> str
```

The condition as compared: the reference-language text, normalised; a condition written
only in another language is kept apart from both the unconditioned and the referenced ones.

#### `constraints`

```python
def constraints(vault: Vault) -> Iterator[Constraint | tuple[Requirement, str, str]]
```

Per current requirement and (quantity, condition): the combined interval of its slots.
A requirement whose own slots on one quantity allow no value is yielded as a problem tuple.

#### `ancestor_sets`

```python
def ancestor_sets(vault: Vault) -> dict[str, set[str]]
```

Each node reference with itself and all its ancestors.

**Helpers**

- `same(first: float, second: float) -> bool`
- `condition_label(condition: str) -> str`
- `listed(names: list[str], limit: int = 5) -> str`

### `qingsong.checks.documents`

Source: [`src/qingsong/checks/documents.py`](../src/qingsong/checks/documents.py)

Document rules: release entries and their tags (docs/SPEC.md §5.5, §10).

**Check rules**

- `documents.release` (`release_entries`): release entries are well formed, in order, and made by approvers.
- `documents.release_tag` (`release_tags`): release tags mark a commit that holds the same release entry.

**Helpers**

- `documents(context: Context) -> Iterator[Document]`
- `release_problems(context: Context, document: Document) -> Iterator[tuple[str, str | None]]`

## Modules: changing the record

### `qingsong.operations`

Source: [`src/qingsong/operations.py`](../src/qingsong/operations.py)

Recorded changes: adopt, new, revise, supersede, withdraw, approve, confirm, renumber, init
(docs/SPEC.md §8, §9, §11). Every operation validates the result, rewrites the stamp, writes the
file atomically and reads it back to verify the stamp.

**Classes**

#### class `OperationError` (Exception)

**Functions**

#### `translation_entries`

```python
def translation_entries(
    vault: Vault,
    record: RecordBase,
    status: str,
    person: str | None,
    today: date,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]
```

Translation state for bilingual fields present in both languages.

With `existing`, entries whose source hash is still current are kept as they are; only stale
or missing entries are (re)written. A review (`status` reviewed) also marks current machine
entries as reviewed by the person; current reviews by others are kept.

#### `literal_blocks`

```python
def literal_blocks(value: Any) -> Any
```

Write new multi-line texts as literal blocks (|-) instead of quoted strings with escapes.
Texts that a literal block cannot hold exactly (control or separator characters such as tab,
vertical tab, carriage return, U+0085 and U+2028, trailing spaces, leading indentation or a
final newline) are left as they are.

#### `stamped`

```python
def stamped(data: CommentedMap) -> tuple[RecordBase, str]
```

Write normative hash and stamp into the data; return the record and its serialized text.

The text is parsed again and must give the same stamp, so that nothing is lost in writing.

#### `adopt`

```python
def adopt(
    root: Path,
    file: Path,
    person: str,
    summary: str,
    event: str = 'imported',
    translation: str = 'machine',
    via: str | None = None,
    today: date | None = None,
) -> RecordBase
```

Take a hand-written record file (without bookkeeping fields) into the record.

#### `numbers_in_use`

```python
def numbers_in_use(vault: Vault, record_type: str, namespace: str | None) -> set[int]
```

Numbers used in the working tree (loaded or not) and on every main reference.

#### `new_requirement`

```python
def new_requirement(
    root: Path,
    namespace: str,
    title: str,
    statement: str,
    person: str,
    level: str | None = None,
    via: str | None = None,
    today: date | None = None,
) -> RecordBase
```

Allocate the next ID; title and statement are given in the node's origin language.

#### `draft_identity`

```python
def draft_identity(
    vault: Vault,
    record_type: str,
    data: CommentedMap,
    slug: str | None,
) -> str
```

The ID a new record of this type receives (docs/SPEC.md §5.3, §6.1).

#### `new_from_draft`

```python
def new_from_draft(
    root: Path,
    record_type: str,
    draft: Path,
    person: str,
    slug: str | None = None,
    via: str | None = None,
    today: date | None = None,
) -> RecordBase
```

Allocate an ID for a draft file (all fields but the ID and bookkeeping), write the record
where its ID says, and record its creation. The draft file itself is left untouched.

#### `revise`

```python
def revise(
    root: Path,
    record_id: str,
    change_class: str,
    summary: str,
    person: str,
    decision: str | None = None,
    translation: str = 'unchanged',
    to_draft: bool = False,
    via: str | None = None,
    today: date | None = None,
) -> RecordBase
```

Record a change already made to a record's file: bump the revision (and the normative
revision for a 'value' change), rewrite the stamp, and append a history event. Refuses
'editorial' when values, the level or the verification methods changed (`normative_hash`), a
baselined requirement without a decision record, and an agreed one without a reason.

#### `supersede`

```python
def supersede(
    root: Path,
    old_id: str,
    successors: list[str],
    summary: str,
    person: str,
    decision: str | None = None,
    via: str | None = None,
    today: date | None = None,
) -> RecordBase
```

Mark a record as superseded by one or more current successors of the same type (several for a
split). An agreed or baselined requirement needs a decision record.

#### `withdraw`

```python
def withdraw(
    root: Path,
    record_id: str,
    reason: str,
    person: str,
    decision: str | None = None,
    via: str | None = None,
    today: date | None = None,
) -> RecordBase
```

Withdraw a record: it stays in the vault with lifecycle 'withdrawn' and its ID is retired. An
agreed or baselined requirement needs a decision record.

#### `approve`

```python
def approve(
    root: Path,
    record_id: str,
    to: str,
    person: str,
    ref: str,
    via: str | None = None,
    today: date | None = None,
) -> RecordBase
```

Record an approver's maturity decision on a requirement: 'agreed' records what was approved
(normative revision and text hash); 'draft' reopens an agreed or baselined requirement.
Agents call it only on an approver's instruction.

#### `confirm`

```python
def confirm(
    root: Path,
    child_id: str,
    parent_id: str,
    person: str,
    via: str | None = None,
    today: date | None = None,
) -> RecordBase
```

Clear a suspect link: record that the child was reviewed against its parent's current
normative revision.

#### `renumber`

```python
def renumber(
    root: Path,
    old_id: str,
    new_id: str,
    person: str,
    via: str | None = None,
    today: date | None = None,
) -> RecordBase
```

Move a record that has not reached main to a free ID, rewriting every reference.

All changes are prepared and verified in memory before any file is written.

#### `init_vault`

```python
def init_vault(path: Path, code: str, name: str) -> Path
```

Create an empty vault at PATH: configuration, people, glossary, root tree file and the record
folders.

**Helpers**

- `today_date(today: date | None) -> date`
- `require_person(vault: Vault, person: str) -> None`
- `require_record(vault: Vault, record_id: str) -> RecordBase`
- `require_current(record: RecordBase) -> None`
- `require_recorded(record: RecordBase) -> None`
- `validate(data: dict[str, Any]) -> RecordBase`
- `languages_of(vault: Vault) -> tuple[str, str]`
- `translation_fields(vault: Vault, record_type: str) -> list[str]`
- `history_event(revision: int, today: date, person: str, event: str, summary: str, change_class: str | None = None, decision: str | None = None, via: str | None = None) -> dict[str, Any]`
- `load_round_trip(path: Path) -> CommentedMap`
- `serialize(data: CommentedMap) -> str`
- `write_atomically(path: Path, text: str, exclusive: bool = False) -> None`
- `finish(path: Path, data: CommentedMap, exclusive: bool = False) -> RecordBase`
- `edit(vault: Vault, record_id: str, change: Callable[[CommentedMap, RecordBase], None], allow_unrecorded: bool = False) -> RecordBase`
- `allocate_number(vault: Vault, record_type: str, namespace: str | None) -> int`
- `expected_level(vault: Vault, namespace: str) -> str`
- `text_origin_for(vault: Vault, node_reference: str) -> str`

### `qingsong.review`

Source: [`src/qingsong/review.py`](../src/qingsong/review.py)

Review items (docs/SPEC.md §5.6): issues raised from check findings, proposed fixes, and the
approver's decisions. Every change goes through the recorded operations of `operations`.

**Functions**

#### `untracked_findings`

```python
def untracked_findings(vault: Vault, rules: set[str] | None = None) -> list[Finding]
```

Warnings on records that no open issue tracks and no acceptance covers.

#### `raise_from_checks`

```python
def raise_from_checks(
    root: Path,
    person: str,
    rules: set[str] | None = None,
    group: bool = False,
    owner: str | None = None,
    via: str | None = None,
    today: date | None = None,
) -> list[RecordBase]
```

Raise issues for check warnings that no issue tracks yet: one per finding, or with `group`
one per rule covering all its records. Kind and title come from the rule.

#### `raise_issue`

```python
def raise_issue(
    root: Path,
    kind: str,
    title: dict[str, str],
    description: dict[str, str],
    records: list[str],
    person: str,
    owner: str | None = None,
    due: str | None = None,
    via: str | None = None,
    rule: str | None = None,
    today: date | None = None,
) -> RecordBase
```

An issue written by hand. With `rule`, it tracks that rule's findings on its records,
for example several records grouped under one proposed fix.

#### `checked_changes`

```python
def checked_changes(
    vault: Vault,
    changes: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]
```

Validate proposed changes against the current records and add their base hashes.

#### `propose`

```python
def propose(
    root: Path,
    issue_id: str,
    person: str,
    summary: dict[str, str],
    changes: list[dict[str, Any]],
    change_class: str = 'editorial',
    via: str | None = None,
    today: date | None = None,
) -> RecordBase
```

Add a proposed fix to an open issue. Without changes, it proposes keeping the text.

#### `set_field`

```python
def set_field(data: CommentedMap, field: str, language: str, text: str) -> None
```

Set one language of a prose field. A new top-level field goes after the prose field that
precedes it in the reading order, so the file keeps its usual layout.

#### `accept`

```python
def accept(
    root: Path,
    issue_id: str,
    number: int,
    person: str,
    decision: str | None = None,
    via: str | None = None,
    today: date | None = None,
) -> list[RecordBase]
```

Apply an accepted proposal and close its issue. Every target is checked before any file
is written, and written files are restored if a later step fails.

#### `reject`

```python
def reject(
    root: Path,
    issue_id: str,
    number: int,
    person: str,
    reason: dict[str, str],
    via: str | None = None,
    today: date | None = None,
) -> RecordBase
```

Reject a proposal (an approver) or withdraw it (its author), with a reason.

#### `close`

```python
def close(
    root: Path,
    issue_id: str,
    outcome: str,
    resolution: dict[str, str],
    person: str,
    via: str | None = None,
    today: date | None = None,
) -> RecordBase
```

Close an issue without accepting a proposal: answered, withdrawn, or fixed by a separate
recorded revision. Approvers only.

**Helpers**

- `require_issue(vault: Vault, issue_id: str, open_only: bool = True) -> Issue`
- `require_approver(vault: Vault, person: str) -> None`
- `write_new_issue(vault: Vault, data: dict[str, Any], number: int) -> RecordBase`
- `issue_skeleton(kind: str, title: dict[str, str], description: dict[str, str], records: list[str], person: str, today: date, rule: str | None = None, owner: str | None = None, due: str | None = None, via: str | None = None) -> dict[str, Any]`
- `find_proposal(issue: Issue, number: int) -> Proposal`
- `stale_changes(vault: Vault, proposal: Proposal) -> list[str]`
- `close_issue_data(data: CommentedMap, old: Issue, outcome: str, resolution: dict[str, str], person: str, today: date, via: str | None, accepted_number: int | None = None, accepted_hashes: dict[str, str] | None = None) -> None`

### `qingsong.decisions_file`

Source: [`src/qingsong/decisions_file.py`](../src/qingsong/decisions_file.py)

Decisions files (docs/SPEC.md §5.6): one reviewer's decisions on proposed fixes, saved from the
review page and applied all or nothing through `review.reject` and `review.accept`.

**Classes**

#### class `ReviewDecision` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `issue` | `str` | `required` |
| `proposal` | `int` | `required` |
| `decision` | `Literal['accept', 'reject']` | `required` |
| `note` | `str` | `''` |
| `proposal_hash` | `str` | `required` |
| `decision_record` | `str \| None` | `None` |

#### class `DecisionsFile` (StrictModel)

| Field | Type | Default |
| --- | --- | --- |
| `format` | `Literal['qingsong-decisions/1']` | `required` |
| `project` | `str` | `required` |
| `decided_by` | `str` | `required` |
| `saved` | `datetime \| None` | `None` |
| `decisions` | `list[ReviewDecision]` | `required` |

#### class `AppliedDecision`

| Field | Type | Default |
| --- | --- | --- |
| `decision` | `ReviewDecision` | `required` |
| `written` | `list[RecordBase]` | `required` |

#### class `Applied`

| Field | Type | Default |
| --- | --- | --- |
| `decided_by` | `str` | `required` |
| `branch` | `str \| None` | `required` |
| `started_branch` | `bool` | `required` |
| `kept` | `Path` | `required` |
| `applied` | `list[AppliedDecision]` | `[]` |

**Functions**

#### `problems_with`

```python
def problems_with(vault: Vault, decisions: DecisionsFile) -> list[str]
```

Every reason the file cannot be applied, found without writing anything.

#### `target_problems`

```python
def target_problems(vault: Vault, entry: ReviewDecision, proposal: Proposal) -> list[str]
```

What `review.accept` would refuse in the records it writes.

#### `apply`

```python
def apply(
    root: Path,
    path: Path,
    via: str | None = None,
    today: date | None = None,
) -> Applied
```

Apply a decisions file: check every decision, then apply them all or none. On the main
branch the changes move to a new review branch. Nothing is committed.

**Helpers**

- `read_decisions(path: Path) -> DecisionsFile`
- `kept_path(root: Path, person: str, today: date) -> Path`
- `review_branch_name(root: Path, person: str, today: date) -> str`
- `language_of(text: str) -> str`

### `qingsong.slots`

Source: [`src/qingsong/slots.py`](../src/qingsong/slots.py)

Moving numbers from a requirement's prose into value slots without changing its meaning
(docs/SPEC.md §5.2, "Converting between the forms").

A move is accepted only when the slot renders the replaced literal the same way, up to a short,
named list of formatting differences, and when no relation word sits just outside the literal.
The rest of the statement is untouched by construction. The approval is re-bound only if it was
current before, and the history event records the normative hash before and after, which is
what `integrity.against` accepts.

**Functions**

#### `glued`

```python
def glued(text: str, start: int, end: int) -> str | None
```

The character that ties the span to a larger expression, if any.

#### `display`

```python
def display(text: str) -> str
```

Rendered slot text as a reader sees it: Markdown escapes removed.

#### `normalized`

```python
def normalized(text: str) -> str
```

The comparison form of a literal or a rendered slot.

#### `protected_spans`

```python
def protected_spans(text: str) -> list[tuple[int, int]]
```

References, links, footnotes, code and mathematics: never rewritten by a move.

#### `slot_values`

```python
def slot_values(
    root: Path,
    record_id: str,
    slots: dict[str, Any],
    person: str,
    via: str | None = None,
    today: date | None = None,
    dry_run: bool = False,
) -> tuple[Requirement, list[tuple[str, str, str]], list[str]]
```

Move numbers into slots. Returns the record and, per language, the statement before and
after. Refuses, with every reason, unless each move provably keeps the meaning.

#### `rebind_accepted_wording`

```python
def rebind_accepted_wording(
    root: Path,
    record_id: str,
    old_review: str,
    new_review: str,
    person: str,
    via: str | None,
    today: date,
) -> list[str]
```

Carry an "accepted as written" decision over a move, as the approval is carried: only where
it covered the record's text before the move (docs/SPEC.md §5.2, §5.6).

**Helpers**

- `overlaps(first: tuple[int, int], second: tuple[int, int]) -> bool`

### `qingsong.wording`

Source: [`src/qingsong/wording.py`](../src/qingsong/wording.py)

Words next to a number or a value slot (docs/SPEC.md §5.2).

Relation words say what a number is: a limit, a range, an approximation. Any comparative ("longer
than", "长于") counts, through "than" and "于". Qualifiers say what it
counts: per item, in total, on average. The slot move refuses a literal with either kind just
outside it, so that the slot's data says what the sentence says. The check for a relation said
twice ("at least ≥ 40 %") uses the relation words only.

**Functions**

#### `neighbour_problem`

```python
def neighbour_problem(
    text: str,
    start: int,
    end: int,
    language: str,
    qualifiers: bool = True,
) -> str | None
```

A relation word (and, with `qualifiers`, a qualifier) right before or after the span.

### `qingsong.release`

Source: [`src/qingsong/release.py`](../src/qingsong/release.py)

Releases of documents and their change summaries (docs/SPEC.md §5.5).

A release is prepared on a branch (`prepare`), reviewed and merged like any other change, and then
tagged at the commit of the main branch that first contains it (`tag_release`). The change summary
(`changes`) compares a document between two states of the vault.

**Classes**

#### class `RecordChange`

| Field | Type | Default |
| --- | --- | --- |
| `record` | `str` | `required` |
| `type` | `str` | `required` |
| `title` | `dict[str, str]` | `required` |
| `kind` | `str` | `required` |
| `fields` | `list[str]` | `[]` |
| `before` | `dict[str, Any]` | `{}` |
| `after` | `dict[str, Any]` | `{}` |
| `events` | `list[dict[str, Any]]` | `[]` |
| `maturity` | `list[str \| None] \| None` | `None` |
| `lifecycle` | `list[str] \| None` | `None` |
| `superseded_by` | `list[str]` | `[]` |
| `aliases_added` | `list[str]` | `[]` |
| `aliases_removed` | `list[str]` | `[]` |
| `history_rewritten` | `bool` | `False` |

#### class `SectionChange`

| Field | Type | Default |
| --- | --- | --- |
| `key` | `str \| None` | `required` |
| `status` | `str` | `required` |
| `title_before` | `dict[str, str] \| None` | `None` |
| `title_after` | `dict[str, str] \| None` | `None` |
| `blocks_before` | `list[dict]` | `[]` |
| `blocks_after` | `list[dict]` | `[]` |

#### class `ChangeSummary`

| Field | Type | Default |
| --- | --- | --- |
| `document` | `str` | `required` |
| `since` | `str` | `required` |
| `since_ref` | `str` | `required` |
| `until` | `str` | `required` |
| `approximate` | `bool` | `required` |
| `added` | `list[str]` | `[]` |
| `removed` | `list[str]` | `[]` |
| `moved` | `dict[str, list[str]]` | `{}` |
| `moved_within` | `dict[str, list[str \| None]]` | `{}` |
| `revised` | `list[RecordChange]` | `[]` |
| `bookkeeping` | `list[RecordChange]` | `[]` |
| `sections` | `list[SectionChange]` | `[]` |
| `front_matter` | `list[str]` | `[]` |

- `is_empty(self) -> bool`
- `as_dict(self) -> dict[str, Any]`
- `bookkeeping_groups(self) -> dict[str, list[str]]`
  Bookkeeping changes grouped by what happened: note → record IDs.
- `lines(self) -> list[str]`

**Functions**

#### `outline_records`

```python
def outline_records(blocks: list[Block]) -> list[str]
```

Requirement and figure IDs in outline order.

#### `kept_order`

```python
def kept_order(order: list[str], accounted: set[str]) -> list[str]
```

A section's block order without the records already reported as added, removed or moved.

#### `outline_places`

```python
def outline_places(blocks: list[Block], key: str | None = None) -> dict[str, str | None]
```

Record ID → key of the section that holds it (None outside any section).

#### `section_contents`

```python
def section_contents(
    blocks: list[Block],
    key: str | None = None,
    title: Any = None,
    found: dict | None = None,
) -> dict[str | None, dict]
```

Section key → its title, its own text, table and definitions blocks, and the order of all
its blocks (records by ID, sections by key, others by content). Blocks outside any section
are kept under the key None; a repeated key gets a suffix (structure.outline reports it).

#### `release_blockers`

```python
def release_blockers(vault: Vault, document: Document) -> list[str]
```

Why the document cannot be released from this state: errors on the document or on the
records of its outline, integrity errors anywhere, and translations not reviewed.

#### `prepare`

```python
def prepare(
    root: Path,
    document_id: str,
    version: str,
    person: str,
    summary: dict[str, str],
    release_date: date | None = None,
    note: dict[str, str] | None = None,
    via: str | None = None,
    today: date | None = None,
) -> Document
```

Write the release entry (step 1 of §5.5). Refuses with every reason at once.

#### `find_release_commit`

```python
def find_release_commit(root: Path, document_path: str, version: str) -> str
```

The commit on the main branch's first-parent history that first contains the release.

#### `tag_release`

```python
def tag_release(
    root: Path,
    document_id: str,
    version: str,
    at: str | None = None,
) -> tuple[str, str]
```

Create the release tag (step 2 of §5.5); return the tag and the commit it marks.

A release made with qingsong is tagged at the commit that introduced it. A release made before
qingsong is tagged at the commit given with `at`, where the record was verified against the
issued document.

#### `resolve_since`

```python
def resolve_since(
    root: Path,
    document: Document,
    since: str | None,
    until_commit: str | None = None,
) -> tuple[str, str, bool]
```

(git reference, label, approximate) of the earlier state to compare with. With an end
commit, only states strictly before it qualify as the default.

#### `changes`

```python
def changes(
    root: Path,
    document_id: str,
    since: str | None = None,
    until: str | None = None,
) -> ChangeSummary
```

Summarise what changed in a document between two states: by default from its latest tagged
release to the working tree; `since` and `until` take a version or a git reference.

#### `summaries_since_last_release`

```python
def summaries_since_last_release(root: Path, later: Vault) -> 'dict[str, ChangeSummary | str]'
```

For every document of a working-tree vault: its changes since its last tagged release, or
why there is none. Each earlier state is read once, however many documents share it.

**Helpers**

- `parse_version(version: str) -> tuple[int, ...]`
- `tag_name(document_id: str, version: str) -> str`
- `require_document(vault: Vault, document_id: str) -> Document`
- `on_main(root: Path, document_path: str, version: str) -> bool`
- `has_release(text: str | None, version: str) -> bool`
- `compact_ids(record_ids: list[str]) -> str`
- `status_lines(change: RecordChange, prefix: str = '               ') -> list[str]`
- `dump(record: RecordBase, name: str) -> Any`
- `compare_record(old: RecordBase, new: RecordBase) -> RecordChange | None`
- `compare(document_id: str, earlier: Vault, later: Vault, since: str, since_ref: str, until: str, approximate: bool) -> ChangeSummary`
- `changes_between(root: Path, document_id: str, later: Vault, since: str | None, until_label: str, until_commit: str | None) -> ChangeSummary`

### `qingsong.gitutil`

Source: [`src/qingsong/gitutil.py`](../src/qingsong/gitutil.py)

Read earlier versions of a vault through the git command line (docs/SPEC.md §6.1).

**Classes**

#### class `GitError` (Exception)

**Functions**

#### `main_refs`

```python
def main_refs(root: Path) -> list[str]
```

Every main reference that exists (remote and local), so that neither is overlooked.

#### `commit_of`

```python
def commit_of(root: Path, ref: str) -> str | None
```

The commit a reference points to, or None if it does not exist.

#### `head_commit`

```python
def head_commit(root: Path) -> str | None
```

The commit checked out, or None outside a git repository.

#### `is_dirty`

```python
def is_dirty(root: Path) -> bool
```

Uncommitted changes, untracked files included, inside the vault folder.

#### `current_branch`

```python
def current_branch(root: Path) -> str | None
```

The checked-out branch; None for a detached HEAD or outside a repository.

#### `switch_to_new_branch`

```python
def switch_to_new_branch(root: Path, name: str) -> None
```

Start a branch at HEAD and check it out; uncommitted changes come along.

#### `uncommitted_paths`

```python
def uncommitted_paths(root: Path) -> list[Path]
```

Absolute paths of uncommitted changes, untracked files included, inside the vault folder.

#### `first_parent_history`

```python
def first_parent_history(root: Path, ref: str, relative_path: str) -> list[tuple[str, str]]
```

(commit, the file's path in it) for the commits on the first-parent history of REF that
touched the file, oldest first. Renames are followed.

#### `export_tree`

```python
def export_tree(root: Path, ref: str, target: Path) -> None
```

Write the vault folder as stored at REF into TARGET, from the raw objects: no checkout, no
archive filters and no line-ending conversion (docs/SPEC.md §5.5).

**Helpers**

- `run_git(root: Path, *arguments: str) -> CompletedProcess`
- `is_repository(root: Path) -> bool`
- `ref_exists(root: Path, ref: str) -> bool`
- `files_at(root: Path, ref: str, folder: str) -> list[str]`
- `read_at(root: Path, ref: str, relative_path: str) -> str | None`
- `branch_exists(root: Path, name: str) -> bool`
- `tag_exists(root: Path, tag: str) -> bool`
- `create_tag(root: Path, tag: str, commit: str, message: str) -> None`
- `is_ancestor(root: Path, commit: str, ref: str) -> bool`

## Modules: outputs

### `qingsong.render.model`

Source: [`src/qingsong/render/model.py`](../src/qingsong/render/model.py)

What the renderers need from a vault: document numbering, links, trees and graphs.

**Classes**

#### class `Numbering`

| Field | Type | Default |
| --- | --- | --- |
| `sections` | `dict[str, str]` | `{}` |
| `figures` | `dict[str, str]` | `{}` |
| `requirements` | `dict[str, str]` | `{}` |
| `titles` | `dict[str, dict[str, str]]` | `{}` |

**Functions**

#### `number_document`

```python
def number_document(document: Document) -> Numbering
```

Section and requirement numbers share one counter per level (2.1, 2.1.1, 2.1.2 …), as in the
formal documents; figures are numbered per top-level section (3.1, 3.2 …). A requirement or figure
placed twice keeps its first number (the outline check reports the repeat).

#### `tree_data`

```python
def tree_data(vault: Vault) -> dict | None
```

The product tree as nested dicts, with requirement counts per node and subtree.

**Helpers**

- `documents_of(vault: Vault) -> list[Document]`
- `requirement_documents(vault: Vault) -> dict[str, list[str]]`
- `children_of(vault: Vault) -> dict[str, list[str]]`

### `qingsong.render.text`

Source: [`src/qingsong/render/text.py`](../src/qingsong/render/text.py)

The text format of docs/SPEC.md §5.4 (a Markdown subset), shared by the HTML and Word renderers.

Block level: paragraphs, bullet lists (`- `) and numbered lists (`1. `), nested by indentation.
Inline: `**bold**`, `*italic*`, `` `code` ``, `~sub~`, `^sup^`, `$math$`, `[text](url)`, `[[ID]]`
and `[[DOC#key]]` references, and backslash escapes. Open values (bracketed text, TBD, TBC, 待定, 待确认) are marked.
The inline rules follow pandoc where the two could differ: emphasis, sub- and superscript and math
need non-space characters inside their markers, so "2 * 3", "~45 m" and "$5" stay as written.

**Types**

- `Resolver`: `Callable[[str, str | None, str], tuple[str, str | None]]`

**Classes**

#### class `ListItem`

| Field | Type | Default |
| --- | --- | --- |
| `level` | `int` | `required` |
| `ordered` | `bool` | `required` |
| `text` | `str` | `required` |

#### class `Block`

| Field | Type | Default |
| --- | --- | --- |
| `kind` | `str` | `required` |
| `text` | `str` | `''` |
| `items` | `list[ListItem]` | `[]` |

**Functions**

#### `parse_blocks`

```python
def parse_blocks(text: str) -> list[Block]
```

Paragraphs and lists. A list may start right after a paragraph line, items continue on
indented lines, blank lines between items keep one list, and indentation nests items.

#### `number`

```python
def number(value: float) -> str
```

Plain decimal notation with a thousands separator, a true minus sign, and a power of ten
only for extreme magnitudes.

#### `format_slot`

```python
def format_slot(slot, language: str) -> str
```

A value slot as it reads in a document: relation, value, tolerance, unit and certainty.
The result is escaped so that it is never read as markup.

#### `substitute_slots`

```python
def substitute_slots(text: str, values: dict, language: str) -> str
```

Replace {slot} placeholders with formatted values; unknown names stay visible.

**Helpers**

- `inline(text: str, language: str, resolve: Callable[[str, str | None, str], tuple[str, str | None]]) -> str`
- `blocks(text: str, language: str, resolve: Callable[[str, str | None, str], tuple[str, str | None]]) -> str`
- `unit_label(unit: str | None) -> str`

### `qingsong.render.html`

Source: [`src/qingsong/render/html.py`](../src/qingsong/render/html.py)

Static HTML site (docs/SPEC.md §12.1): works offline from a folder; no external resources.

**Classes**

#### class `Site`

- `href(self, record_id: str, prefix: str) -> str`
- `resolver(self, prefix: str, document: Document | None)`
- `text(
    self,
    value: dict | None,
    prefix: str,
    document: Document | None = None,
    block: bool = True,
    values: dict | None = None,
) -> Markup`
- `caption(
    self,
    figure: Figure,
    number: str | None,
    prefix: str,
    document: Document | None,
) -> Markup`
  One block per language: the numbered label followed by the caption in that language.
- `slot_text(self, slot) -> str`
- `issue_state(self, issue: Issue) -> str`
- `open_issues_of(self, record_id: str) -> list[Issue]`
- `proposal_hash(self, proposal: Proposal) -> str`
- `open_proposals(self, issue: Issue) -> list[Proposal]`
- `issue_documents(self, issue: Issue) -> list[str]`
- `record_link(self, record_id: str, prefix: str) -> str`
  A requirement inside a document opens at its place in the document.
- `change_diff(self, change: ProposedChange, language: str) -> Markup`
  The difference as a reader sees it: references shown by their labels.
- `form(self, record: Requirement) -> str`
- `numbers_in_text(self, record: Requirement) -> bool`
- `form_hint(self, record: Requirement) -> str`
- `is_text(self, value: Any) -> bool`
  Bilingual text: a non-empty mapping from language codes to strings.
- `field_diff(
    self,
    before: Any,
    after: Any,
    language: str,
    values_before: dict | None = None,
    values_after: dict | None = None,
) -> Markup`
  Word-level difference of one language of a changed text field. With value slots given,
  the texts are compared as a reader sees them, with the values filled in.
- `filled(self, text: str, values: dict, language: str) -> str`
- `as_text(self, value: Any) -> str`
- `blocks_text(self, blocks: list[dict], language: str) -> str`
  The readable text of a section's own blocks, for a before/after difference.
- `blocks_diff(self, before: list[dict], after: list[dict], language: str) -> Markup`
- `plain(self, value: dict | None, language: str = 'en') -> str`
- `render(self, template: str, target: str, prefix: str, **context) -> None`
- `build(self) -> Path`
- `copy_images(self) -> None`
- `flow_data(self, requirements: list[Requirement]) -> dict`
- `write_search_index(self, requirements: list[Requirement]) -> None`

**Functions**

#### `diff_markup`

```python
def diff_markup(old: str, new: str) -> Markup
```

Word-level difference (character level for Chinese): deleted text struck, new text marked.

#### `script_json`

```python
def script_json(data) -> str
```

JSON that is safe inside a <script> element.

#### `change_summaries`

```python
def change_summaries(vault: Vault) -> 'dict[str, ChangeSummary | str]'
```

Each document's changes since its last tagged release, or why there is no summary.

#### `render_site`

```python
def render_site(vault: Vault, output: Path) -> Path
```

Write the static HTML site into `output` (replaced) and return the path of its index page.

### `qingsong.render.word`

Source: [`src/qingsong/render/word.py`](../src/qingsong/render/word.py)

Word output (docs/SPEC.md §12.2): a formal document generated from the records.

The layout follows the MUST requirement documents: cover, change record, responsibilities, table of
contents, acronyms, reference documents, publications, then numbered sections with bilingual
requirement entries (requirement, rationale, notes, suggestions, verification), figures with numbered
captions in both languages, and tables. A reference document (`templates/reference.docx` in the vault)
supplies the styles; its body is discarded.

**Classes**

#### class `WordRenderer`

- `clear_body(self) -> None`
- `bullet_numbering(self) -> int | None`
  A numbering instance for bullet lists, based on the template's first bullet definition.
- `label(self, target: str, key: str | None, language: str) -> str`
  The same labels as the HTML site: sections and figures are numbered by the document
  that holds them, also when that is another document.
- `font(self, run, monospace: bool = False) -> None`
- `runs(
    self,
    paragraph,
    text: str,
    language: str,
    bold: bool = False,
    italic: bool = False,
) -> None`
- `add_run(
    self,
    paragraph,
    text: str,
    bold: bool = False,
    italic: bool = False,
    subscript: bool = False,
    superscript: bool = False,
    monospace: bool = False,
)`
- `paragraph(
    self,
    text: str = '',
    language: str = 'en',
    style: str | None = None,
    level: int | None = None,
    bold: bool = False,
    align = None,
)`
- `style_names(self) -> set[str]`
- `bulletize(self, paragraph, level: int) -> None`
- `localized_paragraphs(
    self,
    value: dict | None,
    level: int | None,
    languages = ('en', 'zh'),
) -> None`
  Each language's paragraphs in turn; list items become bullets one level deeper (numbered
  items keep their number as text).
- `bilingual_title(self, value: dict) -> str`
- `table(
    self,
    header: list[str],
    rows: list[list[str]],
    languages: list[str] | None = None,
)`
- `cover(self) -> None`
- `front_matter(self) -> None`
- `table_of_contents(self) -> None`
  A paragraph that marks where the table of contents goes; `fill_table_of_contents`
  replaces it once every heading is known.
- `fill_table_of_contents(self) -> None`
  A TOC field whose result already lists every heading of levels 1 to 3, each linked to a
  bookmark on its heading. Word shows it as it is, without asking to update fields when the
  document opens. Page numbers appear when the field is updated (F9, or Update Field); with
  `update_fields_on_open`, Word instead rebuilds the table on opening, after asking.
- `request_field_update(self) -> None`
- `page_break(self) -> None`
- `heading(self, text: str, level: int) -> None`
- `outline(self, blocks: list[Block], depth: int) -> None`
- `requirement(self, record: Requirement, depth: int) -> None`
- `figure(self, record: Figure) -> None`
- `caption_paragraphs(self, caption: dict) -> None`
- `definitions(self, terms: list[str]) -> None`
- `header_and_footer(self) -> None`
- `properties(self) -> None`
  Document properties: the document number, title, version and, for an issued copy, the
  release tag (docs/SPEC.md §5.5).
- `render(self, output: Path) -> Path`

**Functions**

#### `check_package`

```python
def check_package(path: Path) -> list[str]
```

Problems that make Word report unreadable content: directory entries in the ZIP package and
non-integer table widths.

**Helpers**

- `render_docx(vault: Vault, document_id: str, output: Path, version: str | None = None, update_fields_on_open: bool = False, tag: str | None = None) -> Path`

### `qingsong.export`

Source: [`src/qingsong/export.py`](../src/qingsong/export.py)

JSON export of the record, with an index of value slots (docs/SPEC.md §12.3).

**Functions**

#### `export_vault`

```python
def export_vault(vault: Vault, commit: str | None, dirty: bool | None) -> dict[str, Any]
```

The JSON export (SPEC §12.3): header, every record, the flattened tree, and one entry per
value slot of a current requirement with its interval.

**Helpers**

- `bound(number: float) -> float | None`
- `interval_entry(interval: Interval | None) -> dict[str, Any] | None`
- `canonical_entry(slot: ValueSlot, quantity: Quantity | None) -> dict[str, Any] | None`
- `value_entries(vault: Vault) -> list[dict[str, Any]]`
- `node_entries(vault: Vault) -> list[dict[str, Any]]`
