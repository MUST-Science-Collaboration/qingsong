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


from fpdf import FPDF


class PDFGenerator(FPDF):
    """Base class for Qingsong PDF reports."""

    def __init__(self, title: str, project_id: str = "MUST"):
        super().__init__()
        self.report_title = title
        self.project_id = project_id
        self.set_title(title)
        self.set_author("Qingsong Management Engine")

    def header(self):
        # Logo
        self.set_font("helvetica", "B", 15)
        self.cell(0, 10, f"{self.project_id} - Qingsong", border=False, ln=0, align="L")
        self.set_font("helvetica", "I", 8)
        self.cell(0, 10, f"Generated: {datetime.now().strftime('%Y-%m-%d')}", border=False, ln=1, align="R")
        self.set_draw_color(30, 58, 95)  # Dark blue
        self.line(10, 20, 200, 20)
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def section_title(self, label: str):
        self.set_font("helvetica", "B", 14)
        self.set_fill_color(230, 230, 230)
        self.cell(0, 10, label, ln=1, fill=True)
        self.ln(4)

    def item_header(self, id_full: str, title: str):
        self.set_font("helvetica", "B", 11)
        self.cell(0, 8, f"{id_full}: {title}", ln=1)
        self.set_font("helvetica", "", 9)

    def multi_cell_markdown(self, text: str):
        """Very basic markdown-ish text handling."""
        self.set_font("helvetica", "", 10)
        # Replace common markdown chars for PDF display
        clean_text = text.replace("**", "").replace("__", "").replace("`", "'")
        self.multi_cell(0, 5, clean_text)
        self.ln(2)


def export_requirements_pdf(
    core: QingsongCore,
    output_path: Path,
    system_path: str | None = None,
) -> None:
    """Export requirements to a formal PDF."""
    items = core.get_items_by_type(ItemType.REQ)
    if system_path:
        items = [i for i in items if i.system_path == system_path]
    items.sort(key=lambda x: x.id_full)

    pdf = PDFGenerator("Requirements Specification", project_id=core.metadata.project_id if core.metadata else "MUST")
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.set_font("helvetica", "B", 20)
    pdf.cell(0, 20, "Requirements Specification", ln=1, align="C")
    if system_path:
        pdf.set_font("helvetica", "B", 14)
        pdf.cell(0, 10, f"System: {system_path}", ln=1, align="C")
    pdf.ln(10)

    # Summary Table
    pdf.section_title("Summary Table")
    pdf.set_font("helvetica", "B", 9)
    pdf.cell(40, 8, "ID", border=1)
    pdf.cell(100, 8, "Title", border=1)
    pdf.cell(30, 8, "Status", border=1)
    pdf.cell(20, 8, "Owner", border=1, ln=1)

    pdf.set_font("helvetica", "", 8)
    for item in items:
        pdf.cell(40, 7, item.id_full, border=1)
        pdf.cell(100, 7, item.title[:60], border=1)
        pdf.cell(30, 7, item.status.value, border=1)
        pdf.cell(20, 7, item.owner, border=1, ln=1)
    
    pdf.add_page()
    pdf.section_title("Detailed Requirements")
    
    for item in items:
        if pdf.get_y() > 250:
            pdf.add_page()
        pdf.item_header(item.id_full, item.title)
        pdf.set_font("helvetica", "I", 9)
        pdf.cell(0, 6, f"Status: {item.status.value} | Owner: {item.owner} | System: {item.system_path}", ln=1)
        pdf.ln(2)
        pdf.multi_cell_markdown(item.text)
        
        if item.links:
            pdf.set_font("helvetica", "B", 9)
            pdf.cell(0, 6, "Links:", ln=1)
            pdf.set_font("helvetica", "", 9)
            for link in item.links:
                pdf.cell(0, 5, f"  - {link.link_type}: {link.target_id}", ln=1)
        
        pdf.ln(5)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)

    pdf.output(str(output_path))


