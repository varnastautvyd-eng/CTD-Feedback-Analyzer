
from typing import Dict

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)


def _get_styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="TitleBlue",
            parent=styles["Title"],
            textColor=colors.HexColor("#004b93"),  # clean Airbus-like blue
        )
    )
    styles.add(
        ParagraphStyle(
            name="HeadingBlue",
            parent=styles["Heading2"],
            textColor=colors.HexColor("#004b93"),
        )
    )
    return styles


def generate_summary_pdf(buffer, kpis: Dict):
    """Build a high-level management PDF summary.

    Parameters
    ----------
    buffer:
        A file-like object (e.g. io.BytesIO) or path where the PDF will be written.
    kpis : dict
        Dictionary returned from compute_global_kpis().
    """
    styles = _get_styles()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    story = []

    # Cover page
    story.append(Spacer(1, 3 * cm))
    story.append(Paragraph("Cabin Crew Instructor Performance", styles["TitleBlue"]))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph("Management Summary Report", styles["HeadingBlue"]))
    story.append(Spacer(1, 1.5 * cm))

    story.append(Paragraph("This report summarises the performance of cabin crew instructors based on training evaluation forms exported from Centrik.", styles["Normal"]))
    story.append(Spacer(1, 2 * cm))

    # KPI table
    story.append(Paragraph("Key Performance Indicators", styles["HeadingBlue"]))
    story.append(Spacer(1, 0.5 * cm))

    data = [
        ["Metric", "Value"],
        ["Total forms", str(kpis.get("total_forms", ""))],
        ["Average score", f"{kpis.get('avg_score', 0):.2f}"],
        ["Low-score forms (≤3)", str(kpis.get("total_low_score", ""))],
        ["Low-score rate", f"{kpis.get('low_score_pct', 0):.1f}%"],
    ]
    table = Table(data, colWidths=[7 * cm, 7 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#004b93")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 1 * cm))

    story.append(Paragraph("Low-score forms are those where any rating on the form is 3 or below on a 1–5 scale.", styles["Normal"]))

    doc.build(story)


def generate_instructor_pdf(buffer, stats: Dict):
    """Build a report for a single instructor.

    Parameters
    ----------
    buffer:
        A file-like object (e.g. io.BytesIO) or path where the PDF will be written.
    stats : dict
        Dictionary returned from get_instructor_stats().
    """
    styles = _get_styles()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    story = []

    name = stats.get("name", "Unknown")

    # Cover / heading
    story.append(Spacer(1, 2.5 * cm))
    story.append(Paragraph(f"Instructor Performance Report", styles["TitleBlue"]))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(name, styles["HeadingBlue"]))
    story.append(Spacer(1, 1 * cm))

    # Summary metrics
    data = [
        ["Metric", "Value"],
        ["Total forms", str(stats.get("total_forms", ""))],
        ["Average score", f"{stats.get('avg_score', 0):.2f}"],
        ["Low-score forms (≤3)", str(stats.get("low_score_count", ""))],
        ["Low-score rate", f"{stats.get('low_score_pct', 0):.1f}%"],
    ]
    table = Table(data, colWidths=[7 * cm, 7 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#004b93")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 1 * cm))

    # Subject breakdown table, if available
    by_subject = stats.get("by_subject")
    if by_subject is not None and not by_subject.empty:
        story.append(Paragraph("Breakdown by subject", styles["HeadingBlue"]))
        story.append(Spacer(1, 0.5 * cm))

        subj_data = [["Subject", "Forms", "Average score", "Low-score forms"]]
        for _, row in by_subject.iterrows():
            subj_data.append(
                [
                    str(row.get("subject_grouped", "")),
                    str(row.get("form_count", "")),
                    f"{row.get('avg_score', 0):.2f}",
                    str(row.get("low_score_count", "")),
                ]
            )

        subj_table = Table(subj_data, colWidths=[6 * cm, 3 * cm, 3 * cm, 3 * cm])
        subj_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#004b93")),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ]
            )
        )
        story.append(subj_table)
        story.append(Spacer(1, 1 * cm))

    doc.build(story)
