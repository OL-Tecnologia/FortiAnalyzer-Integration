"""PDF no layout do SEMANAL Tráfego WAN."""

from __future__ import annotations

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

from forti_report.charts.plotly_charts import (
    category_pie_chart,
    chart_to_png_bytes,
    top_sites_bar_chart,
    top_users_bar_chart,
    traffic_timeline_placeholder,
)
from forti_report.config import Settings, get_settings
from forti_report.data.hierarchy import RegionalUnit
from forti_report.data.models import SiteRankingItem
from forti_report.data.wan_models import RankedItem, WanTrafficReport
from forti_report.pdf.device_table import DEVICE_TABLE_HEADER, device_table_row


class WanRegionalPdfBuilder:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def build(self, regional_unit: RegionalUnit, wan: WanTrafficReport, output_path: Path) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc = _WanPdfDoc(str(output_path), settings=self.settings, unit=regional_unit, wan=wan)
        doc.build_story()
        return output_path


class _WanPdfDoc(BaseDocTemplate):
    WAN_SECTIONS = [
        ("intro", "Análise Abrangente da Navegação Web"),
        ("resumo", "Resumo de Utilização Web"),
        ("usuarios-permitidos", "Top 10 Usuários — Requisições Permitidas"),
        ("usuarios-bloqueados", "Top 10 Usuários — Requisições Bloqueadas"),
        ("categorias", "Categorias de Sites Mais Acessados"),
        ("navegacao", "Navegação Web — Tempo por Categoria"),
        ("top-sites", "Top 20 Sites por Tempo de Navegação"),
        ("risco", "Principais Usuários — Sites de Risco"),
        ("dispositivos", "Dispositivos da unidade regional"),
    ]

    def __init__(self, filename: str, *, settings: Settings, unit: RegionalUnit, wan: WanTrafficReport):
        super().__init__(filename, pagesize=A4)
        apply_lateral_margins(self)
        self.settings = settings
        self.unit = unit
        self.wan = wan
        self._header_h = 1.6 * cm
        self._footer_h = 1.2 * cm
        frame = Frame(
            self.leftMargin,
            self.bottomMargin + self._footer_h,
            self.width,
            self.height - self._header_h - self._footer_h,
            id="content",
        )
        self.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=self._on_page)])

    def _asset(self, path: Path):
        return path if path.is_file() else None

    def _on_page(self, canvas, doc):
        canvas.saveState()
        pw, ph = A4
        header = self._asset(self.settings.pdf_header_image)
        if header:
            canvas.drawImage(str(header), 0, ph - self._header_h, width=pw, height=self._header_h, preserveAspectRatio=True, mask="auto")
        footer = self._asset(self.settings.pdf_footer_image)
        if footer:
            canvas.drawImage(str(footer), 0, 0, width=pw, height=self._footer_h, preserveAspectRatio=True, mask="auto")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(1.5 * cm, 0.55 * cm, f"{self.unit.display_name} — Tráfego WAN")
        canvas.drawRightString(pw - 1.5 * cm, 0.55 * cm, f"Página {doc.page}")
        canvas.restoreState()

    def build_story(self):
        story: list = []
        story.extend(self._cover())
        story.append(PageBreak())
        story.extend(self._toc())
        story.append(PageBreak())

        story.extend(self._section_intro())
        story.append(PageBreak())
        story.extend(self._section_summary())
        story.append(PageBreak())
        story.extend(self._section_users("usuarios-permitidos", self.wan.top_users_allowed, "Permitidas"))
        story.append(PageBreak())
        story.extend(self._section_users("usuarios-bloqueados", self.wan.top_users_blocked, "Bloqueadas"))
        story.append(PageBreak())
        story.extend(self._section_categories())
        story.append(PageBreak())
        story.extend(self._section_browsing())
        story.append(PageBreak())
        story.extend(self._section_top_sites())
        story.append(PageBreak())
        story.extend(self._section_risk())
        story.append(PageBreak())
        story.extend(self._section_antennas())
        self.build(story)

    def _cover(self):
        cover = self._asset(self.settings.pdf_cover_image)
        if cover:
            return [Image(str(cover), width=A4[0], height=A4[1])]
        styles = getSampleStyleSheet()
        return [
            Spacer(1, 6 * cm),
            Paragraph(
                "Relatório Semanal Tráfego WAN",
                ParagraphStyle("T", parent=styles["Title"], fontSize=22, textColor=colors.HexColor("#003366")),
            ),
            Paragraph(self.unit.display_name, styles["Heading2"]),
            Paragraph(datetime.now().strftime("%d/%m/%Y"), styles["Normal"]),
        ]

    def _toc(self):
        styles = getSampleStyleSheet()
        flow = [
            Paragraph("Sumário", ParagraphStyle("H", parent=styles["Heading1"], textColor=colors.HexColor("#003366"))),
            Spacer(1, 0.4 * cm),
        ]
        for key, title in self.WAN_SECTIONS:
            flow.append(Paragraph(f'<a href="#{key}" color="#0066A1">{title}</a>', styles["Normal"]))
        return flow

    def _section_intro(self):
        styles = getSampleStyleSheet()
        body = ParagraphStyle("B", parent=styles["Normal"], fontSize=10, leading=14, alignment=4)
        text = (
            "Este relatório oferece uma análise detalhada das atividades de navegação web, "
            "compiladas a partir dos logs FortiGate pelo FortiAnalyzer. "
            f"Escopo: <b>{self.wan.scope_label}</b> — {len(self.unit.antennas)} dispositivo(s)."
        )
        return [
            Paragraph('<a name="intro"/>', styles["Normal"]),
            Paragraph("Análise Abrangente da Navegação Web da Rede", styles["Heading1"]),
            Spacer(1, 0.3 * cm),
            Paragraph(text, body),
        ]

    def _section_summary(self):
        styles = getSampleStyleSheet()
        s = self.wan.summary
        rows = [
            ["Métrica", "Valor"],
            ["Requisições permitidas", s.allowed_requests or "—"],
            ["Requisições bloqueadas", s.blocked_requests or "—"],
            ["Usuários (ref.)", str(s.users or "—")],
            ["Sites (ref.)", str(s.sites or "—")],
            ["Sites maliciosos (ref.)", str(s.malicious_sites or "—")],
        ]
        table = _styled_table(rows, [6 * cm, 10 * cm])
        flow = [
            Paragraph('<a name="resumo"/>', styles["Normal"]),
            Paragraph("RESUMO DE UTILIZAÇÃO WEB", styles["Heading1"]),
            Spacer(1, 0.3 * cm),
            table,
        ]
        # timeline placeholder chart
        try:
            import io

            fig = traffic_timeline_placeholder()
            png = chart_to_png_bytes(fig, width=780, height=280)
            flow.extend([Spacer(1, 0.4 * cm), Image(io.BytesIO(png), width=16 * cm, height=5.5 * cm)])
        except Exception:
            pass
        return flow

    def _section_users(self, anchor: str, items: list[RankedItem], label: str):
        styles = getSampleStyleSheet()
        flow: list = [
            Paragraph(f'<a name="{anchor}"/>', styles["Normal"]),
            Paragraph(f"Top 10 Usuários por Requisições {label}", styles["Heading1"]),
            Spacer(1, 0.3 * cm),
        ]
        if items:
            flow.append(_ranked_table(items, value_header="Requisições"))
            try:
                import io

                fig = top_users_bar_chart(items, title=f"Top usuários — {label}")
                png = chart_to_png_bytes(fig, width=780, height=320)
                flow.extend([Spacer(1, 0.3 * cm), Image(io.BytesIO(png), width=16 * cm, height=6.5 * cm)])
            except Exception:
                pass
        else:
            flow.append(Paragraph("Sem dados filtrados para esta unidade regional.", styles["Italic"]))
        return flow

    def _section_categories(self):
        styles = getSampleStyleSheet()
        flow: list = [
            Paragraph('<a name="categorias"/>', styles["Normal"]),
            Paragraph("Categorias de Sites Mais Acessados", styles["Heading1"]),
            Spacer(1, 0.3 * cm),
        ]
        if self.wan.top_categories:
            flow.append(_ranked_table(self.wan.top_categories, value_header="Ocorrências"))
            try:
                import io

                fig = category_pie_chart(self.wan.top_categories)
                png = chart_to_png_bytes(fig, width=700, height=350)
                flow.extend([Spacer(1, 0.3 * cm), Image(io.BytesIO(png), width=14 * cm, height=7 * cm)])
            except Exception:
                pass
        else:
            flow.append(Paragraph("Dados consolidados — ver relatório global.", styles["Italic"]))
        return flow

    def _section_browsing(self):
        styles = getSampleStyleSheet()
        flow: list = [
            Paragraph('<a name="navegacao"/>', styles["Normal"]),
            Paragraph("Categoria com maior tempo de Navegação", styles["Heading1"]),
            Spacer(1, 0.3 * cm),
        ]
        if self.wan.top_browsing_categories:
            flow.append(_ranked_table(self.wan.top_browsing_categories, value_header="Tempo (hh:mm:ss)"))
        else:
            flow.append(Paragraph("—", styles["Normal"]))
        return flow

    def _section_top_sites(self):
        styles = getSampleStyleSheet()
        flow: list = [
            Paragraph('<a name="top-sites"/>', styles["Normal"]),
            Paragraph("Top 20 Sites por Tempo de Navegação", styles["Heading1"]),
            Spacer(1, 0.3 * cm),
        ]
        sites = self.wan.top_sites_by_browsing
        if sites:
            rows = [["#", "Site", "Categoria"]]
            for s in sites:
                rows.append([str(s.rank), s.label, s.category or "—"])
            flow.append(_styled_table(rows, [1 * cm, 9 * cm, 5 * cm]))
            try:
                import io

                items = [
                    SiteRankingItem(s.label, hits=s.rank, category=s.category)
                    for s in sites[:15]
                ]
                fig = top_sites_bar_chart(items, title="Top sites — tempo de navegação", metric="hits")
                png = chart_to_png_bytes(fig, width=800, height=380)
                flow.extend([Spacer(1, 0.3 * cm), Image(io.BytesIO(png), width=16 * cm, height=7.5 * cm)])
            except Exception:
                pass
        else:
            flow.append(Paragraph("Sem sites para esta unidade regional.", styles["Italic"]))
        return flow

    def _section_risk(self):
        styles = getSampleStyleSheet()
        flow: list = [
            Paragraph('<a name="risco"/>', styles["Normal"]),
            Paragraph("Principais Usuários que Acessam Sites de Risco", styles["Heading1"]),
            Spacer(1, 0.3 * cm),
        ]
        if self.wan.top_risk_users:
            flow.append(_ranked_table(self.wan.top_risk_users, value_header="Requisições", pct_col=True))
        else:
            flow.append(Paragraph("Sem usuários de risco filtrados.", styles["Italic"]))
        return flow

    def _section_antennas(self):
        styles = getSampleStyleSheet()
        rows = [DEVICE_TABLE_HEADER.copy()]
        for a in self.unit.antennas:
            rows.append(device_table_row(a))
        return [
            Paragraph('<a name="dispositivos"/>', styles["Normal"]),
            Paragraph(f"Dispositivos da unidade regional ({len(self.unit.antennas)})", styles["Heading1"]),
            Spacer(1, 0.3 * cm),
            _styled_table(rows, [2.0 * cm, 3.5 * cm, 1.8 * cm, 1.0 * cm, 1.1 * cm, 1.2 * cm, 0.9 * cm]),
        ]


def _styled_table(rows: list[list[str]], widths: list):
    table = Table(rows, colWidths=widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#003366")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
                ("VALIGN", (0, 1), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F0F4F8")]),
                ("TOPPADDING", (0, 0), (-1, 0), 6),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
            ]
        )
    )
    return table


def _ranked_table(items: list[RankedItem], *, value_header: str, pct_col: bool = False) -> Table:
    if pct_col:
        rows = [["#", "Usuário", value_header, "%"]]
        for i in items:
            rows.append([str(i.rank), i.label, i.value, i.percentage])
        return _styled_table(rows, [1 * cm, 5 * cm, 3 * cm, 2.5 * cm])
    rows = [["#", "Usuário / Site", value_header]]
    for i in items:
        rows.append([str(i.rank), i.label, i.value or i.category or "—"])
    return _styled_table(rows, [1 * cm, 9 * cm, 5 * cm])