def export_maturity_report_pdf(
    core: QingsongCore,
    output_path: Path,
) -> None:
    """Export a Project Maturity & Compliance Report to PDF."""
    summary = core.get_verification_summary()
    staged = len(core.staged_changes)
    tbd_items = [i for i in core.items.values() if i.has_placeholders]

    pdf = PDFGenerator("Project Maturity Report", project_id=core.metadata.project_id if core.metadata else "MUST")
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.set_font("helvetica", "B", 20)
    pdf.cell(0, 20, "Project Maturity & Compliance", ln=1, align="C")
    pdf.ln(10)

    # Verification Progress
    pdf.section_title("1. Verification Progress")
    pdf.set_font("helvetica", "", 11)
    pdf.cell(0, 8, f"Total Requirements: {summary['total']}", ln=1)
    pdf.cell(0, 8, f"Verified Requirements: {summary['verified']} ({summary['percent']:.1f}%)", ln=1)
    pdf.cell(0, 8, f"Pending Verification: {summary['total'] - summary['verified']}", ln=1)
    pdf.ln(5)

    # Stability Tracking
    pdf.section_title("2. Stability Tracking (TBD/TBC)")
    if not tbd_items:
        pdf.set_text_color(40, 167, 69) # Green
        pdf.cell(0, 8, "No TBD or TBC placeholders found. Project requirements are stable.", ln=1)
        pdf.set_text_color(0, 0, 0)
    else:
        pdf.set_text_color(220, 53, 69) # Red
        pdf.cell(0, 8, f"Found {len(tbd_items)} items with TBD/TBC placeholders.", ln=1)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(5)
        pdf.set_font("helvetica", "B", 9)
        pdf.cell(50, 8, "ID", border=1)
        pdf.cell(100, 8, "Title", border=1)
        pdf.cell(40, 8, "Owner", border=1, ln=1)
        pdf.set_font("helvetica", "", 8)
        for i in tbd_items:
            pdf.cell(50, 7, i.id_full, border=1)
            pdf.cell(100, 7, i.title[:60], border=1)
            pdf.cell(40, 7, i.owner, border=1, ln=1)

    # Staging Status
    pdf.ln(10)
    pdf.section_title("3. Repository Health")
    if staged > 0:
        pdf.cell(0, 8, f"Warning: {staged} changes are currently staged but not flushed to disk.", ln=1)
    else:
        pdf.cell(0, 8, "Repository is synchronized with disk.", ln=1)

    pdf.output(str(output_path))


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


def export_to_csv(
    items: list[BaseItem],
    output_path: Path,
) -> None:
    """
    Export a list of items to a CSV file.

    Args:
        items: List of items to export.
        output_path: Path to the output CSV file.
    """
    import csv
    import io

    if not items:
        return

    # Convert to dicts for CSV writing
    records = []
    for item in items:
        record = item.model_dump(mode="json")
        # Flatten some complex fields if needed, or just use JSON strings
        # For CSV, flat is better
        flat_record = {
            "id_full": record["id_full"],
            "type": record["type"],
            "title": record["title"],
            "status": record["status"],
            "owner": record["owner"],
            "system_path": record["system_path"],
            "l3": record.get("l3"),
            "category_path": record.get("category_path"),
            "created_at": record["created_at"],
            "updated_at": record["updated_at"],
        }
        # Add some type-specific fields if they exist
        if "priority" in record: flat_record["priority"] = record["priority"]
        if "likelihood" in record: flat_record["likelihood"] = record["likelihood"]
        if "consequence" in record: flat_record["consequence"] = record["consequence"]
        if "risk_score" in record: flat_record["risk_score"] = record["risk_score"]
        
        records.append(flat_record)

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)


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
        "## Summary Table",
        "",
        "| ID | Title | Status | Owner | Priority |",
        "|---|---|---|---|---|",
    ])

    for item in items:
        lines.append(
            f"| {item.id_full} | {_escape_markdown(item.title[:50])} | "
            f"{item.status.value} | {item.owner} | {getattr(item, 'priority', 'N/A')} |"
        )

    lines.extend(["", "---", "", "## Requirement Details", ""])

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

