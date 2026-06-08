"""Margens e dimensões comuns dos PDFs."""

from __future__ import annotations

from reportlab.platypus import BaseDocTemplate

# 2,50 cm ≈ 70 pt (padrão ReportLab era 72 pt / 2,54 cm)
LATERAL_MARGIN = 70


def apply_lateral_margins(doc: BaseDocTemplate) -> None:
    doc.leftMargin = LATERAL_MARGIN
    doc.rightMargin = LATERAL_MARGIN
