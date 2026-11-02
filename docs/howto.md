# How to use qingsong

This guide is for everyone who works on a project's requirements with qingsong: the scientists and
engineers who write and approve them, and the AI agents who do most of the editing. It explains the
ideas, the rules and the everyday workflow, then walks through the common tasks with real commands
and their real output.

The examples use the fictional DEMO project that ships with qingsong (`examples/demo`). Its detector
subsystem is `INS-DET`; `alice` is an approver and `bob` is not. Commands are run inside the vault
folder. `--by` names the person in `people.yaml` responsible for a change. An agent working for that
person adds `--via` and its own name.

## 1. The idea

- **The record is the reference.** Each requirement, quantity, issue, decision and document
  definition is a small YAML file in a git repository, the **vault**. Documents, the HTML site and
  Word files, are generated from it and never edited by hand. A Word file is a snapshot.
- **Every change is recorded.** When a file changes, a qingsong command records the change: it
  raises the record's revision, appends a history event, and writes a stamp, a hash of the content.
  A change made without recording it is caught.
- **Every change is checked.** `qingsong check` runs more than forty rules: structure, flow-down, units,
  conflicting values, translations, approvals and unrecorded edits.
- **People decide, agents prepare.** Agents draft requirements and propose fixes. Approvers, listed
  in `people.yaml`, approve requirements, decide on proposals, release documents and permit merges.

## 2. Concepts

### The vault

```
qingsong.toml        project code, languages, levels
people.yaml          people, their languages, and who approves
glossary.yaml        acronyms, terms and symbols in both languages
tree/                the product tree: one file per top-level system
quantities/          named physical quantities, e.g. detector.read_noise
requirements/INS/    requirements of the INS system, one file each
issues/ decisions/   review items and recorded decisions
documents/           document definitions: outline, front matter, releases
figures/ sources/    figure records with their images; cited external documents
reviews/             decisions files saved from the review page
```

### Records and IDs

