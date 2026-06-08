"""Sumário estilo FAZ — hierarquia, pontilhado e números de página (multiBuild)."""

from __future__ import annotations

from dataclasses import dataclass

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Flowable, Paragraph, Spacer
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.lib.units import cm


@dataclass(frozen=True)
class TocSpec:
    level: int
    title: str
    anchor: str


class TocEntryMarker(Flowable):
    """Marcador invisível que registra entrada no sumário durante a composição."""

    def __init__(self, level: int, title: str, anchor: str) -> None:
        self.level = level
        self.title = title
        self.anchor = anchor

    def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:
        return 0.0, 0.0

    def draw(self) -> None:
        pass


def create_mensal_table_of_contents() -> TableOfContents:
    toc = TableOfContents()
    toc.dotsMinLevel = 0
    page_num_space = 32
    toc.levelStyles = [
        ParagraphStyle(
            name="TOCLevel0",
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=11,
            leftIndent=0,
            rightIndent=page_num_space,
            spaceBefore=2,
            spaceAfter=2,
        ),
        ParagraphStyle(
            name="TOCLevel1",
            fontName="Helvetica",
            fontSize=9,
            leading=10,
            leftIndent=14,
            rightIndent=page_num_space,
            spaceBefore=1,
            spaceAfter=1,
        ),
        ParagraphStyle(
            name="TOCLevel2",
            fontName="Helvetica",
            fontSize=8.5,
            leading=9.5,
            leftIndent=24,
            rightIndent=page_num_space,
            spaceBefore=0,
            spaceAfter=0,
        ),
    ]
    return toc


def section_anchor(anchor: str) -> list:
    """Âncora interna sem entrada no sumário."""
    return [
        Paragraph(f'<a name="{anchor}"/>', ParagraphStyle("Anchor", fontSize=1, leading=1)),
    ]


def toc_marker(level: int, title: str, anchor: str) -> list:
    """Âncora + marcador para registro no sumário."""
    return [
        TocEntryMarker(level, title, anchor),
        Paragraph(f'<a name="{anchor}"/>', ParagraphStyle("Anchor", fontSize=1, leading=1)),
    ]


def toc_page_flowables(toc: TableOfContents) -> list:
    title = ParagraphStyle(
        "TocPageTitle",
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        alignment=0,
        textColor=colors.HexColor("#003366"),
        spaceAfter=10,
    )
    return [
        Paragraph("Sumário", title),
        Spacer(1, 0.15 * cm),
        toc,
    ]


def register_toc_entry(doc, flowable) -> None:
    """Callback afterFlowable — registra marcadores no TableOfContents."""
    if not isinstance(flowable, TocEntryMarker):
        return
    doc.canv.bookmarkPage(flowable.anchor)
    doc.notify(
        "TOCEntry",
        (flowable.level, flowable.title, doc.page, flowable.anchor),
    )
