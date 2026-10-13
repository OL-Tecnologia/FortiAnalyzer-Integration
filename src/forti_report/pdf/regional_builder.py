"""PDF consolidado por unidade regional (vários dispositivos)."""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from forti_report.charts.plotly_charts import chart_to_png_bytes, top_sites_bar_chart
from forti_report.config import Settings, get_settings
from forti_report.data.hierarchy import AntennaInfo, RegionalUnit
from forti_report.pdf.device_table import DEVICE_TABLE_HEADER, device_table_row
from forti_report.pdf.sections.base import SectionRegistry
from forti_report.pdf.sections.registry import build_default_registry


class RegionalPdfBuilder:
    """Gera um PDF por unidade regional com seção por dispositivo."""

    def __init__(
        self,
        settings: Settings | None = None,
        registry: SectionRegistry | None = None,
    ):
        self.settings = settings or get_settings()
        self.registry = registry or build_default_registry()

    def build(self, regional_unit: RegionalUnit, output_path: Path) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc = _RegionalPdfDoc(str(output_path), settings=self.settings, unit=regional_unit, registry=self.registry)
        doc.build_story()
        return output_path


class _RegionalPdfDoc(BaseDocTemplate):
    def __init__(self, filename: str, *, settings: Settings, unit: RegionalUnit, registry: SectionRegistry):
        super().__init__(filename, pagesize=A4)
        apply_lateral_margins(self)
        self.settings = settings
        self.unit = unit
        self.registry = registry
        self._header_h = 1.6 * cm
        self._footer_h = 1.2 * cm
        frame = Frame(
            self.leftMargin,
            self.bottomMargin + self._footer_h,
            self.width,
            self.height - self._header_h - self._footer_h,
            id="content",
        )
        self.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=self._draw_header_footer)])

    def _asset(self, path):
        return path if path.is_file() else None

    def _draw_header_footer(self, canvas, doc):
        canvas.saveState()
        page_w, page_h = A4
        header = self._asset(self.settings.pdf_header_image)
        if header:
            canvas.drawImage(str(header), 0, page_h - self._header_h, width=page_w, height=self._header_h, preserveAspectRatio=True, mask="auto")
        footer = self._asset(self.settings.pdf_footer_image)
        if footer:
            canvas.drawImage(str(footer), 0, 0, width=page_w, height=self._footer_h, preserveAspectRatio=True, mask="auto")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(page_w - 1.5 * cm, 0.6 * cm, f"Página {doc.page}")
        canvas.restoreState()

    def build_story(self):
        story: list = []
        story.extend(self._cover())
        story.append(PageBreak())
        story.extend(self._toc())
        story.append(PageBreak())
        story.extend(self._summary_table())
        story.append(PageBreak())

        for antenna in self.unit.antennas:
            story.extend(self._antenna_section(antenna))
            story.append(PageBreak())

        self.build(story)

    def _cover(self):
        cover = self._asset(self.settings.pdf_cover_image)
        if cover:
            return [Image(str(cover), width=A4[0], height=A4[1])]
        styles = getSampleStyleSheet()
        return [
            Spacer(1, 7 * cm),
            Paragraph(self.unit.display_name, ParagraphStyle("T", parent=styles["Title"], fontSize=22, textColor=colors.HexColor("#003366"))),
            Paragraph(f"{self.unit.antenna_count} dispositivo(s)", styles["Normal"]),
            Paragraph(datetime.now().strftime("%d/%m/%Y"), styles["Normal"]),
        ]

    def _toc(self):
        styles = getSampleStyleSheet()
        entries = [
            Paragraph("Sumário", ParagraphStyle("H", parent=styles["Heading1"], textColor=colors.HexColor("#003366"))),
            Spacer(1, 0.3 * cm),
            Paragraph('<a href="#resumo-unidade">Resumo da unidade regional</a>', styles["Normal"]),
        ]
        for ant in self.unit.antennas:
            anchor = _antenna_anchor(ant)
            entries.append(
                Paragraph(
                    f'<a href="#{anchor}" color="#0066A1">{ant.display_name}</a> '
                    f'<font size="9" color="#666">({ant.device_name})</font>',
                    styles["Normal"],
                )
            )
        entries.append(Spacer(1, 0.5 * cm))
        return entries

    def _summary_table(self):
        styles = getSampleStyleSheet()
        rows = [DEVICE_TABLE_HEADER.copy()]
        for ant in self.unit.antennas:
            rows.append(device_table_row(ant))
        table = Table(rows, colWidths=[2.0 * cm, 3.5 * cm, 1.8 * cm, 1.0 * cm, 1.1 * cm, 1.2 * cm, 0.9 * cm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#003366")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F0F4F8")]),
        ]))
        return [
            Paragraph('<a name="resumo-unidade"/>', styles["Normal"]),
            Paragraph("Resumo da unidade regional", styles["Heading1"]),
            Spacer(1, 0.3 * cm),
            table,
        ]

    def _antenna_section(self, antenna: AntennaInfo):
        styles = getSampleStyleSheet()
        anchor = _antenna_anchor(antenna)
        flow: list = [
            Paragraph(f'<a name="{anchor}"/>', styles["Normal"]),
            Paragraph(
                antenna.display_name,
                ParagraphStyle("H", parent=styles["Heading1"], textColor=colors.HexColor("#003366")),
            ),
            Paragraph(f"<b>Unidade:</b> {antenna.display_name}", styles["Normal"]),
            Paragraph(f"<b>Dispositivo:</b> {antenna.device_name}", styles["Normal"]),
        ]
        if antenna.platform:
            flow.append(Paragraph(f"<b>Plataforma:</b> {antenna.platform}", styles["Normal"]))
        if antenna.ip:
            flow.append(Paragraph(f"<b>IP:</b> {antenna.ip}", styles["Normal"]))
        flow.append(Spacer(1, 0.3 * cm))

        rep = antenna.report
        if not rep:
            flow.append(Paragraph("Nenhum relatório vinculado no período.", styles["Italic"]))
            return flow

        if rep.report_title:
            flow.append(Paragraph(f"<b>Relatório:</b> {rep.report_title}", styles["Normal"]))
        if rep.report_name:
            flow.append(Paragraph(f"<b>Arquivo FAZ:</b> {rep.report_name}", styles["Normal"]))
        if rep.period_start and rep.period_end:
            flow.append(
                Paragraph(
                    f"<b>Período:</b> {rep.period_start:%d/%m/%Y} — {rep.period_end:%d/%m/%Y}",
                    styles["Normal"],
                )
            )
        if rep.faz_tid:
            flow.append(Paragraph(f"<b>TID:</b> {rep.faz_tid}", styles["Normal"]))
        if rep.import_note:
            flow.append(Spacer(1, 0.2 * cm))
            flow.append(Paragraph(f"<i>{rep.import_note}</i>", styles["Normal"]))

        if rep.sections:
            flow.append(Spacer(1, 0.4 * cm))
            for section_impl in self.registry.for_unit(rep):
                flow.extend(section_impl.build_flowables(rep))
        elif rep.faz_tid:
            flow.append(Spacer(1, 0.3 * cm))
            flow.append(
                Paragraph(
                    "Relatório vinculado. Conteúdo detalhado pendente de download ou parser XML.",
                    styles["Italic"],
                )
            )

        return flow


def _antenna_anchor(antenna: AntennaInfo) -> str:
    return f"dispositivo-{antenna.site_slug.replace('-', '_')}"
