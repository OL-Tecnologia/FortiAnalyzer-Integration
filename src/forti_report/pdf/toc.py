"""Sumário com links internos (âncoras ReportLab)."""

from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer

from forti_report.pdf.sections.base import PdfSection


def build_toc_paragraphs(
    sections: list[PdfSection],
    *,
    unit_label: str,
) -> list:
    styles = getSampleStyleSheet()
    toc_title = ParagraphStyle(
        "TocTitle",
        parent=styles["Heading1"],
        fontSize=18,
        spaceAfter=16,
        textColor=colors.HexColor("#003366"),
    )
    toc_entry = ParagraphStyle(
        "TocEntry",
        parent=styles["Normal"],
        fontSize=12,
        leftIndent=12,
        spaceBefore=6,
        leading=16,
    )

    flowables: list = [
        Paragraph("Sumário", toc_title),
        Paragraph(unit_label, styles["Heading3"]),
        Spacer(1, 0.4 * cm),
    ]

    for section in sections:
        anchor = section.key
        # link interno: <a href="#anchor">texto</a>
        text = f'<a href="#{anchor}" color="#0066A1">{section.title}</a>'
        flowables.append(Paragraph(text, toc_entry))

    flowables.append(Spacer(1, 0.8 * cm))
    return flowables
