# qingsong 青松

qingsong keeps a project's requirements as **engineering records**: small text files in a git repository, checked for consistency on every change, and rendered as the documents people read (HTML first, Word for formal distribution).

It is being rebuilt for the MUltiplexed Survey Telescope (MUST). The project's own records live in a separate, private repository; this repository holds only the engine and fictional examples.

> **Status: rebuild in progress (version 0.2.0.dev0).** Phase 0 (specification, reset, tooling) is under way. The package does not yet read or check records. The earlier version 0.1 is preserved under the git tag `legacy-0.1`.

## What it will do

- **Permanent identifiers.** A requirement such as `INS-DET-REQ-012` keeps its ID for life; it is never renumbered or reused. Earlier or vendor numbers are kept as aliases.
- **Rules for change.** Editorial changes, value changes and changes of intent are distinguished; obsolete requirements are withdrawn, never deleted; dependent requirements are flagged when a parent changes.
- **Levels from science to components.** Science, survey, system, element, subsystem and component requirements, linked by flow-down.
- **Maturity on separate axes.** How settled a requirement is, whether it is in force, how certain each value is, and how far verification has progressed.
- **Continuous checks.** Every change is checked for structure, flow-down, units, conflicting values and unrecorded edits.
- **Two languages.** English is the reference; the main content is also kept in Chinese.
- **Generated documents.** A static HTML site for reading and tracing requirements, and Word files for formal releases.

The design is in [docs/SPEC.md](docs/SPEC.md).

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
