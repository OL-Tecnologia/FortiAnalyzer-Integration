"""Capa MENSAL — cabeçalho/rodapé gráficos + bloco central de texto e logo."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, Paragraph, Spacer, Table, TableStyle

from forti_report.config import Settings
from forti_report.pdf.page_layout import LATERAL_MARGIN

_MONTHS_PT = (
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
)


def _asset(path: Path) -> Path | None:
    return path if path.is_file() else None


def _full_width_image(path: Path, page_width: float) -> tuple[Image, float]:
    reader = ImageReader(str(path))
    iw, ih = reader.getSize()
    height = page_width * ih / iw
    img = Image(str(path), width=page_width, height=height)
    img.hAlign = "CENTER"
    return img, height


def _month_year_label(when: datetime | None = None) -> str:
    dt = when or datetime.now()
    return f"{_MONTHS_PT[dt.month - 1]}/{dt.year}"


def build_mensal_cover_flowables(
    settings: Settings,
    *,
    adom: str,
    regional_units: int,
    antennas: int,
    when: datetime | None = None,
) -> list:
    """Monta capa A4: cabecalho_capa + texto central + logo + rodape_capa."""
    page_w, page_h = A4
    header_path = _asset(settings.pdf_cover_header_image)
    footer_path = _asset(settings.pdf_cover_footer_image)
    logo_path = _asset(settings.pdf_cover_logo_image)

    if not header_path and not footer_path:
        return _fallback_cover(adom, regional_units, antennas, when)

    flow: list = []
    header_h = 0.0
    footer_h = 0.0

    if header_path:
        header_img, header_h = _full_width_image(header_path, page_w)
        flow.append(header_img)

    if footer_path:
        _, footer_h = _full_width_image(footer_path, page_w)

    middle_h = max(page_h - header_h - footer_h, 6 * cm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CoverTitle",
        parent=styles["Title"],
        fontSize=22,
        leading=26,
        alignment=1,
        textColor=colors.HexColor("#003366"),
        spaceAfter=10,
    )
    subtitle_style = ParagraphStyle(
        "CoverSubtitle",
        parent=styles["Heading2"],
        fontSize=14,
        leading=18,
        alignment=1,
        textColor=colors.HexColor("#0066A1"),
        spaceAfter=8,
    )
    body_style = ParagraphStyle(
        "CoverBody",
        parent=styles["Normal"],
        fontSize=11,
        leading=15,
        alignment=1,
        textColor=colors.HexColor("#333333"),
        spaceAfter=6,
    )

    text_block: list = [
        Paragraph("RELATÓRIO MENSAL  GERAL", title_style),
        Paragraph(f"Relatório Unificado — ADOM {adom}", subtitle_style),
        Paragraph(
            f"{regional_units} unidades regionais · {antennas} dispositivos",
            body_style,
        ),
        Paragraph(_month_year_label(when), body_style),
    ]

    logo_h = 0.0
    logo_cell: list | Image = Spacer(1, 0.1 * cm)
    if logo_path:
        reader = ImageReader(str(logo_path))
        iw, ih = reader.getSize()
        logo_w = 2.1 * cm
        logo_h = logo_w * ih / iw
        logo_img = Image(str(logo_path), width=logo_w, height=logo_h)
        logo_img.hAlign = "RIGHT"
        logo_cell = logo_img

    side_pad = LATERAL_MARGIN
    logo_row_h = logo_h + 0.5 * cm if logo_path else 0.2 * cm
    text_row_h = max(middle_h - logo_row_h, 4 * cm)
    middle = Table(
        [[text_block], [logo_cell]],
        colWidths=[page_w],
        rowHeights=[text_row_h, logo_row_h],
    )
    middle.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (0, 0), "MIDDLE"),
            ("VALIGN", (0, 1), (0, 1), "BOTTOM"),
            ("ALIGN", (0, 0), (0, 0), "CENTER"),
            ("ALIGN", (0, 1), (0, 1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), side_pad),
            ("RIGHTPADDING", (0, 0), (-1, -1), side_pad),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (0, 0), 0),
            ("BOTTOMPADDING", (0, 1), (0, 1), 0.4 * cm),
        ])
    )
    flow.append(middle)

    if footer_path:
        footer_img, _ = _full_width_image(footer_path, page_w)
        flow.append(footer_img)

    return flow


def _fallback_cover(
    adom: str,
    regional_units: int,
    antennas: int,
    when: datetime | None,
) -> list:
    styles = getSampleStyleSheet()
    centered = ParagraphStyle("CoverCenter", parent=styles["Normal"], alignment=1)
    return [
        Spacer(1, 5.5 * cm),
        Paragraph(
            "RELATÓRIO MENSAL  GERAL",
            ParagraphStyle(
                "T",
                parent=styles["Title"],
                fontSize=24,
                alignment=1,
                textColor=colors.HexColor("#003366"),
            ),
        ),
        Paragraph(
            f"Relatório Unificado — ADOM {adom}",
            ParagraphStyle(
                "S",
                parent=styles["Heading2"],
                alignment=1,
                textColor=colors.HexColor("#0066A1"),
            ),
        ),
        Spacer(1, 0.5 * cm),
        Paragraph(
            f"{regional_units} unidades regionais · {antennas} dispositivos",
            centered,
        ),
        Paragraph(_month_year_label(when), centered),
    ]
