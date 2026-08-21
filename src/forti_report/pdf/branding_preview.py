"""PDF de amostra: capa completa + página interna com rodapé tipográfico."""

from __future__ import annotations

from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
)

from forti_report.config import Settings
from forti_report.pdf.cover_page import build_mensal_cover_flowables
from forti_report.pdf.internal_page import (
    draw_internal_page_footer,
    draw_internal_page_header,
    internal_footer_height,
    internal_header_height,
)
from forti_report.pdf.page_layout import LATERAL_MARGIN


def build_branding_preview_pdf(settings: Settings, *, adom: str, display_name: str) -> bytes:
    """
    Gera PDF de verificação:
    - página 1: capa (faixas OL + textos + logo do cliente)
    - página 2: corpo com cabeçalho interno + rodapé tipográfico
    """
    buffer = BytesIO()
    page_w, page_h = A4
    header_h = internal_header_height(settings, page_w)
    footer_h = internal_footer_height()
    label = (display_name or settings.client_display_name or adom or "Cliente").strip()

    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "PreviewBody",
        parent=styles["Normal"],
        fontSize=11,
        leading=16,
        textColor="#333333",
    )
    title = ParagraphStyle(
        "PreviewTitle",
        parent=styles["Heading1"],
        fontSize=16,
        textColor="#003366",
        spaceAfter=12,
    )

    def _on_internal(canvas, doc) -> None:
        canvas.saveState()
        draw_internal_page_header(canvas, settings, header_h=header_h)
        draw_internal_page_footer(
            canvas,
            adom=adom,
            page_num=1,
            total_pages=1,
            footer_h=footer_h,
            display_name=label,
        )
        canvas.restoreState()

    cover_frame = Frame(
        0,
        0,
        page_w,
        page_h,
        id="cover",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    body_frame = Frame(
        LATERAL_MARGIN,
        footer_h + 0.4 * cm,
        page_w - 2 * LATERAL_MARGIN,
        page_h - header_h - footer_h - 0.8 * cm,
        id="body",
    )

    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=0,
        rightMargin=0,
        topMargin=0,
        bottomMargin=0,
    )
    doc.addPageTemplates(
        [
            PageTemplate(id="cover", frames=[cover_frame]),
            PageTemplate(id="internal", frames=[body_frame], onPage=_on_internal),
        ]
    )

    story = [
        *build_mensal_cover_flowables(
            settings,
            adom=adom,
            regional_units=6,
            antennas=10,
        ),
        NextPageTemplate("internal"),
        PageBreak(),
        Paragraph("Prévia — página interna (corpo do PDF)", title),
        Paragraph(
            f"Cliente: <b>{label}</b> · ADOM técnico: <b>{adom}</b>",
            body,
        ),
        Spacer(1, 0.4 * cm),
        Paragraph(
            "Esta página existe só para validar o <b>cabeçalho interno</b> e o "
            "<b>rodapé tipográfico</b> (linha vermelha + texto + numeração). "
            "A capa completa está na página anterior.",
            body,
        ),
    ]
    doc.build(story)
    return buffer.getvalue()


def branding_preview_filename(slug: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in slug) or "cliente"
    return f"previa_branding_{safe}.pdf"
