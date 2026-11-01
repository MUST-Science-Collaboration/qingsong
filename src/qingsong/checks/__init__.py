"""Check registry and runner (docs/SPEC.md §10)."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
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
    from qingsong.checks import change, content, integrity, structure  # noqa: F401  (registers rules)

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
        findings,
        key=lambda finding: (
            severity_order[finding.severity],
            finding.rule,
            finding.record or "",
            finding.file or "",
        ),
    )


def all_rule_summaries() -> dict[str, str]:
    from qingsong.checks import change, content, integrity, structure  # noqa: F401

    summaries = dict(load_rules)
    summaries.update({rule_id: entry.summary for rule_id, entry in rules.items()})
    return dict(sorted(summaries.items()))


def relative_file(vault: Vault, record_id: str) -> str | None:
    path: Path | None = vault.files.get(record_id)
    return vault.relative(path) if path else None
