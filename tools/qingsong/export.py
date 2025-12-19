"""
Export module for Qingsong.

Generates documentation and reports from items:
- Markdown/HTML requirement documents
- Risk registers
- Interface lists
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .core import QingsongCore
from .models import BaseItem, ItemType, Requirement, Risk, Interface


def _escape_markdown(text: str) -> str:
    """Escape special markdown characters."""
    # Simple escape - just handle pipes for tables
    return text.replace("|", "\\|")


def _format_datetime(dt: datetime | str | None) -> str:
    """Format datetime for display."""
    if dt is None:
        return ""
    if isinstance(dt, str):
        return dt
    return dt.strftime("%Y-%m-%d %H:%M")


def export_requirements_markdown(
    core: QingsongCore,
    system_path: str | None = None,
    category_path: str | None = None,
    output_path: Path | None = None,
) -> str:
    """
    Export requirements to Markdown format.

    Args:
        core: QingsongCore instance.
        system_path: Filter by system path.
        category_path: Filter by category path.
        output_path: Optional file to write to.

    Returns:
        Markdown content.
    """
    # Get requirements
    items = core.get_items_by_type(ItemType.REQ)

    if system_path:
        items = [i for i in items if i.system_path == system_path]

    if category_path:
        items = [i for i in items if getattr(i, "category_path", "") == category_path]

    # Sort by ID
    items.sort(key=lambda x: x.id_full)

    # Build markdown
    lines = [
        "# Requirements Document",
        "",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
    ]

    if system_path:
        lines.append(f"**System:** {system_path}")
    if category_path:
        lines.append(f"**Category:** {category_path}")

    lines.extend([
        "",
        f"**Total Requirements:** {len(items)}",
        "",
        "---",
        "",
    ])

    # Group by category
    categories: dict[str, list[BaseItem]] = {}
    for item in items:
        cat = getattr(item, "category_path", "uncategorized")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(item)

    for category, cat_items in sorted(categories.items()):
        lines.extend([
            f"## {category}",
            "",
        ])

        for item in cat_items:
            req = item  # type: Requirement
            lines.extend([
                f"### {req.id_full}: {req.title}",
                "",
                f"**Status:** {req.status.value} | **Owner:** {req.owner} | **Priority:** {getattr(req, 'priority', 'N/A')}",
                "",
                req.text,
                "",
            ])

            # Verification info
            if hasattr(req, "verification_method") and req.verification_method:
                lines.append(f"**Verification Method:** {req.verification_method}")

            # Links
            if req.links:
                lines.append("")
                lines.append("**Links:**")
                for link in req.links:
                    lines.append(f"- {link.link_type}: {link.target_id}")

            lines.extend(["", "---", ""])

    content = "\n".join(lines)

    if output_path:
        output_path.write_text(content)

    return content


def export_risk_register_markdown(
    core: QingsongCore,
    system_path: str | None = None,
    output_path: Path | None = None,
) -> str:
    """
    Export risk register to Markdown format.

    Args:
        core: QingsongCore instance.
        system_path: Filter by system path.
        output_path: Optional file to write to.

    Returns:
        Markdown content.
    """
    # Get risks
    items = core.get_items_by_type(ItemType.RSK)

    if system_path:
        items = [i for i in items if i.system_path == system_path]

    # Sort by risk score (highest first)
    items.sort(key=lambda x: getattr(x, "risk_score", 0) or 0, reverse=True)

    # Build markdown
    lines = [
        "# Risk Register",
        "",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
    ]

    if system_path:
        lines.append(f"**System:** {system_path}")

    lines.extend([
        "",
        f"**Total Risks:** {len(items)}",
        "",
        "## Risk Summary Table",
        "",
        "| ID | Title | L | C | Score | Status | Owner |",
        "|---|---|---|---|---|---|---|",
    ])

    for item in items:
        risk = item  # type: Risk
        score = getattr(risk, "risk_score", 0) or 0
        lines.append(
            f"| {risk.id_full} | {_escape_markdown(risk.title[:50])} | "
            f"{getattr(risk, 'likelihood', 'N/A')} | {getattr(risk, 'consequence', 'N/A')} | "
            f"{score} | {risk.status.value} | {risk.owner} |"
        )

    lines.extend(["", "---", "", "## Risk Details", ""])

    for item in items:
        risk = item  # type: Risk
        lines.extend([
            f"### {risk.id_full}: {risk.title}",
            "",
            f"**System:** {risk.system_path} | **Category:** {getattr(risk, 'category_path', 'N/A')}",
            "",
            f"**Likelihood:** {getattr(risk, 'likelihood', 'N/A')} | "
            f"**Consequence:** {getattr(risk, 'consequence', 'N/A')} | "
            f"**Risk Score:** {getattr(risk, 'risk_score', 'N/A')}",
            "",
            "**Description:**",
            "",
            risk.text,
            "",
        ])

        if hasattr(risk, "mitigation_strategy") and risk.mitigation_strategy:
            lines.extend([
                "**Mitigation Strategy:**",
                "",
                risk.mitigation_strategy,
                "",
            ])

        if hasattr(risk, "contingency_plan") and risk.contingency_plan:
            lines.extend([
                "**Contingency Plan:**",
                "",
                risk.contingency_plan,
                "",
            ])

        lines.extend(["---", ""])

    content = "\n".join(lines)

    if output_path:
        output_path.write_text(content)

    return content


def export_interface_list_markdown(
    core: QingsongCore,
    system_path: str | None = None,
    output_path: Path | None = None,
) -> str:
    """
    Export interface list to Markdown format.

    Args:
        core: QingsongCore instance.
        system_path: Filter by system path.
        output_path: Optional file to write to.

    Returns:
        Markdown content.
    """
    # Get interfaces
    items = core.get_items_by_type(ItemType.IFC)

    if system_path:
        items = [i for i in items if i.system_path == system_path]

    # Sort by ID
    items.sort(key=lambda x: x.id_full)

    # Build markdown
    lines = [
        "# Interface List",
        "",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
    ]

    if system_path:
        lines.append(f"**System:** {system_path}")

    lines.extend([
        "",
        f"**Total Interfaces:** {len(items)}",
        "",
        "## Interface Summary",
        "",
        "| ID | Title | Type | Provider | Consumer | Status |",
        "|---|---|---|---|---|---|",
    ])

    for item in items:
        ifc = item  # type: Interface
        lines.append(
            f"| {ifc.id_full} | {_escape_markdown(ifc.title[:40])} | "
            f"{getattr(ifc, 'category_path', 'N/A')} | "
            f"{getattr(ifc, 'provider_system', 'N/A')} | "
            f"{getattr(ifc, 'consumer_system', 'N/A')} | "
            f"{getattr(ifc, 'interface_status', ifc.status.value)} |"
        )

    lines.extend(["", "---", "", "## Interface Details", ""])

    for item in items:
        ifc = item  # type: Interface
        lines.extend([
            f"### {ifc.id_full}: {ifc.title}",
            "",
            f"**Type:** {getattr(ifc, 'category_path', 'N/A')} | **Status:** {getattr(ifc, 'interface_status', 'N/A')}",
            "",
            f"**Provider:** {getattr(ifc, 'provider_system', 'N/A')} | "
            f"**Consumer:** {getattr(ifc, 'consumer_system', 'N/A')}",
            "",
            "**Description:**",
            "",
            ifc.text,
            "",
        ])

        # Parameters
        params = getattr(ifc, "parameters", {})
        if params:
            lines.extend([
                "**Parameters:**",
                "",
            ])
            for key, value in params.items():
                lines.append(f"- {key}: {value}")
            lines.append("")

        lines.extend(["---", ""])

    content = "\n".join(lines)

    if output_path:
        output_path.write_text(content)

    return content


def export_summary_markdown(
    core: QingsongCore,
    output_path: Path | None = None,
) -> str:
    """
    Export a summary document.

    Args:
        core: QingsongCore instance.
        output_path: Optional file to write to.

    Returns:
        Markdown content.
    """
    summary = core.summary()

    lines = [
        "# Qingsong Repository Summary",
        "",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Overview",
        "",
        f"**Total Items:** {summary['total_items']}",
        "",
        "### Items by Type",
        "",
        "| Type | Count |",
        "|---|---|",
    ]

    for item_type, count in summary["items_by_type"].items():
        lines.append(f"| {item_type} | {count} |")

    lines.extend([
        "",
        "### Items by Status",
        "",
        "| Status | Count |",
        "|---|---|",
    ])

    for status, count in summary["items_by_status"].items():
        lines.append(f"| {status} | {count} |")

    lines.extend([
        "",
        "### Systems",
        "",
    ])

    for system in summary["systems"]:
        items_in_system = len(core.get_items_by_system(system))
        lines.append(f"- {system}: {items_in_system} items")

    content = "\n".join(lines)

    if output_path:
        output_path.write_text(content)

    return content

