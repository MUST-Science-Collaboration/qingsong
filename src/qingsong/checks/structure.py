"""Structure rules: tree codes, allocation, levels, flow-down, lifecycle links, aliases."""

from collections.abc import Iterator

from qingsong import ids
from qingsong.checks import Context, by_maturity, relative_file, rule
from qingsong.findings import Finding
from qingsong.schema import Requirement


def requirements(context: Context) -> Iterator[Requirement]:
    for record in context.vault.records.values():
        if isinstance(record, Requirement):
            yield record


@rule("structure.node_code", "node codes are valid, not reserved, and unique within their system")
def node_codes(context: Context) -> Iterator[Finding]:
    vault = context.vault
    top_codes: dict[str, str] = {}
    for info in vault.nodes.values():
        code = info.node.node
        if not ids.node_code_pattern.match(code):
            yield Finding(
                "structure.node_code",
                "error",
                f"code {code!r} must match [A-Z][A-Z0-9]{{1,5}}",
                file=info.file,
            )
        if code in ids.reserved_codes:
            yield Finding(
                "structure.node_code", "error", f"code {code} is a reserved word", file=info.file
            )
        if info.depth == 1:
            if code in top_codes:
                yield Finding(
                    "structure.node_code",
                    "error",
                    f"top-level code {code} used twice",
                    file=info.file,
                )
            top_codes[code] = info.file
    if vault.config:
        suffixes = {namespace.split("-")[-1] for namespace in vault.config.top_namespaces}
        for info in vault.nodes.values():
            if info.depth >= 1 and info.node.node in suffixes:
                yield Finding(
                    "structure.node_code",
                    "error",
                    f"code {info.node.node} collides with a top-level namespace suffix",
                    file=info.file,
                )


@rule("structure.allocation", "a requirement is allocated to one active product node")
def allocation(context: Context) -> Iterator[Finding]:
    vault = context.vault
    for requirement in requirements(context):
        info = vault.nodes.get(requirement.allocated_to)
        if info is None:
            continue
        if info.node.kind != "product":
            yield Finding(
                "structure.allocation",
                "error",
                f"allocated to {requirement.allocated_to}, a {info.node.kind} node",
                record=requirement.id,
                file=relative_file(vault, requirement.id),
                fix="allocate requirements to product nodes only",
            )
        elif info.node.status == "retired" and requirement.lifecycle == "current":
            yield Finding(
                "structure.allocation",
                "warning",
                f"allocated to the retired node {requirement.allocated_to}",
                record=requirement.id,
                file=relative_file(vault, requirement.id),
            )


@rule("structure.namespace", "an ID's namespace exists in the tree or configuration")
def namespace_known(context: Context) -> Iterator[Finding]:
    vault = context.vault
    namespaces = vault.namespaces()
    context_nodes = {
        reference for reference, info in vault.nodes.items() if info.node.kind == "context"
    }
    for record in vault.records.values():
        namespace = ids.namespace_of(record.type, record.id)
        if namespace is None:
            continue
        if record.type in ("requirement", "figure"):
            if namespace in namespaces:
                continue
            if namespace in {reference for reference in vault.nodes}:
                continue
        elif record.type == "condition":
            if namespace in context_nodes:
                continue
        elif record.type == "interface":
            if namespace in vault.nodes and vault.nodes[namespace].depth == 1:
                continue
        else:
            continue
        yield Finding(
            "structure.namespace",
            "error",
            f"namespace {namespace} is not defined",
            record=record.id,
            file=relative_file(vault, record.id),
            fix="namespaces come from product nodes and qingsong.toml [top_namespaces]",
        )


