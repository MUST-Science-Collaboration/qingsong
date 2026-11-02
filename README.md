# qingsong 青松

qingsong keeps a project's requirements as **engineering records**: small text files in a git repository, checked for consistency on every change, and rendered as the documents people read (HTML first, Word for formal distribution).

It is being rebuilt for the MUltiplexed Survey Telescope (MUST). The project's own records live in a separate, private repository; this repository holds only the engine and fictional examples.

> **Status: rebuild in progress (version 0.2.0.dev0).**
> - Done:
>   - the core engine: records, IDs, change recording and checks, including consistency of values;
>   - the HTML site with the review page and the changes since each release;
>   - Word output;
>   - releases, prepared on a branch and tagged after the merge;
>   - JSON export.
> - Next: interfaces and conditions in the site, and CI for record repositories.
> - The earlier version 0.1 is preserved under the git tag `legacy-0.1`.

## What it does

- **Permanent identifiers.** A requirement such as `INS-DET-REQ-012` keeps its ID for life; it is never renumbered or reused. Earlier or vendor numbers are kept as aliases.
- **Rules for change.** Editorial changes, value changes and changes of intent are distinguished; obsolete requirements are withdrawn, never deleted; dependent requirements are flagged when a parent changes.
- **Levels from science to components.** Science, survey, system, element, subsystem and component requirements, linked by flow-down.
- **Maturity on separate axes.** How settled a requirement is, whether it is in force, how certain each value is, and how far verification has progressed.
- **Continuous checks.** Every change is checked for structure, flow-down, units, conflicting values and unrecorded edits.
- **Two languages.** English is the reference; the main content is also kept in Chinese.
- **Generated documents.** A static HTML site for reading and tracing requirements, and Word files for formal releases.
- **Review.** What the checks find is raised as labelled issues and highlighted in the HTML documents. Fixes are proposed with word-level differences in both languages and decided by an approver from one review page.

The design is in [docs/SPEC.md](docs/SPEC.md).

## Commands

```bash
qingsong check                                  # run every rule
qingsong new requirement --namespace INS-DET …  # allocate the next ID
qingsong new decision --file draft.yaml --by PERSON   # also issue, interface, condition, source…
qingsong revise ID --class editorial --summary … --by PERSON   # record a change
qingsong approve ID --to agreed --by PERSON --ref …
qingsong issue raise --from-checks --by PERSON  # one issue per untracked finding
qingsong issue propose ISS-0001 --file fix.yaml --by PERSON
qingsong issue accept ISS-0001 --proposal 1 --by APPROVER
qingsong render html site                       # open site/index.html, then site/review.html
qingsong render docx DOC out.docx --version 1.2
qingsong release changes DOC                    # what changed since the last tagged release
qingsong release prepare DOC 1.2 --by APPROVER --summary-en … --summary-zh …   # on a branch
qingsong release tag DOC 1.2                    # after the merge; tags the commit that brought it in
qingsong render docx DOC out.docx --release 1.2 # the issued copy, from the release tag
qingsong export json --output record.json       # all records and an index of value slots
```

`qingsong --help` lists all commands; every command accepts `--json`. A fictional demo vault is in [examples/demo](examples/demo).

## Development

```bash
uv sync                      # create the environment
uv run pytest                # run the tests
uv run pre-commit install    # lint and format on commit
uv run qingsong --version
```

## Name

Named after the astronomer Yu Ching-Sung (余青松, Yu Qingsong), a Tsinghua alumnus.

## License

See [LICENSE](LICENSE).
