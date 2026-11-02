"""Vault discovery, strict loading and round-trip saving (docs/SPEC.md §3, §6.1)."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from qingsong import ids
from qingsong.findings import Finding
from qingsong.schema import (
    GlossaryFile,
    Node,
    PeopleFile,
    Record,
    RecordBase,
    TreeFile,
    VaultConfig,
    plain,
    record_folders,
)

config_name = "qingsong.toml"
record_adapter: TypeAdapter = TypeAdapter(Record)


class VaultNotFoundError(Exception):
    pass


@dataclass
class NodeInfo:
    node: Node
    reference: str
    system: str | None
    depth: int
    parent: str | None
    file: str

    @property
    def requirement_namespace(self) -> str | None:
        if self.node.kind != "product":
            return None
        if self.system is None:
            return None
        return f"{self.system}-SYS" if self.depth == 1 else f"{self.system}-{self.node.node}"


@dataclass
class Vault:
    root: Path
    config: VaultConfig | None = None
    nodes: dict[str, NodeInfo] = field(default_factory=dict)
    root_node: str | None = None
    people: PeopleFile | None = None
    glossary: GlossaryFile | None = None
    records: dict[str, RecordBase] = field(default_factory=dict)
    files: dict[str, Path] = field(default_factory=dict)
    duplicates: list[tuple[str, Path]] = field(default_factory=list)
    load_findings: list[Finding] = field(default_factory=list)

    def relative(self, path: Path) -> str:
        return str(path.relative_to(self.root))

    def by_type(self, record_type: str) -> list[RecordBase]:
        return [record for record in self.records.values() if record.type == record_type]

    def namespaces(self) -> dict[str, str]:
        """Requirement namespace → node reference it belongs to."""
        result: dict[str, str] = {}
        if self.config and self.root_node:
            for namespace in self.config.top_namespaces:
                result[namespace] = self.root_node
        for info in self.nodes.values():
            namespace = info.requirement_namespace
            if namespace:
                result[namespace] = info.reference
        return result

    def is_approver(self, person: str) -> bool:
        return bool(
            self.people and person in self.people.people and self.people.people[person].approver
        )


def find_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / config_name).is_file():
            return candidate
    raise VaultNotFoundError(f"no {config_name} found in {current} or its parents")


safe_loader = YAML(typ="safe")


def read_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return safe_loader.load(handle)


def round_trip_yaml() -> YAML:
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.width = 1_000_000
    yaml.indent(mapping=2, sequence=4, offset=2)
    # A date used twice in one write would otherwise appear as an anchor (&id001) and alias.
    yaml.representer.ignore_aliases = lambda data: True
    return yaml


def describe_validation_error(error: ValidationError) -> str:
    parts = []
    for item in error.errors()[:5]:
        location = ".".join(
            str(part) for part in item["loc"] if not str(part).startswith("function")
        )
        parts.append(f"{location or 'record'}: {item['msg']}")
    more = len(error.errors()) - 5
    return "; ".join(parts) + (f"; and {more} more" if more > 0 else "")


def load(root: Path) -> Vault:
    vault = Vault(root=root)
    load_config(vault)
    load_tree(vault)
    load_people_and_glossary(vault)
    load_records(vault)
    return vault


def load_config(vault: Vault) -> None:
    path = vault.root / config_name
    try:
        vault.config = VaultConfig.model_validate(tomllib.loads(path.read_text(encoding="utf-8")))
    except (tomllib.TOMLDecodeError, ValidationError) as error:
        message = (
            describe_validation_error(error) if isinstance(error, ValidationError) else str(error)
        )
        vault.load_findings.append(Finding("integrity.config", "error", message, file=config_name))


def load_tree(vault: Vault) -> None:
    tree_dir = vault.root / "tree"
    files: dict[str, TreeFile] = {}
    for path in sorted(tree_dir.glob("*.yaml")):
        relative = vault.relative(path)
        try:
            branch = TreeFile.model_validate(plain(read_yaml(path)))
        except YAMLError as error:
            vault.load_findings.append(
                Finding("integrity.yaml_syntax", "error", str(error), file=relative)
            )
            continue
        except ValidationError as error:
            vault.load_findings.append(
                Finding(
                    "integrity.schema", "error", describe_validation_error(error), file=relative
                )
            )
            continue
        if path.stem != branch.node:
            vault.load_findings.append(
                Finding(
                    "integrity.path_mismatch",
                    "error",
                    f"tree file defines {branch.node}",
                    file=relative,
                    fix=f"rename the file to tree/{branch.node}.yaml",
                )
            )
        files[relative] = branch
    roots = [(relative, branch) for relative, branch in files.items() if branch.parent is None]
    if len(roots) != 1:
        found = ", ".join(branch.node for _, branch in roots) or "none"
        vault.load_findings.append(
            Finding(
                "structure.tree_root",
                "error",
                f"exactly one tree file must have no parent; found {found}",
                file="tree",
            )
        )
        return
    root_file, root_branch = roots[0]
    vault.root_node = root_branch.node
    register_branch(vault, root_branch, system=None, depth=0, parent=None, file=root_file)
    for relative, branch in files.items():
        if branch.parent is None:
            continue
        if branch.parent != root_branch.node:
            vault.load_findings.append(
                Finding(
                    "structure.tree_parent",
                    "error",
                    f"parent {branch.parent} is not the root {root_branch.node}; top-level branches "
                    "hang from the root",
                    file=relative,
                )
            )
            continue
        register_branch(
            vault, branch, system=branch.node, depth=1, parent=root_branch.node, file=relative
        )


def register_branch(
    vault: Vault, node: Node, system: str | None, depth: int, parent: str | None, file: str
) -> None:
    reference = node.node if depth <= 1 else f"{system}-{node.node}"
    if reference in vault.nodes:
        vault.load_findings.append(
            Finding(
                "structure.node_code",
                "error",
                f"node reference {reference} defined twice",
                file=file,
                fix="node codes must be unique within their top-level system",
            )
        )
    else:
        vault.nodes[reference] = NodeInfo(node, reference, system, depth, parent, file)
    for child in node.children:
        register_branch(vault, child, system, depth + 1, reference, file)


def load_people_and_glossary(vault: Vault) -> None:
    for name, model, attribute in (
        ("people.yaml", PeopleFile, "people"),
        ("glossary.yaml", GlossaryFile, "glossary"),
    ):
        path = vault.root / name
        if not path.exists():
            vault.load_findings.append(
                Finding("integrity.missing_file", "error", f"{name} is missing", file=name)
            )
            continue
        try:
            setattr(vault, attribute, model.model_validate(plain(read_yaml(path))))
        except YAMLError as error:
            vault.load_findings.append(
                Finding("integrity.yaml_syntax", "error", str(error), file=name)
            )
        except ValidationError as error:
            vault.load_findings.append(
                Finding("integrity.schema", "error", describe_validation_error(error), file=name)
            )


def load_records(vault: Vault) -> None:
    for record_type, folder in record_folders.items():
        base = vault.root / folder
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.yaml")):
            load_record_file(vault, path, record_type)
        for path in sorted(base.rglob("*.yml")):
            vault.load_findings.append(
                Finding(
                    "integrity.path_mismatch",
                    "error",
                    "record files end in .yaml, not .yml",
                    file=vault.relative(path),
                    fix=f"rename it to {path.stem}.yaml",
                )
            )


def load_record_file(vault: Vault, path: Path, expected_type: str) -> None:
    relative = vault.relative(path)
    try:
        data = plain(read_yaml(path))
    except (UnicodeDecodeError, OSError) as error:
        vault.load_findings.append(
            Finding(
                "integrity.yaml_syntax", "error", f"cannot read the file: {error}", file=relative
            )
        )
        return
    except YAMLError as error:
        vault.load_findings.append(
            Finding(
                "integrity.yaml_syntax",
                "error",
                str(error).splitlines()[0],
                file=relative,
                fix="fix the YAML syntax",
            )
        )
        return
    if not isinstance(data, dict):
        vault.load_findings.append(
            Finding("integrity.schema", "error", "a record file must hold a mapping", file=relative)
        )
        return
    record_id = data.get("id") if isinstance(data.get("id"), str) else None
    if data.get("type") != expected_type:
        vault.load_findings.append(
            Finding(
                "integrity.schema",
                "error",
                f"type is {data.get('type')!r} but the file is in the {record_folders[expected_type]}/ folder",
                record=record_id,
                file=relative,
            )
        )
        return
    try:
        record = record_adapter.validate_python(data)
    except ValidationError as error:
        vault.load_findings.append(
            Finding(
                "integrity.schema",
                "error",
                describe_validation_error(error),
                record=record_id,
                file=relative,
            )
        )
        return
    if record.id in vault.records:
        vault.duplicates.append((record.id, path))
        return
    vault.records[record.id] = record
    vault.files[record.id] = path


def save_record(path: Path, updates: dict[str, Any], removals: tuple[str, ...] = ()) -> None:
    """Apply top-level updates to a record file, keeping comments, key order and quoting."""
    yaml = round_trip_yaml()
    with path.open(encoding="utf-8") as handle:
        data = yaml.load(handle)
    for key in removals:
        data.pop(key, None)
    for key, value in updates.items():
        data[key] = value
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump(data, handle)


def write_new_record(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        round_trip_yaml().dump(data, handle)


def expected_path(vault: Vault, record: RecordBase) -> Path:
    return vault.root / ids.relative_path(record.type, record.id)