@rule("structure.level", "levels are configured, ordered downward, and match the namespace")
def levels(context: Context) -> Iterator[Finding]:
    vault = context.vault
    if vault.config is None:
        return
    rank = vault.config.level_rank
    top_namespaces = vault.config.top_namespaces
    for requirement in requirements(context):
        file = relative_file(vault, requirement.id)
        if requirement.level not in rank:
            yield Finding(
                "structure.level",
                "error",
                f"unknown level {requirement.level!r}",
                record=requirement.id,
                file=file,
            )
            continue
        for link in requirement.derives_from:
            parent = vault.records.get(link.id)
            if isinstance(parent, Requirement) and parent.level in rank:
                if rank[parent.level] >= rank[requirement.level]:
                    yield Finding(
                        "structure.level",
                        "error",
                        f"derives from {parent.id} at level {parent.level}, which is not higher "
                        f"than {requirement.level}",
                        record=requirement.id,
                        file=file,
                        fix="a requirement derives only from requirements at higher levels",
                    )
        namespace = ids.namespace_of("requirement", requirement.id)
        if namespace in top_namespaces:
            expected = {top_namespaces[namespace]}
        elif namespace and namespace.endswith("-SYS"):
            expected = {"element"}
        else:
            expected = {"subsystem", "component"}
        if expected <= set(rank) and requirement.level not in expected:
            yield Finding(
                "structure.level",
                "warning",
                f"level {requirement.level} differs from what namespace {namespace} implies "
                f"({' or '.join(sorted(expected))})",
                record=requirement.id,
                file=file,
            )


@rule("structure.justification", "a parentless requirement is justified (otherwise TBJ)")
def justification(context: Context) -> Iterator[Finding]:
    vault = context.vault
    if vault.config is None or not vault.config.levels:
        return
    top_level = vault.config.levels[0].name
    for requirement in requirements(context):
        if requirement.derives_from or requirement.lifecycle != "current":
            continue
        file = relative_file(vault, requirement.id)
        severity = by_maturity(requirement.maturity, "info", "warning", "error", "error")
        if requirement.level == top_level:
            if not requirement.justification:
                yield Finding(
                    "structure.justification",
                    severity,
                    f"a {top_level} requirement needs a justification",
                    record=requirement.id,
                    file=file,
                )
        elif not requirement.justified_by:
            # Approval concerns a requirement's content; a missing parent stays a tracked
            # warning until the requirement enters a baseline, where traceability is complete.
            yield Finding(
                "structure.justification",
                by_maturity(requirement.maturity, "info", "warning", "warning", "error"),
                "no parent and no justifying decision: to be justified (TBJ)",
                record=requirement.id,
                file=file,
                fix="add derives_from, or justified_by pointing to a decision",
            )


@rule("structure.cycle", "derives_from has no cycles")
def cycles(context: Context) -> Iterator[Finding]:
    vault = context.vault
    graph = {
        requirement.id: [link.id for link in requirement.derives_from]
        for requirement in requirements(context)
    }
    state: dict[str, int] = {}
    reported: set[frozenset[str]] = set()

    def visit(node: str, stack: list[str]) -> Iterator[Finding]:
        state[node] = 1
        stack.append(node)
        for parent in graph.get(node, []):
            if state.get(parent) == 1:
                cycle = stack[stack.index(parent) :]
                key = frozenset(cycle)
                if key not in reported:
                    reported.add(key)
                    yield Finding(
                        "structure.cycle",
                        "error",
                        " → ".join([*cycle, parent]),
                        record=parent,
                        file=relative_file(vault, parent),
                    )
            elif state.get(parent) is None and parent in graph:
                yield from visit(parent, stack)
        stack.pop()
        state[node] = 2

    for node in graph:
        if state.get(node) is None:
            yield from visit(node, [])


@rule("structure.lifecycle", "superseded records name successors; links point to current records")
def lifecycle(context: Context) -> Iterator[Finding]:
    vault = context.vault
    for record in vault.records.values():
        file = relative_file(vault, record.id)
        if record.lifecycle == "superseded" and not record.superseded_by:
            yield Finding(
                "structure.lifecycle",
                "error",
                "superseded without successors",
                record=record.id,
                file=file,
            )
        if record.lifecycle != "superseded" and record.superseded_by:
            yield Finding(
                "structure.lifecycle",
                "error",
                f"superseded_by set but lifecycle is {record.lifecycle}",
                record=record.id,
                file=file,
            )
    for requirement in requirements(context):
        if requirement.lifecycle != "current":
            continue
        for link in [*requirement.derives_from, *requirement.constrained_by]:
            target = vault.records.get(link.id)
            if target is not None and target.lifecycle != "current":
                successors = (
                    f" (successors: {', '.join(target.superseded_by)})"
                    if target.superseded_by
                    else ""
                )
                yield Finding(
                    "structure.lifecycle",
                    by_maturity(requirement.maturity, "warning", "warning", "error", "error"),
                    f"links to {link.id}, which is {target.lifecycle}{successors}",
                    record=requirement.id,
                    file=relative_file(vault, requirement.id),
                    fix="re-point the link to a current record and confirm it",
                )


