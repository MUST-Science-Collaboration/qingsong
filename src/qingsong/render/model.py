"""What the renderers need from a vault: document numbering, links, trees and graphs."""

from dataclasses import dataclass, field

from qingsong.schema import Block, Document, Requirement
from qingsong.vault import Vault


@dataclass
class Numbering:
    sections: dict[str, str] = field(default_factory=dict)
    figures: dict[str, str] = field(default_factory=dict)
    requirements: dict[str, str] = field(default_factory=dict)
    titles: dict[str, dict[str, str]] = field(default_factory=dict)


def number_document(document: Document) -> Numbering:
    """Section numbers (1, 2.1, 2.1.3), figure numbers per top-level section (3.1) and the
    position of each requirement (2.1.1), as in the formal documents."""
    numbering = Numbering()

    def visit(blocks: list[Block], prefix: list[int], chapter: int | None) -> None:
        section_count = 0
        requirement_count = 0
        for block in blocks:
            if block.section is not None:
                section_count += 1
                number = [*prefix, section_count]
                numbering.sections[block.section.key] = ".".join(map(str, number))
                numbering.titles[block.section.key] = block.section.title
                visit(
                    block.section.blocks, number, chapter if chapter is not None else section_count
                )
            elif block.requirement:
                requirement_count += 1
                numbering.requirements[block.requirement] = ".".join(
                    map(str, [*prefix, requirement_count])
                )
            elif block.figure and chapter is not None:
                count = (
                    sum(
                        1 for value in numbering.figures.values() if value.startswith(f"{chapter}.")
                    )
                    + 1
                )
                numbering.figures[block.figure] = f"{chapter}.{count}"

    visit(document.outline, [], None)
    return numbering


def documents_of(vault: Vault) -> list[Document]:
    return sorted(
        (record for record in vault.records.values() if isinstance(record, Document)),
        key=lambda document: document.id,
    )


def requirement_documents(vault: Vault) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for document in documents_of(vault):
        for requirement_id in number_document(document).requirements:
            result.setdefault(requirement_id, []).append(document.id)
    return result


def children_of(vault: Vault) -> dict[str, list[str]]:
    children: dict[str, list[str]] = {}
    for record in vault.records.values():
        if isinstance(record, Requirement):
            for link in record.derives_from:
                children.setdefault(link.id, []).append(record.id)
    return {key: sorted(value) for key, value in children.items()}


def tree_data(vault: Vault) -> dict | None:
    """The product tree as nested dicts, with requirement counts per node and subtree."""
    if vault.root_node is None:
        return None
    allocated: dict[str, list[str]] = {}
    for record in vault.records.values():
        if isinstance(record, Requirement) and record.lifecycle == "current":
            allocated.setdefault(record.allocated_to, []).append(record.id)
    namespaces = {reference: namespace for namespace, reference in vault.namespaces().items()}

    def build(reference: str) -> dict:
        info = vault.nodes[reference]
        child_references = [
            other.reference for other in vault.nodes.values() if other.parent == reference
        ]
        if reference == vault.root_node and vault.config and vault.config.tree_order:
            order = vault.config.tree_order
            child_references.sort(
                key=lambda child: (order.index(child) if child in order else len(order), child)
            )
        children = [build(child) for child in child_references]
        own = [
            {
                "id": record_id,
                "title": (
                    vault.records[record_id].title.get("en")
                    or next(iter(vault.records[record_id].title.values()), "")
                ),
            }
            for record_id in sorted(allocated.get(reference, []))
        ]
        node_namespaces = sorted(
            namespace for namespace, target in vault.namespaces().items() if target == reference
        )
        return {
            "reference": reference,
            "code": info.node.node,
            "structural_code": info.node.structural_code,
            "names": info.node.names,
            "kind": info.node.kind,
            "status": info.node.status,
            "note": info.node.note,
            "namespaces": node_namespaces
            or ([namespaces[reference]] if reference in namespaces else []),
            "requirements": own,
            "total": len(own) + sum(child["total"] for child in children),
            "children": children,
        }

    return build(vault.root_node)
