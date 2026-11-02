"""Check registry and runner (docs/SPEC.md §10)."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from pathlib import Path

from qingsong.findings import Finding, severity_order
from qingsong.vault import Vault


@dataclass(frozen=True)
class Context:
    vault: Vault
    against: str | None


@dataclass(frozen=True)
class Rule:
    rule_id: str
    summary: str
    function: Callable[[Context], Iterable[Finding]]


rules: dict[str, Rule] = {}

load_rules = {
    "integrity.config": "the configuration file qingsong.toml is valid",
    "integrity.yaml_syntax": "every file is valid YAML",
    "integrity.schema": "every record matches its schema; no unknown fields",
    "integrity.missing_file": "people.yaml and glossary.yaml exist",
    "integrity.path_mismatch": "each file is stored where its ID says",
    "structure.tree_root": "the tree has exactly one root file",
    "structure.tree_parent": "top-level branches hang from the root",
    "structure.node_code": "node codes are valid, not reserved, and unique within their system",
}


def rule(rule_id: str, summary: str) -> Callable:
    def register(function: Callable[[Context], Iterable[Finding]]) -> Callable:
        rules[rule_id] = Rule(rule_id, summary, function)
        return function

    return register


def by_maturity(maturity: str | None, concept: str, draft: str, agreed: str, baselined: str) -> str:
    return {"concept": concept, "draft": draft, "agreed": agreed, "baselined": baselined}.get(
        maturity or "draft", draft
    )


def run(
    vault: Vault, against: str | None = None, selected: set[str] | None = None
) -> list[Finding]:
    from qingsong.checks import (  # noqa: F401  (registers rules)
        change,
        consistency,
        content,
        documents,
        integrity,
        structure,
    )

    context = Context(vault, against)
    findings = [
        finding for finding in vault.load_findings if selected is None or finding.rule in selected
    ]
    for rule_id, entry in rules.items():
        if selected is not None and rule_id not in selected:
            continue
        try:
            findings.extend(entry.function(context))
        except Exception as error:  # a broken rule must not hide the other findings
            findings.append(
                Finding(
                    rule_id,
                    "error",
                    f"the rule could not run: {error!r}",
                    fix="report this as a qingsong bug, with the record that caused it",
                )
            )
    return sorted(
        apply_review(vault, findings),
        key=lambda finding: (
            severity_order[finding.severity],
            finding.rule,
            finding.record or "",
            finding.file or "",
        ),
    )


def apply_review(vault: Vault, findings: list[Finding]) -> list[Finding]:
    """Findings that an issue covers (docs/SPEC.md §5.6): an open issue tracking the rule on the
    record is named; an acceptance as written turns the finding into a note while the record's
    review hash is unchanged."""
    from qingsong.hashing import review_hash
    from qingsong.schema import Issue

    tracked: dict[tuple[str, str], str] = {}
    accepted: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for record in vault.records.values():
        if not isinstance(record, Issue) or not record.rule:
            continue
        if record.status == "open":
            for target in record.records:
                tracked.setdefault((record.rule, target), record.id)
        elif record.outcome == "accepted_as_written":
            for target, digest in (record.accepted or {}).items():
                accepted.setdefault((record.rule, target), []).append((record.id, digest))
    result = []
    for finding in findings:
        key = (finding.rule, finding.record or "")
        target = vault.records.get(finding.record or "")
        if key in accepted and target is not None and finding.severity != "error":
            current = review_hash(target)
            covering = [issue_id for issue_id, digest in accepted[key] if digest == current]
            if covering:
                issue_id = covering[0]
                finding = replace(
                    finding,
                    severity="info",
                    message=f"{finding.message} (accepted as written in {issue_id})",
                    issue=issue_id,
                )
                result.append(finding)
                continue
        if key in tracked:
            finding = replace(finding, issue=tracked[key])
        result.append(finding)
    return result


def all_rule_summaries() -> dict[str, str]:
    from qingsong.checks import (  # noqa: F401
        change,
        consistency,
        content,
        documents,
        integrity,
        structure,
    )

    summaries = dict(load_rules)
    summaries.update({rule_id: entry.summary for rule_id, entry in rules.items()})
    return dict(sorted(summaries.items()))


def relative_file(vault: Vault, record_id: str) -> str | None:
    path: Path | None = vault.files.get(record_id)
    return vault.relative(path) if path else None
