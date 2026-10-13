"""Capa MENSAL — faixa superior OL + texto/logo cliente + faixa inferior."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Flowable, Image, KeepTogether, Paragraph, Spacer, Table, TableStyle

from forti_report.config import Settings
from forti_report.pdf.page_layout import LATERAL_MARGIN

# Folga para o motor do ReportLab não empurrar a faixa inferior para a 2ª página
# quando a soma das alturas fecha exatamente em A4.
_COVER_PAGE_SLACK = 3.0
_DEFAULT_LOGO_WIDTH_CM = 2.1
_DEFAULT_LOGO_ALIGN = "right"
_DEFAULT_LOGO_OFFSET_Y_CM = 0.35


class _CoverLogoSlot(Flowable):
    """Caixa do miolo inferior com logo dimensionado e posicionado."""

    def __init__(
        self,
        path: Path,
        *,
        box_w: float,
        box_h: float,
        logo_w: float,
        logo_h: float,
        align: str,
        offset_x: float,
        offset_y: float,
        side_pad: float,
    ):
        super().__init__()
        self.path = path
        self.box_w = box_w
        self.box_h = box_h
        self.logo_w = logo_w
        self.logo_h = logo_h
        self.align = (align or _DEFAULT_LOGO_ALIGN).lower()
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.side_pad = side_pad

    def wrap(self, availWidth, availHeight):  # noqa: N803
        return self.box_w, self.box_h

    def draw(self) -> None:
        inner_left = self.side_pad
        inner_right = self.box_w - self.side_pad
        inner_w = max(inner_right - inner_left, self.logo_w)
        if self.align == "left":
            x = inner_left
        elif self.align == "center":
            x = inner_left + (inner_w - self.logo_w) / 2
        else:
            x = inner_right - self.logo_w
        x += self.offset_x
        y = max(0.0, min(self.offset_y, self.box_h - self.logo_h))
        self.canv.drawImage(
            str(self.path),
            x,
            y,
            width=self.logo_w,
            height=self.logo_h,
            mask="auto",
            preserveAspectRatio=True,
        )


def _logo_layout(settings: Settings, logo_path: Path) -> tuple[float, float, str, float, float]:
    """Retorna (logo_w, logo_h, align, offset_x, offset_y) em pontos."""
    width_cm = float(getattr(settings, "pdf_cover_logo_width_cm", _DEFAULT_LOGO_WIDTH_CM) or _DEFAULT_LOGO_WIDTH_CM)
    width_cm = max(0.5, min(width_cm, 10.0))
    align = str(getattr(settings, "pdf_cover_logo_align", _DEFAULT_LOGO_ALIGN) or _DEFAULT_LOGO_ALIGN).lower()
    if align not in {"left", "center", "right"}:
        align = _DEFAULT_LOGO_ALIGN
    ox = float(getattr(settings, "pdf_cover_logo_offset_x_cm", 0.0) or 0.0) * cm
    oy = float(
        getattr(settings, "pdf_cover_logo_offset_y_cm", _DEFAULT_LOGO_OFFSET_Y_CM) or _DEFAULT_LOGO_OFFSET_Y_CM
    ) * cm
    reader = ImageReader(str(logo_path))
    iw, ih = reader.getSize()
    logo_w = width_cm * cm
    logo_h = logo_w * ih / iw if iw else logo_w
    return logo_w, logo_h, align, ox, oy

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


def _cover_subtitle(adom: str, company: str) -> str:
    """Na capa usa o Nome de exibição do cliente; ADOM só como fallback."""
    label = (company or adom or "").strip()
    return f"Relatório Unificado — {label}"


def build_mensal_cover_flowables(
    settings: Settings,
    *,
    adom: str,
    regional_units: int,
    antennas: int,
    when: datetime | None = None,
    title: str | None = None,
    detail: str | None = None,
    period_label: str | None = None,
) -> list:
    """
    Capa A4 completa:
    - faixa superior (cabecalho_capa — branding OL)
    - miolo: título, ADOM/empresa, contagens FAZ, mês/ano, logo do cliente
    - faixa inferior (rodape_capa — branding OL)
    """
    page_w, page_h = A4
    header_path = _asset(settings.pdf_cover_header_image)
    footer_path = _asset(settings.pdf_cover_footer_image)
    logo_path = _asset(settings.pdf_cover_logo_image)

    title = (title or settings.cover_title or "RELATÓRIO MENSAL  GERAL").strip()
    company = (settings.client_display_name or "").strip()
    subtitle = _cover_subtitle(adom, company)
    detail_line = detail if detail is not None else f"{regional_units} unidades regionais · {antennas} dispositivos"
    period = period_label or _month_year_label(when)

    if not header_path and not footer_path:
        return _text_only_cover(
            adom,
            regional_units,
            antennas,
            when,
            title=title,
            company=company,
            logo_path=logo_path,
            settings=settings,
            detail_line=detail_line,
            period=period,
        )

    flow: list = []
    header_h = 0.0
    footer_h = 0.0

    header_img = None
    if header_path:
        header_img, header_h = _full_width_image(header_path, page_w)

    footer_img = None
    if footer_path:
        footer_img, footer_h = _full_width_image(footer_path, page_w)

    # Garante capa em 1 página: escala faixas se necessário e deixa folga.
    min_middle = 5 * cm
    band_h = header_h + footer_h
    budget = page_h - _COVER_PAGE_SLACK - min_middle
    if band_h > budget > 0:
        scale = budget / band_h
        header_h *= scale
        footer_h *= scale
        if header_img is not None:
            header_img = Image(str(header_path), width=page_w, height=header_h)
            header_img.hAlign = "CENTER"
        if footer_img is not None:
            footer_img = Image(str(footer_path), width=page_w, height=footer_h)
            footer_img.hAlign = "CENTER"

    middle_h = page_h - _COVER_PAGE_SLACK - header_h - footer_h

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
        Paragraph(title, title_style),
        Paragraph(subtitle, subtitle_style),
        Paragraph(detail_line, body_style),
        Paragraph(period, body_style),
    ]

    side_pad = LATERAL_MARGIN
    logo_cell: Flowable | Spacer = Spacer(1, 0.1 * cm)
    logo_row_h = 0.2 * cm
    if logo_path:
        logo_w, logo_h, align, ox, oy = _logo_layout(settings, logo_path)
        logo_row_h = logo_h + oy + 0.15 * cm
        if logo_row_h >= middle_h - 3 * cm:
            logo_row_h = max(middle_h * 0.22, logo_h + 0.1 * cm)
            oy = max(0.0, logo_row_h - logo_h - 0.1 * cm)
        logo_cell = _CoverLogoSlot(
            logo_path,
            box_w=page_w,
            box_h=logo_row_h,
            logo_w=logo_w,
            logo_h=logo_h,
            align=align,
            offset_x=ox,
            offset_y=oy,
            side_pad=side_pad,
        )

    text_row_h = middle_h - logo_row_h
    middle = Table(
        [[text_block], [logo_cell]],
        colWidths=[page_w],
        rowHeights=[text_row_h, logo_row_h],
    )
    middle.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (0, 0), "MIDDLE"),
                ("VALIGN", (0, 1), (0, 1), "BOTTOM"),
                ("ALIGN", (0, 0), (0, 0), "CENTER"),
                ("LEFTPADDING", (0, 0), (0, 0), side_pad),
                ("RIGHTPADDING", (0, 0), (0, 0), side_pad),
                ("LEFTPADDING", (0, 1), (0, 1), 0),
                ("RIGHTPADDING", (0, 1), (0, 1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    if header_img is not None:
        flow.append(header_img)
    flow.append(middle)
    if footer_img is not None:
        flow.append(footer_img)

    return [KeepTogether(flow)]


def _text_only_cover(
    adom: str,
    regional_units: int,
    antennas: int,
    when: datetime | None,
    *,
    title: str,
    company: str,
    logo_path: Path | None,
    settings: Settings,
    detail_line: str | None = None,
    period: str | None = None,
) -> list:
    """Fallback se as faixas OL não existirem no disco."""
    page_w, page_h = A4
    styles = getSampleStyleSheet()
    subtitle = _cover_subtitle(adom, company)
    text_block = [
        Paragraph(
            title,
            ParagraphStyle(
                "T",
                parent=styles["Title"],
                fontSize=22,
                alignment=1,
                textColor=colors.HexColor("#003366"),
                spaceAfter=10,
            ),
        ),
        Paragraph(
            subtitle,
            ParagraphStyle(
                "S",
                parent=styles["Heading2"],
                fontSize=14,
                alignment=1,
                textColor=colors.HexColor("#0066A1"),
                spaceAfter=8,
            ),
        ),
        Paragraph(
            detail_line or f"{regional_units} unidades regionais · {antennas} dispositivos",
            ParagraphStyle("B", parent=styles["Normal"], alignment=1, fontSize=11),
        ),
        Paragraph(
            period or _month_year_label(when),
            ParagraphStyle("M", parent=styles["Normal"], alignment=1, fontSize=11),
        ),
    ]
    logo_cell: Flowable | Spacer = Spacer(1, 0.1 * cm)
    logo_row_h = 0.2 * cm
    if logo_path:
        logo_w, logo_h, align, ox, oy = _logo_layout(settings, logo_path)
        logo_row_h = logo_h + oy + 0.15 * cm
        logo_cell = _CoverLogoSlot(
            logo_path,
            box_w=page_w,
            box_h=logo_row_h,
            logo_w=logo_w,
            logo_h=logo_h,
            align=align,
            offset_x=ox,
            offset_y=oy,
            side_pad=LATERAL_MARGIN,
        )
    text_row_h = max(page_h - logo_row_h - 1.5 * cm, 8 * cm)
    middle = Table(
        [[text_block], [logo_cell]],
        colWidths=[page_w],
        rowHeights=[text_row_h, logo_row_h],
    )
    middle.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (0, 0), "MIDDLE"),
                ("VALIGN", (0, 1), (0, 1), "BOTTOM"),
                ("ALIGN", (0, 0), (0, 0), "CENTER"),
                ("LEFTPADDING", (0, 0), (0, 0), LATERAL_MARGIN),
                ("RIGHTPADDING", (0, 0), (0, 0), LATERAL_MARGIN),
                ("LEFTPADDING", (0, 1), (0, 1), 0),
                ("RIGHTPADDING", (0, 1), (0, 1), 0),
            ]
        )
    )
    return [KeepTogether([middle])]
