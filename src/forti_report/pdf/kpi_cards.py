"""Cards KPI desenhados com ReportLab (sem Plotly)."""

from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Table, TableStyle

_CARD_BG = colors.HexColor("#F7FAFC")
_CARD_BORDER = colors.HexColor("#E2EAF2")
_LABEL_COLOR = colors.HexColor("#6B7C8F")
_VALUE_COLOR = colors.HexColor("#0B3A5B")
_ACCENT = colors.HexColor("#1A7AB8")


def kpi_cards_table(
    items: list[tuple[str, str]],
    width: float,
    *,
    cols: int = 3,
) -> Table | None:
    """
    Monta grade de cards KPI (baixos, com barra lateral — menos “quadrados”).
    items: lista de (rótulo, valor).
    """
    if not items:
        return None

    cols = max(2, min(cols, len(items)))
    label_style = ParagraphStyle(
        "KpiLabel",
        fontName="Helvetica",
        fontSize=6.5,
        leading=8,
        textColor=_LABEL_COLOR,
        alignment=0,
    )
    value_style = ParagraphStyle(
        "KpiValue",
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        textColor=_VALUE_COLOR,
        alignment=0,
        spaceBefore=1,
    )

    cell_w = width / cols - 0.18 * cm
    cells: list = []
    for label, value in items:
        inner = Table(
            [
                [Paragraph(str(label), label_style)],
                [Paragraph(str(value) if value not in ("", None) else "—", value_style)],
            ],
            colWidths=[cell_w],
        )
        inner.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), _CARD_BG),
                    ("BOX", (0, 0), (-1, -1), 0.4, _CARD_BORDER),
                    ("LINEBEFORE", (0, 0), (0, -1), 2.2, _ACCENT),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ]
            )
        )
        cells.append(inner)

    while len(cells) % cols:
        cells.append("")

    rows = [cells[i : i + cols] for i in range(0, len(cells), cols)]
    col_w = width / cols
    table = Table(rows, colWidths=[col_w] * cols)
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return table
