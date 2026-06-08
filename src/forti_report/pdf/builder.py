"""
Montagem do PDF: capa, sumário com links, seções e header/footer em imagem.
"""

from __future__ import annotations

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
)

from forti_report.config import Settings, get_settings
from forti_report.data.models import ReportDocument, UnitReport
from forti_report.pdf.sections.base import SectionRegistry
from forti_report.pdf.page_layout import apply_lateral_margins
from forti_report.pdf.toc import build_toc_paragraphs


class PdfReportBuilder:
    def __init__(
        self,
        settings: Settings | None = None,
        registry: SectionRegistry | None = None,
    ):
        self.settings = settings or get_settings()
        self.registry = registry

    def build_unit_pdf(self, unit: UnitReport, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc = _UnitPdfDocument(
            str(output_path),
            settings=self.settings,
            unit=unit,
            registry=self.registry,
        )
        doc.build_story()
        return output_path

    def build_document(self, document: ReportDocument, output_dir: Path | None = None) -> list[Path]:
        out = output_dir or self.settings.output_dir
        paths: list[Path] = []
        for unit in document.units:
            safe_name = unit.device_name.replace("/", "-").replace(" ", "_")
            path = out / f"{safe_name}_{document.generated_at:%Y%m%d}.pdf"
            paths.append(self.build_unit_pdf(unit, path))
        return paths


class _UnitPdfDocument(BaseDocTemplate):
    def __init__(
        self,
        filename: str,
        *,
        settings: Settings,
        unit: UnitReport,
        registry: SectionRegistry | None,
    ):
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
        template = PageTemplate(id="main", frames=[frame], onPage=self._draw_header_footer)
        self.addPageTemplates([template])

    def _asset(self, path: Path) -> Path | None:
        return path if path.is_file() else None

    def _draw_header_footer(self, canvas, doc) -> None:
        canvas.saveState()
        page_w, page_h = A4

        header = self._asset(self.settings.pdf_header_image)
        if header:
            canvas.drawImage(
                str(header),
                0,
                page_h - self._header_h,
                width=page_w,
                height=self._header_h,
                preserveAspectRatio=True,
                mask="auto",
            )

        footer = self._asset(self.settings.pdf_footer_image)
        if footer:
            canvas.drawImage(
                str(footer),
                0,
                0,
                width=page_w,
                height=self._footer_h,
                preserveAspectRatio=True,
                mask="auto",
            )

        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(page_w - 1.5 * cm, 0.6 * cm, f"Página {doc.page}")
        canvas.restoreState()

    def build_story(self) -> None:
        story: list = []
        story.extend(self._cover_page())
        story.append(PageBreak())

        sections = self.registry.for_unit(self.unit) if self.registry else []
        story.extend(
            build_toc_paragraphs(
                sections,
                unit_label=self.unit.display_name or self.unit.device_name,
            )
        )
        story.append(PageBreak())

        for section in sections:
            story.append(Paragraph(f'<a name="{section.key}"/>', getSampleStyleSheet()["Normal"]))
            story.extend(section.build_flowables(self.unit))
            story.append(PageBreak())

        self.build(story)

    def _cover_page(self) -> list:
        cover = self._asset(self.settings.pdf_cover_image)
        if cover:
            return [Image(str(cover), width=A4[0], height=A4[1])]

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "CoverTitle",
            parent=styles["Title"],
            fontSize=24,
            textColor=colors.HexColor("#003366"),
            spaceAfter=20,
        )
        period = ""
        if self.unit.period_start and self.unit.period_end:
            period = (
                f"{self.unit.period_start:%d/%m/%Y} — {self.unit.period_end:%d/%m/%Y}"
            )
        return [
            Spacer(1, 8 * cm),
            Paragraph(self.unit.display_name, title_style),
            Paragraph(period, styles["Normal"]),
        ]
