"""Utilitários de tabela para PDFs ReportLab."""

from __future__ import annotations

import re

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Table, TableStyle

from forti_report.data.parsers.mensal_utils import format_bandwidth
from forti_report.data.wan_models import RankedItem

_CELL_PAD = 6  # left + right padding total


def _table_style(*, font_size: int = 9, header_font_size: int | None = None) -> list:
    hfs = header_font_size if header_font_size is not None else max(font_size + 1, 9)
    return [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#003366")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), hfs),
        ("FONTSIZE", (0, 1), (-1, -1), font_size),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
        ("VALIGN", (0, 1), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F0F4F8")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
        ("WORDWRAP", (0, 1), (-1, -1), True),
    ]


def styled_table(
    rows: list[list[str]],
    widths: list,
    *,
    font_size: int = 9,
    header_font_size: int = 9,
) -> Table:
    table = Table(rows, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle(_table_style(font_size=font_size, header_font_size=header_font_size)))
    return table


def _escape(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _break_long_text(text: str, *, max_token: int = 22) -> str:
    """Escapa texto; quebra de linha fica a cargo do Paragraph (splitLongWords)."""
    return _escape(str(text).strip())


def _measure_col_widths(
    rows: list[list[str]],
    *,
    font_size: int,
    header_font_size: int,
    nowrap_cols: frozenset[int],
) -> list[float]:
    from reportlab.pdfbase.pdfmetrics import stringWidth

    col_count = len(rows[0])
    widths: list[float] = []
    for col in range(col_count):
        header_text = str(rows[0][col]) if col < len(rows[0]) else ""
        body_longest = max(
            (str(row[col]) for row in rows[1:] if col < len(row)),
            key=len,
            default="",
        )
        header_w = stringWidth(header_text, "Helvetica-Bold", header_font_size) + _CELL_PAD + 8
        body_w = stringWidth(body_longest, "Helvetica", font_size) + _CELL_PAD + 4
        w = max(header_w, body_w)
        if col not in nowrap_cols and len(body_longest) > 24:
            w = max(w, min(body_w, stringWidth(body_longest[:24], "Helvetica", font_size) + _CELL_PAD + 8))
        widths.append(w)
    return widths


def column_widths_from_content(
    rows: list[list[str]],
    total_width: float,
    *,
    min_widths: list[float] | None = None,
    font_size: int = 7,
    header_font_size: int = 9,
    stretch_col: int | None = None,
    nowrap_cols: frozenset[int] | None = None,
) -> list[float]:
    """Distribui largura total; colunas nowrap recebem espaço mínimo para o conteúdo."""
    if not rows:
        return []

    col_count = len(rows[0])
    mins = list(min_widths or [0.0] * col_count)
    while len(mins) < col_count:
        mins.append(0.0)

    nowrap = nowrap_cols or frozenset()
    min_cell = font_size * 2 + _CELL_PAD
    measured = _measure_col_widths(
        rows,
        font_size=font_size,
        header_font_size=header_font_size,
        nowrap_cols=nowrap,
    )

    floors: list[float] = []
    flex_weights: list[float] = []
    for col in range(col_count):
        if col in nowrap:
            floor = max(mins[col], measured[col], min_cell)
        else:
            floor = max(mins[col], min_cell)
        floors.append(floor)
        weight = measured[col] if col not in nowrap else 0.2
        if stretch_col is not None and col == stretch_col:
            weight += measured[col] + 2.0
        flex_weights.append(max(weight, 0.3))

    floor_sum = sum(floors)
    if floor_sum >= total_width:
        scale = total_width / floor_sum
        return [max(f * scale, min_cell) for f in floors]

    flex_budget = total_width - floor_sum
    flex_total = sum(flex_weights) or 1.0
    return [floors[i] + flex_budget * (flex_weights[i] / flex_total) for i in range(col_count)]


def wrapped_table(
    rows: list[list],
    widths: list,
    *,
    font_size: int = 7,
    header_font_size: int = 9,
    nowrap_cols: frozenset[int] | None = None,
    split_by_row: int = 0,
) -> Table:
    """Tabela com Paragraph em todas as células para evitar sobreposição horizontal."""
    styles = getSampleStyleSheet()
    nowrap_cols = nowrap_cols or frozenset()
    header_style = ParagraphStyle(
        "TblHeader",
        parent=styles["Normal"],
        fontSize=header_font_size,
        leading=header_font_size + 4,
        textColor=colors.white,
        fontName="Helvetica-Bold",
        alignment=1,
        splitLongWords=0,
        wordWrap=None,
    )
    cell_wrap_style = ParagraphStyle(
        "TblCellWrap",
        parent=styles["Normal"],
        fontSize=font_size,
        leading=font_size + 3,
        splitLongWords=1,
        wordWrap="LTR",
    )
    cell_compact_style = ParagraphStyle(
        "TblCellCompact",
        parent=cell_wrap_style,
        alignment=1,  # center
        splitLongWords=0,
    )

    def _cell(text: str, col_idx: int, *, header: bool = False) -> Paragraph:
        if header:
            return Paragraph(_escape(str(text).strip()), header_style)
        if col_idx in nowrap_cols:
            return Paragraph(_escape(str(text)), cell_compact_style)
        return Paragraph(_break_long_text(text), cell_wrap_style)

    flow_rows = [
        [_cell(cell, c_idx, header=(r_idx == 0)) for c_idx, cell in enumerate(row)]
        for r_idx, row in enumerate(rows)
    ]

    table = Table(flow_rows, colWidths=widths, repeatRows=1, splitByRow=split_by_row)
    table.setStyle(TableStyle(_table_style(font_size=font_size, header_font_size=header_font_size)))
    return table


def data_table(
    rows: list[list[str]],
    total_width: float,
    *,
    min_widths: list[float] | None = None,
    font_size: int = 7,
    header_font_size: int = 9,
    nowrap_cols: frozenset[int] | None = None,
    stretch_col: int | None = None,
    allow_split: bool = False,
) -> Table:
    """Tabela padrão do relatório."""
    nowrap = nowrap_cols or frozenset()
    widths = column_widths_from_content(
        rows,
        total_width,
        min_widths=min_widths,
        font_size=font_size,
        header_font_size=header_font_size,
        stretch_col=stretch_col,
        nowrap_cols=nowrap,
    )
    split = 1 if allow_split or len(rows) > 22 else 0
    return wrapped_table(
        rows,
        widths,
        font_size=font_size,
        header_font_size=header_font_size,
        nowrap_cols=nowrap,
        split_by_row=split,
    )


def _category_display(item: RankedItem) -> str:
    cat = (item.category or "").strip()
    if not cat or cat == item.label:
        return "—"
    return cat


def _format_cell_value(value: str, *, value_header: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return "—"
    if value_header.lower() in {"banda", "bytes", "tráfego", "trafego"}:
        return format_bandwidth(raw)
    return raw


def ranked_table(
    items: list[RankedItem],
    total_width: float,
    *,
    label_header: str = "Nome",
    value_header: str,
    pct_col: bool = False,
    category_col: bool = False,
) -> Table:
    """Tabela de ranking com colunas dimensionadas automaticamente."""
    if category_col and pct_col:
        rows = [["#", label_header, "Categoria", value_header, "%"]]
        for item in items:
            rows.append([
                str(item.rank),
                item.label,
                _category_display(item),
                _format_cell_value(item.value, value_header=value_header),
                item.percentage or "—",
            ])
        min_w = [0.9 * cm, 2.8 * cm, 2.8 * cm, 2.2 * cm, 1.4 * cm]
        nowrap = frozenset({0, 3, 4})
        stretch = 1
    elif pct_col:
        rows = [["#", label_header, value_header, "%"]]
        for item in items:
            rows.append([
                str(item.rank),
                item.label,
                _format_cell_value(item.value, value_header=value_header),
                item.percentage or "—",
            ])
        min_w = [0.9 * cm, 3.5 * cm, 2.8 * cm, 1.4 * cm]
        nowrap = frozenset({0, 2, 3})
        stretch = 1
    elif category_col:
        rows = [["#", label_header, "Categoria", value_header]]
        for item in items:
            rows.append([
                str(item.rank),
                item.label,
                _category_display(item),
                _format_cell_value(item.value, value_header=value_header),
            ])
        min_w = [0.9 * cm, 3.2 * cm, 3.2 * cm, 2.8 * cm]
        nowrap = frozenset({0, 3})
        stretch = 1
    else:
        rows = [["#", label_header, value_header]]
        for item in items:
            val = item.value or item.category or ""
            rows.append([
                str(item.rank),
                item.label,
                _format_cell_value(val, value_header=value_header),
            ])
        min_w = [0.9 * cm, 4.5 * cm, 3.0 * cm]
        nowrap = frozenset({0, 2})
        stretch = 1

    return data_table(
        rows,
        total_width,
        min_widths=min_w,
        font_size=7,
        header_font_size=9,
        nowrap_cols=nowrap,
        stretch_col=stretch,
    )