| Record | ID example | Holds |
| --- | --- | --- |
| Requirement | `INS-DET-REQ-002` | one "shall" statement, values, rationale, flow-down links, verification |
| Quantity | `detector.read_noise` | a named quantity with its dimension and canonical unit |
| Issue | `ISS-0001` | an open question, TBD/TBC value or check finding, with proposed fixes |
| Decision | `DEC-0001` | who decided what, when and why |
| Document | `DEMO-INS-DET-RD` | the outline of a generated document and its releases |
| Figure, source, condition, interface, verification, waiver | `INS-DET-FIG-001`, `SRC-…`, … | see the [specification](SPEC.md#53-other-record-types) |

An ID is **permanent** once its record reaches the main branch. It is never changed, reused or
deleted. A record that is no longer wanted is *withdrawn*, or *superseded* by a successor; it stays in
the vault. Earlier numbers, such as a row number in an old Word document or a vendor's number, are kept
as **aliases**.

### Levels, namespaces and flow-down

Requirements have a **level**: `science`, `survey`, `system`, `element`, `subsystem` or `component`.
The ID's prefix, its **namespace**, says where the requirement was issued: `DEMO-SRV` for the
project's survey requirements, `INS-SYS` for the instrument's own requirements, `INS-DET` for the
detector subsystem.

A requirement **derives from** a parent at a higher level. The link stores the parent's normative
revision, so that when the parent's meaning changes the link becomes **suspect** until someone
reviews the child. A requirement below `science` without a parent must cite a decision that justifies
it. Otherwise it is flagged as **TBJ**, "to be justified".

### Values live in slots

Numbers that matter are kept in **value slots**, not in the prose. Both languages then show the same
number, and checks can compare values across requirements:

```yaml
statement:
  en: The detector gain shall vary by {gain_variation} during one night.
  zh: 探测器增益在一夜内的变化应为{gain_variation}。
values:
  gain_variation:
    quantity: detector.gain_variation
    relation: lt              # eq, le, lt, ge, gt, range or approx
    value: 0.5
    unit: percent
    certainty: firm           # firm, provisional, tbc or tbd
```

This renders as "The detector gain shall vary by < 0.5 % during one night." A provisional value is
shown with its value and unit in brackets, as in "≥ [90 %]". Provisional, TBC and TBD values must be tracked by an open issue.
A slot may also carry a `goal` on the better side of its limit, a `tolerance`, or a `condition`.

A requirement with at least one slot is **quantitative**. One without slots is **qualitative**, which
is fine as long as it is verifiable. Numbers that only give context, such as dates and standard
numbers, may stay in the prose.

### Four separate kinds of status

| Axis | Values | Meaning |
| --- | --- | --- |
| Maturity | `concept`, `draft`, `agreed`, `baselined` | how settled the requirement is |
| Lifecycle | `current`, `superseded`, `withdrawn` | whether it is in force |
| Certainty, per value | `firm`, `provisional`, `tbc`, `tbd` | how settled each number is |
| Verification status | `planned`, `predicted`, `compliant`, … | how far evidence shows compliance |

A `concept` may be incomplete and in one language. A `draft` is a verifiable statement in both
languages. An `agreed` requirement carries an approver's approval of its current meaning.

### Kinds of change

| Class | For example | Effect |
| --- | --- | --- |
| `editorial` | wording, punctuation, translation, rationale | children and approval unaffected, unless the approved wording changed |
| `value` | a value, tolerance, unit or condition; the level or verification method | new normative revision; links from children become suspect; the approval becomes stale |
| `reallocate` | a different `allocated_to` node | documents affected; same ID |
| new intent | the requirement asks for something different | a new requirement; `qingsong supersede` the old one |

### Two languages

English is the reference language, and the title, statement, rationale and verification criteria
also exist in Chinese from `draft` upward. `text_origin` records which language a requirement was
written in. For each translated field, qingsong tracks whether the translation was written by an agent
(`machine`) or checked by a person (`reviewed`). Editing the original makes the translation stale. A
document can only be released when everything in it has a reviewed, current translation.

### Issues, proposals and decisions

An **issue** is a review item: a TBD value, a wording problem found by a check, a question. It carries
a label, an owner and **proposals**, which are fixes with the exact new text in both languages, or a
proposal to keep the text as written. An approver accepts or rejects proposals, usually on the HTML
**review page**, which saves the decisions as a file for `qingsong issue apply`.

### Documents and releases

A **document** record lists its sections and the requirements and figures in each. qingsong generates
it as an HTML page and as a Word file. A **release** is prepared on a branch, merged, and then tagged
in git (`release/<DOC>/<version>`). The issued Word copy of any release can be rebuilt from its tag.

## 3. The rules

1. **Never work on `main`.** Every change starts on a branch and reaches `main` by a merge that an
   approver permits.
2. **Record every change.** After editing a file, run `qingsong revise` (or the command that made
   the change). Never edit `revision`, `normative_revision`, `normative_hash`, `history`, `stamp` or
   `approval` by hand.
3. **No errors on commit.** Run `qingsong check` after every change and before every commit.
4. **IDs are permanent.** Never rename, renumber or delete a record that is on `main`; supersede or
   withdraw it.
5. **One "shall" per requirement, and no vague words.** "Adequate", "as far as possible" and the like
   are flagged (`content.writing`).
6. **Numbers that matter go in slots.** Every non-firm value is tracked by an open issue.
7. **Both languages from `draft` on.** Respect the language a requirement was written in: never
   regenerate the original from its translation.
8. **People decide.** Only approvers approve, accept or reject proposals, and release. Agents run
   these commands only on an approver's explicit instruction, and apply an approver's decisions file
   unchanged.

## 4. Setting up

**Install.** qingsong needs Python 3.11 or newer and [uv](https://docs.astral.sh/uv/). In the vault
repository:

```bash
uv add "qingsong @ git+https://github.com/MUST-Science-Collaboration/qingsong"
uv run qingsong --version
```

To develop the engine and a vault side by side, point the dependency at a local checkout instead:
`qingsong = { path = "../qingsong", editable = true }` under `[tool.uv.sources]`.

**Create a vault.**

```bash
qingsong init my-vault --code DEMO --name "Demo Survey Telescope"
```

This writes `qingsong.toml`, `people.yaml`, `glossary.yaml` and the root tree file `tree/DEMO.yaml`.
Record folders appear as records are added. Then list the people:

```yaml
people:
  alice:
    name: Alice Example
    organization: Demo Observatory
    github: alice-example
    languages: [en, zh]
    approver: true
```

**Check on every commit.** Add a hook to the vault's `.pre-commit-config.yaml`, and run the same check
in CI against the main branch (`qingsong check --against origin/main`):

```yaml
  - repo: local
    hooks:
      - id: qingsong_check
        name: qingsong check
        entry: uv run --frozen qingsong check
        language: system
        pass_filenames: false
        always_run: true
```

## 5. The everyday workflow

1. **Branch:** `git switch -c feature/gain-stability`.
2. **Edit:** create a record with `qingsong new`, or change a record's YAML file.
3. **Record:** `qingsong revise ID --class … --summary … --by …`.
4. **Check:** `qingsong check`. Fix every error; a warning is either fixed or tracked by an issue.
5. **Commit**, and ask an approver to review the branch. The HTML site's changes and review pages
   show what changed.
6. **Approve and merge:** the approver approves the requirements (`qingsong approve`) and permits the
   merge.
7. **Release** a document when it is ready (§6.10).

## 6. Worked examples

### 6.1 Write a new requirement

Allocate the next ID in the namespace. qingsong writes a `concept` requirement:

```console
$ qingsong new requirement --namespace INS-DET --title "Gain stability" \
    --statement "The detector gain shall vary by less than 0.5 % during one night." --by alice
created INS-DET-REQ-002 (revision 1)
```

The value needs a quantity. Write `quantities/detector.gain_variation.yaml` and take it in with
`adopt`, which adds the revision, history and stamp:

```yaml
id: detector.gain_variation
type: quantity
title: {en: Detector gain variation, zh: 探测器增益变化}
dimension: "[]"
unit: percent
lifecycle: current
```

```console
$ qingsong adopt quantities/detector.gain_variation.yaml --event created \
    --summary "quantity for the gain stability requirement" --by alice
adopted detector.gain_variation (revision 1)
```

Now complete the requirement in its file: the Chinese title and statement, the value slot (as in §2),
the rationale, the parent link and the verification:

```yaml
rationale:
  en: Flat fields are taken once per night; a stable gain keeps them valid until the next set.
  zh: 平场每夜拍摄一次；增益稳定可使其在下一组平场之前保持有效。
derives_from:
  - {id: INS-SYS-REQ-001, normative_revision: 1}
verification:
  methods: [test]
  criteria:
    en: Gain measured from flat fields at the start and end of three nights.
    zh: 在三个夜晚的开始和结束时由平场测量增益。
```

Record it. The values changed, so the class is `value`. `--to-draft` raises it from `concept` to
`draft`, and `--translation updated` records that the Chinese was written by an agent:

```console
$ qingsong revise INS-DET-REQ-002 --class value --to-draft --translation updated \
    --summary "first full draft: value in a slot, Chinese, rationale and verification" \
    --by alice --via demo-agent
revised INS-DET-REQ-002 (revision 2)
```

Then add it to its document (§6.9), check, and commit.

### 6.2 Read and fix a finding

Each finding names the rule, the record, what is wrong, and a fix. Editing a file without recording
the change gives:

```console
$ qingsong check
ERROR   change.unrecorded                  DEMO-INS-DET-RD: content changed since the last recorded change
        fix: qingsong revise DEMO-INS-DET-RD --class editorial|value|reallocate --summary …
1 errors, 0 warnings, 0 notes
```

`qingsong revise` refuses the wrong class. Recording a changed value as `editorial` gives
`error: values, level or verification methods changed: this is a 'value' change, not editorial`.

Severities:
- **Errors** block a commit.
- **Warnings** must be fixed, or tracked by an issue (§6.8). A tracked warning names its issue.
- **Notes** are information.

### 6.3 Keep the translation current

Changing the English text makes its translation stale:

```console
WARNING change.translation                 INS-DET-REQ-002: statement: the en text changed after the translation was made
        fix: update the other language, then revise with --translation updated|reviewed
```

Update the Chinese if needed, then record who wrote or checked it. `updated` means an agent wrote it;
`reviewed` means a person who reads both languages checked it:

```console
$ qingsong revise INS-DET-REQ-002 --class editorial --translation reviewed \
    --summary "Chinese statement checked against the new English" --by alice
revised INS-DET-REQ-002 (revision 4)
```

### 6.4 Approve a requirement

An approver approves the current meaning and wording. `--ref` says where the decision was made:

```console
$ qingsong approve INS-DET-REQ-002 --to agreed --by alice --ref "design review 2026-11-03"
approved INS-DET-REQ-002 (revision 5)
```

`approve --to draft` reopens an agreed requirement. Agents run `approve` only when an approver
tells them to.

### 6.5 Change a value

Edit the value in the file, then record a `value` change with a summary that states the reason:

```console
$ qingsong revise INS-SYS-REQ-001 --class value \
    --summary "Throughput raised to 45 % after the coating study (DEC-0001)." --by alice
revised INS-SYS-REQ-001 (revision 3)
$ qingsong check
ERROR   change.approval                    INS-SYS-REQ-001: approval covers normative revision 1, the requirement is at 2
        fix: approve again, or reopen as draft
ERROR   change.suspect_link                INS-DET-REQ-002: INS-SYS-REQ-001 changed (normative revision 1 → 2) since this link was confirmed
        fix: review, then qingsong confirm INS-DET-REQ-002 INS-SYS-REQ-001
WARNING change.suspect_link                INS-OPT-REQ-001: INS-SYS-REQ-001 changed (normative revision 1 → 2) since this link was confirmed
        fix: review, then qingsong confirm INS-OPT-REQ-001 INS-SYS-REQ-001
2 errors, 1 warnings, 0 notes
```

The approval no longer covers the new meaning, and every child must be reviewed against the new
value. A suspect link is an error for an agreed child and a warning for a draft one. After review:

```console
$ qingsong approve INS-SYS-REQ-001 --to agreed --by alice --ref "design review 2026-11-03"
$ qingsong confirm INS-DET-REQ-002 INS-SYS-REQ-001 --by alice
```

A baselined requirement also needs `--decision DEC-…`.

### 6.6 Move a number from the prose into a slot

Requirements imported from Word documents often carry their numbers in the text. `qingsong slot`
moves them into slots without changing the meaning. It checks that the slot renders the same words it
replaces, so the approval stays valid. Write the slots, with `replaces` giving the exact text in each
language. A relation word such as "no more than" belongs to the replaced text:

```yaml
mass:
  quantity: detector.mass
  relation: le
  value: 120
  unit: kg
  certainty: firm
  replaces:
    en: no more than 120 kg
```

```console
$ qingsong slot INS-DET-REQ-003 --file slots.yaml --by alice --dry-run
would move values of INS-DET-REQ-003:
  en before: The detector assembly shall weigh no more than 120 kg.
  en after:  The detector assembly shall weigh {mass}.
```

Run it again without `--dry-run` to write. When the move would change what the sentence says, it is
refused with the reason. Changing what is required is an ordinary `value` revision (§6.5).

### 6.7 Supersede or withdraw

When a requirement must ask for something different, write a new one and supersede the old:

```console
$ qingsong supersede INS-DET-REQ-001 --with INS-DET-REQ-004 --summary "split by readout mode" --by alice
```

Repeat `--with` for a split. A requirement that is no longer needed is withdrawn:
`qingsong withdraw ID --reason … --by …`. Both need `--decision DEC-…` for an agreed or baselined
requirement. Links to the old record must then point to its successor (`structure.lifecycle`).

### 6.8 Review: issues, proposals and decisions

**Raise issues** for warnings that nothing tracks yet. Each gets a label and lists its records:

```console
$ qingsong issue raise --from-checks --by alice
```

Use `--group` for one issue per rule. To raise one by hand, use `--kind question --title … --description … --record ID`.

**Propose a fix.** Anyone in `people.yaml` may propose. The file gives the new text in both languages:

```yaml
summary: {en: State how the read noise is combined, zh: 说明读出噪声的合并方式}
change_class: editorial
changes:
  - record: INS-DET-REQ-001
    field: notes
    text:
      en: Measured at the operating temperature in the slow readout mode, as the median over all amplifiers.
      zh: 在工作温度下以慢读出模式测量，取所有放大器的中位数。
```

```console
$ qingsong issue propose ISS-0001 --file proposal.yaml --by bob
proposed in ISS-0001 (revision 3)
```

`--keep --summary …` proposes keeping the text as written.

**Decide on the review page.** Run `qingsong render html site` and open `site/review.html`. It shows
each issue with its label and records, and each proposal as a word-level difference in both languages.
1. Mark proposals Accept or Reject, with a note if you like.
2. Choose your name under "You are".
3. Press **Save decisions**. The page downloads a decisions file, such as
   `decisions_DEMO_2026-11-03_alice.yaml`.

**Apply the file**, yourself or through an agent:

```console
$ qingsong issue apply ~/Downloads/decisions_DEMO_2026-11-03_alice.yaml
```

It checks every decision before writing anything, and applies all of them or none. It refuses a
proposal that changed after you read it. On `main`, it starts the branch `review/<date>-<person>`. It
keeps the file in `reviews/`. It commits nothing: commit and merge as usual.

From the command line, `qingsong issue accept ISS --proposal N` and
`qingsong issue reject ISS --proposal N --reason …` do the same one at a time. Accepting a proposal
applies its text, records the revision and closes the issue.

### 6.9 Put a requirement in a document

Add a `requirement` block to the right section of the document's `outline` and record the change:

```yaml
      blocks:
        - requirement: INS-DET-REQ-001
        - requirement: INS-DET-REQ-002
```

```console
$ qingsong revise DEMO-INS-DET-RD --class editorial --summary "outline: add INS-DET-REQ-002" --by alice
```

No check yet reminds you of a requirement that is in no document, so add new requirements as you
create them. Refer to other records in text with `[[ID]]`, and to a section with `[[DOC#key]]`;
qingsong numbers figures and sections itself.

### 6.10 Release a document

1. **Prepare on a branch.** An approver gives the summary in both languages:

   ```console
   $ qingsong release prepare DEMO-INS-DET-RD 1.1 --by alice \
       --summary-en "Adds gain stability (INS-DET-REQ-002)." \
       --summary-zh "增加增益稳定性需求（INS-DET-REQ-002）。"
   prepared DEMO-INS-DET-RD 1.1 (revision 3); after the merge run qingsong release tag DEMO-INS-DET-RD 1.1
   ```

   It refuses while the document has errors, or while anything in it lacks a reviewed translation.
   It prints the changes since the previous release.
2. **Merge** the branch, with the approver's permission.
3. **Tag** on `main`. The tag marks the commit that brought the release in, whatever followed it:

   ```console
   $ qingsong release tag DEMO-INS-DET-RD 1.1
   tagged dc5343c14479 as release/DEMO-INS-DET-RD/1.1; publish it with: git push origin release/DEMO-INS-DET-RD/1.1
   ```

   Pushing the tag is a separate step, with permission.
4. **Issue the copy.** `qingsong render docx DEMO-INS-DET-RD issued.docx --release 1.1` renders the
   document as it was at the tag. `qingsong release changes DEMO-INS-DET-RD` lists what changed since
   the latest release. The HTML site shows the same as "Changes since v1.1".

### 6.11 Read, share and analyse

- `qingsong render html site`: the static site. Open `site/index.html`. It works offline, so it can
  be shared as a folder or a CI artifact.
- `qingsong show ID`, `qingsong list --type requirement --node INS-DET`, `qingsong find TEXT`: look
  things up from the terminal.
- `qingsong export json --output record.json`: every record and an index of all values with their
  intervals, for analysis code. `--release DOC/VERSION` exports the numbers behind an issued document.

## 7. For agents

**Before you start.**
- Read the vault's `AGENTS.md`.
- Work on a branch. Find the vault root (`qingsong.toml`), or pass `--vault`.

**For every change.**
- Edit the file, record it with the right class, and run `qingsong check`. Pass `--via` with your
  name, and `--by` with the person you work for.
- Use `--json` to read results. `qingsong check --json` gives
  `{"errors", "warnings", "tracked", "findings": [{"rule", "severity", "message", "record", "file", "fix", "issue"}]}`.
- **Exit codes.** `check` exits with 1 when there is an error. Any command exits with 2 when it refuses,
  printing `{"error": "…"}` with `--json`.
- **Quoting.** In YAML, quote a text that starts with `[` or `{`, for example `zh: "[[ID]]的…"`.
  Otherwise YAML reads it as a list or a mapping.

**Never, unless an approver tells you to:**
- approve;
- accept, reject or close a proposal;
- prepare or tag a release;
- merge, push, or delete a branch.

**Never:**
- edit the recorded fields by hand;
- reuse or renumber an ID that is on `main`;
- regenerate a requirement's original-language text from its translation.

**When an approver hands you a decisions file:**
- apply it unchanged with `qingsong issue apply FILE --via AGENT`;
- commit the changes together with the copy kept in `reviews/`;
- if it is refused, report the listed problems; do not work around them.

**When a command refuses,** read its message: it names the fix. Report anything you cannot resolve,
rather than editing around the check.

## 8. Troubleshooting

| Message | Meaning | What to do |
| --- | --- | --- |
| `content changed since the last recorded change` | a file was edited without recording it | `qingsong revise ID --class … --summary …` |
| `this is a 'value' change, not editorial` | values, level or verification method changed | record it as `--class value` |
| `approval covers normative revision 1, the requirement is at 2` | the meaning changed after approval | approve again, or reopen as draft |
| `… changed … since this link was confirmed` | a parent's meaning changed | review the child, then `qingsong confirm CHILD PARENT` |
| `the en text changed after the translation was made` | the translation is stale | update it, then `revise --translation updated` or `reviewed` |
| `no parent and no justifying decision: to be justified (TBJ)` | a requirement has no parent | add `derives_from`, or `justified_by` with a decision |
| `… is not valid YAML …; quote texts that start with [ or {` | YAML read a text as a list or mapping | put the text in quotes |
| `… is out of date …; propose again` | the text changed after the proposal was made | write a new proposal |
| `… has changed since the review page was made` | a proposal changed after you read it | render the page again and decide again |
| `… is not an approver (people.yaml)` | only approvers may do this | ask an approver |

## 9. Where next

- [API reference](api.md): every command and check rule, and the code for those who change qingsong.
- [Specification](SPEC.md): the full design and the decisions behind it.
- [Contributor rules](../AGENTS.md): the rules for changing qingsong itself.