@rule("structure.alias", "aliases do not collide with IDs or overlap within a document")
def aliases(context: Context) -> Iterator[Finding]:
    vault = context.vault
    seen: dict[tuple[str, str, str], list[tuple[str, str | None, str | None]]] = {}
    for record in vault.records.values():
        for alias in record.aliases:
            if alias.id in vault.records:
                yield Finding(
                    "structure.alias",
                    "error",
                    f"alias {alias.id} is also a record ID",
                    record=record.id,
                    file=relative_file(vault, record.id),
                )
            key = (alias.kind, alias.document, alias.id)
            for other_id, start, end in seen.get(key, []):
                if other_id != record.id and ranges_overlap(
                    start, end, alias.from_version, alias.to_version
                ):
                    yield Finding(
                        "structure.alias",
                        "error",
                        f"alias {alias.id} in {alias.document} overlaps with {other_id}",
                        record=record.id,
                        file=relative_file(vault, record.id),
                        fix="give each alias the version range in which it applied",
                    )
            seen.setdefault(key, []).append((record.id, alias.from_version, alias.to_version))


def version_key(version: str | None) -> tuple:
    if version is None:
        return ()
    parts = []
    for part in version.lstrip("v").replace("-", ".").split("."):
        parts.append((0, int(part), "") if part.isdigit() else (1, 0, part))
    return tuple(parts)


def ranges_overlap(
    start_a: str | None, end_a: str | None, start_b: str | None, end_b: str | None
) -> bool:
    low_a, high_a = version_key(start_a), version_key(end_a)
    low_b, high_b = version_key(start_b), version_key(end_b)
    a_before_b = bool(high_a) and bool(low_b) and high_a < low_b
    b_before_a = bool(high_b) and bool(low_a) and high_b < low_a
    return not (a_before_b or b_before_a)


@rule("structure.ends", "interfaces join two different nodes; conditions belong to context nodes")
def ends(context: Context) -> Iterator[Finding]:
    vault = context.vault
    for record in vault.records.values():
        file = relative_file(vault, record.id)
        if record.type == "interface" and record.owner_end == record.other_end:
            yield Finding(
                "structure.ends",
                "error",
                "both ends are the same node",
                record=record.id,
                file=file,
            )
        if record.type == "condition":
            info = vault.nodes.get(record.node)
            if info is not None and info.node.kind != "context":
                yield Finding(
                    "structure.ends",
                    "error",
                    f"condition on {record.node}, a {info.node.kind} node",
                    record=record.id,
                    file=file,
                    fix="conditions describe context nodes only",
                )


def outline_counts(blocks, counts: dict[str, int]) -> dict[str, int]:
    for block in blocks:
        if block.section is not None:
            outline_counts(block.section.blocks, counts)
        for target in (block.requirement, block.figure):
            if target:
                counts[target] = counts.get(target, 0) + 1
    return counts


def section_keys(blocks, keys: list[str]) -> list[str]:
    for block in blocks:
        if block.section is not None:
            keys.append(block.section.key)
            section_keys(block.section.blocks, keys)
    return keys


@rule(
    "structure.outline",
    "each requirement and figure appears once in a document outline; section keys are unique",
)
def outline(context: Context) -> Iterator[Finding]:
    from qingsong.schema import Document

    vault = context.vault
    for record in vault.records.values():
        if not isinstance(record, Document):
            continue
        for target, count in sorted(outline_counts(record.outline, {}).items()):
            if count > 1:
                yield Finding(
                    "structure.outline",
                    "warning",
                    f"{target} appears {count} times in the outline",
                    record=record.id,
                    file=relative_file(vault, record.id),
                    fix="place each requirement and figure once; refer to it elsewhere with [[ID]]",
                )
        keys = section_keys(record.outline, [])
        for key in sorted({key for key in keys if keys.count(key) > 1 or not key.strip()}):
            yield Finding(
                "structure.outline",
                "error",
                f"section key {key!r} is empty or used more than once",
                record=record.id,
                file=relative_file(vault, record.id),
                fix="give every section its own key; [[DOC#key]] references and change "
                "summaries rely on it",
            )
