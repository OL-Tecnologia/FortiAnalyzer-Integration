"""PDF unificado MENSAL- RELATÓRIO GERAL — 6 unidades, 11 antenas."""

from __future__ import annotations

import io
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Frame,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    NextPageTemplate,
)

from forti_report.charts.plotly_charts import (
    bandwidth_timeline_chart,
    category_pie_chart,
    chart_to_png_bytes,
    ranked_horizontal_chart,
    top_users_bar_chart,
)
from forti_report.services.mensal_cache import chart_scope_for_unit
from forti_report.config import Settings, get_settings
from forti_report.data.hierarchy import AntennaInfo, RegionalUnit
from forti_report.data.mensal_models import MensalGeralReport, PolicyDetailRow
from forti_report.data.models import UnitReport
from forti_report.data.parsers.mensal_utils import filter_ranked, format_bandwidth, ranked_chart_values, timeline_has_signal
from forti_report.data.wan_models import RankedItem
from forti_report.pdf.mensal_toc import (
    TocEntryMarker,
    create_mensal_table_of_contents,
    register_toc_entry,
    section_anchor,
    toc_marker,
    toc_page_flowables,
)
from forti_report.pdf.device_table import (
    DEVICE_TABLE_HEADER,
    device_table_min_widths,
    device_table_row,
)
from forti_report.pdf.cover_page import build_mensal_cover_flowables
from forti_report.pdf.internal_page import (
    draw_internal_page_footer,
    draw_internal_page_header,
    internal_footer_height,
    internal_header_height,
    prewarm_header_logo,
)
from forti_report.pdf.page_layout import apply_lateral_margins
from forti_report.pdf.table_utils import data_table, ranked_table
from forti_report.services.progress import clamp_percent


_SECTION_GAP = 0.12 * cm
_BLOCK_GAP = 0.35 * cm  # separação visual entre blocos no mesmo fluxo
_LOCALITY_BREAK = 3.5 * cm  # quebra de página só se faltar espaço útil


class UnifiedMensalPdfBuilder:
    """Gera um único PDF com todas as antenas agrupadas por unidade regional."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def build(
        self,
        regional_units: list[RegionalUnit],
        output_path: Path,
        *,
        adom: str = "CRUZ_AZUL",
        on_progress: Callable[[int, str], None] | None = None,
    ) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc = _UnifiedMensalDoc(
            str(output_path),
            settings=self.settings,
            regional_units=regional_units,
            adom=adom,
            on_progress=on_progress,
        )
        doc.build_story()
        return output_path


class _UnifiedMensalDoc(BaseDocTemplate):
    def __init__(
        self,
        filename: str,
        *,
        settings: Settings,
        regional_units: list[RegionalUnit],
        adom: str,
        on_progress: Callable[[int, str], None] | None = None,
    ):
        super().__init__(filename, pagesize=A4)
        apply_lateral_margins(self)
        self.settings = settings
        self.regional_units = regional_units
        self.adom = adom
        self._on_progress = on_progress
        self._pdf_steps = 3 + sum(1 + len(ru.antennas) for ru in regional_units) + 1
        self._pdf_step = 0
        self._header_h = internal_header_height(settings)
        self._footer_h = internal_footer_height()
        prewarm_header_logo(settings, header_h=self._header_h)
        cover_frame = Frame(0, 0, A4[0], A4[1], id="cover", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        frame = Frame(
            self.leftMargin,
            self.bottomMargin + self._footer_h,
            self.width,
            self.height - self._header_h - self._footer_h,
            id="content",
        )
        self.addPageTemplates([
            PageTemplate(id="cover", frames=[cover_frame]),
            PageTemplate(id="toc", frames=[frame]),
            PageTemplate(id="main", frames=[frame], onPage=self._on_page),
        ])
        self._toc = create_mensal_table_of_contents()
        self._total_pages = 0
        self._current_chart_scope = ""

    def afterPage(self) -> None:
        self._total_pages = max(self._total_pages, self.page)

    def afterFlowable(self, flowable) -> None:
        register_toc_entry(self, flowable)

    @property
    def total_antennas(self) -> int:
        return sum(ru.antenna_count for ru in self.regional_units)

    def _asset(self, path: Path):
        return path if path.is_file() else None

    def _on_page(self, canvas, doc):
        canvas.saveState()
        draw_internal_page_header(canvas, self.settings, header_h=self._header_h)
        draw_internal_page_footer(
            canvas,
            adom=self.adom,
            page_num=doc.page,
            total_pages=getattr(doc, "_total_pages", doc.page) or doc.page,
            footer_h=self._footer_h,
        )
        canvas.restoreState()

    def _tick_pdf(self, message: str) -> None:
        if not self._on_progress:
            return
        self._pdf_step += 1
        total = max(self._pdf_steps, 1)
        pct = clamp_percent(int(100 * self._pdf_step / total))
        self._on_progress(pct, message)

    def build_story(self):
        story: list = []
        self._tick_pdf("Gerando capa...")
        story.extend(self._cover())
        story.append(NextPageTemplate("toc"))
        story.append(PageBreak())
        self._tick_pdf("Montando sumário...")
        story.extend(toc_page_flowables(self._toc))
        story.append(NextPageTemplate("main"))
        story.append(PageBreak())
        self._tick_pdf("Tabela resumo global...")
        story.extend(self._pack_section(self._global_summary()))

        for ru in self.regional_units:
            story.append(PageBreak())
            self._tick_pdf(f"Unidade {ru.display_name} — introdução...")
            story.extend(self._pack_section(self._regional_intro(ru)))
            for ant_idx, antenna in enumerate(ru.antennas):
                if ant_idx > 0:
                    story.append(CondPageBreak(_LOCALITY_BREAK))
                self._tick_pdf(f"PDF: {antenna.display_name} ({ru.display_name})...")
                story.extend(self._antenna_detail(ru, antenna))

        self._tick_pdf("Renderizando páginas do PDF...")
        self.multiBuild(story)

    def _is_toc_flowable(self, item) -> bool:
        if isinstance(item, TocEntryMarker):
            return True
        if isinstance(item, Paragraph) and getattr(item.style, "name", "") == "Anchor":
            return True
        return False

    def _pack_section(self, block: list) -> list:
        """Mantém título + tabela/gráfico na mesma página (marcadores TOC ficam fora)."""
        if not block:
            return []
        markers = [x for x in block if self._is_toc_flowable(x)]
        content = [x for x in block if not self._is_toc_flowable(x)]
        if not content:
            return markers
        return markers + [KeepTogether(content)]

    def _cover(self):
        legacy = self._asset(self.settings.pdf_cover_image)
        has_parts = (
            self._asset(self.settings.pdf_cover_header_image)
            or self._asset(self.settings.pdf_cover_footer_image)
        )
        if legacy and not has_parts:
            return [Image(str(legacy), width=A4[0], height=A4[1])]
        return build_mensal_cover_flowables(
            self.settings,
            adom=self.adom,
            regional_units=len(self.regional_units),
            antennas=self.total_antennas,
        )

    def _global_summary(self):
        styles = getSampleStyleSheet()
        rows = [DEVICE_TABLE_HEADER.copy()]
        for ru in self.regional_units:
            for ant in ru.antennas:
                rows.append(device_table_row(ant))
        min_w = device_table_min_widths()
        return [
            *toc_marker(0, "RESUMO GLOBAL — UNIDADES E DISPOSITIVOS", "resumo-global"),
            Paragraph("Resumo global — Unidades e Dispositivos", styles["Heading1"]),
            Spacer(1, _SECTION_GAP),
            data_table(
                rows,
                self.width,
                min_widths=min_w,
                font_size=7,
                header_font_size=9,
                nowrap_cols=frozenset({3, 4, 5, 6}),
                stretch_col=1,
            ),
            Spacer(1, _SECTION_GAP),
        ]

    def _regional_intro(self, ru: RegionalUnit):
        styles = getSampleStyleSheet()
        anchor = _regional_anchor(ru)
        linked = ru.reports_linked
        with_data = sum(1 for a in ru.antennas if a.report and a.report.mensal and a.report.mensal.has_content)
        rows = [DEVICE_TABLE_HEADER.copy()]
        for ant in ru.antennas:
            rows.append(device_table_row(ant))
        return [
            *toc_marker(0, ru.display_name.upper(), anchor),
            Paragraph(ru.display_name, styles["Heading1"]),
            Paragraph(
                f"{ru.antenna_count} dispositivo(s) · {linked} com relatório vinculado · "
                f"{with_data} com dados parseados",
                styles["Normal"],
            ),
            Spacer(1, _SECTION_GAP),
            data_table(
                rows,
                self.width,
                min_widths=device_table_min_widths(),
                font_size=7,
                header_font_size=9,
                nowrap_cols=frozenset({3, 4, 5, 6}),
                stretch_col=1,
            ),
            Spacer(1, _SECTION_GAP),
        ]

    def _antenna_detail(self, ru: RegionalUnit, antenna: AntennaInfo):
        styles = getSampleStyleSheet()
        body = ParagraphStyle("B", parent=styles["Normal"], fontSize=10, leading=14, alignment=4)
        anchor = _antenna_anchor(ru, antenna)
        rep = antenna.report
        markers = toc_marker(1, f"{antenna.display_name} — {ru.display_name}", anchor)
        header: list = [
            Paragraph(
                f"{antenna.display_name} — {ru.display_name}",
                ParagraphStyle("H", parent=styles["Heading1"], textColor=colors.HexColor("#003366")),
            ),
            Paragraph(f"<b>Unidade:</b> {antenna.display_name}", styles["Normal"]),
            Paragraph(f"<b>Dispositivo:</b> {antenna.device_name}", styles["Normal"]),
        ]
        if antenna.ip:
            header.append(Paragraph(f"<b>IP:</b> {antenna.ip}", styles["Normal"]))
        if antenna.platform:
            header.append(Paragraph(f"<b>Plataforma:</b> {antenna.platform}", styles["Normal"]))
        header.append(Spacer(1, 0.08 * cm))

        if not rep:
            header.append(Paragraph("Nenhum relatório MENSAL vinculado no período.", styles["Italic"]))
            return markers + [KeepTogether(header)]

        if rep.report_title:
            header.append(Paragraph(f"<b>Schedule:</b> {rep.report_title}", styles["Normal"]))
        if rep.period_start and rep.period_end:
            header.append(
                Paragraph(
                    f"<b>Período:</b> {rep.period_start:%d/%m/%Y} — {rep.period_end:%d/%m/%Y}",
                    styles["Normal"],
                )
            )
        if rep.faz_tid:
            header.append(Paragraph(f"<b>TID FAZ:</b> {rep.faz_tid}", styles["Normal"]))

        flow: list = markers + [KeepTogether(header)]

        mensal = rep.mensal
        if mensal and mensal.has_content:
            prefix = f"{anchor}-"
            self._current_chart_scope = chart_scope_for_unit(rep)
            flow.extend(self._mensal_sections(mensal, styles, body, anchor_prefix=prefix))
        else:
            flow.append(Spacer(1, _SECTION_GAP))
            note = rep.import_note or "Conteúdo detalhado indisponível."
            flow.append(Paragraph(f"<i>{note}</i>", styles["Normal"]))
            flow.append(Spacer(1, 0.08 * cm))
            flow.append(
                Paragraph(
                    "Seções previstas neste relatório (layout MENSAL GERAL): "
                    "Resumo de Utilização Web, Top Usuários (permitidos/bloqueados), "
                    "Categorias de Sites, Top Sites por Navegação, Usuários de Risco, "
                    "SD-WAN e Consumo de Banda.",
                    body,
                )
            )
        return flow

    def _mensal_sections(
        self,
        mensal: MensalGeralReport,
        styles,
        body,
        *,
        anchor_prefix: str = "",
    ) -> list:
        flow: list = [
            Spacer(1, _SECTION_GAP),
            Paragraph("Análise Abrangente da Navegação Web da Rede", styles["Heading2"]),
            Paragraph(
                "Relatório consolidado para apoio à tomada de decisão (BI) da operação Cruz Azul. "
                "Indicadores de utilização web, risco, consumo de banda e políticas de firewall "
                f"referentes ao dispositivo <b>{mensal.device_name}</b>.",
                body,
            ),
        ]
        sections = [
            ("resumo", self._summary_section(mensal, styles, anchor_prefix)),
            ("timeline", self._timeline_section(mensal, styles, anchor_prefix)),
            (
                "usuarios-permitidos",
                self._users_section(mensal.top_users_allowed, styles, "Permitidas", anchor_prefix),
            ),
            (
                "usuarios-bloqueados",
                self._users_section(mensal.top_users_blocked, styles, "Bloqueadas", anchor_prefix),
            ),
            (
                "app-visibility",
                self._app_visibility_section(mensal, styles, anchor_prefix),
            ),
            (
                "navegacao-cat",
                self._ranked_section(
                    mensal.top_browsing_categories,
                    styles,
                    "Categoria com maior tempo de Navegação",
                    "Tempo (hh:mm:ss)",
                    f"{anchor_prefix}nav-cat",
                    label_header="Categoria",
                ),
            ),
            ("categorias-sites", None),
            (
                "bloqueio-resumo",
                self._ranked_section(
                    mensal.blocked_usage_summary,
                    styles,
                    "Uso da Web — Usuários e Categorias Mais Bloqueados",
                    "Requisições",
                    f"{anchor_prefix}bloq-cat",
                    label_header="Usuário",
                    pct_col=True,
                    category_col=True,
                    chart_min_items=5,
                ),
            ),
            ("risco", self._risk_section(mensal, styles, anchor_prefix)),
            (
                "phishing",
                self._ranked_section(
                    mensal.phishing_victims,
                    styles,
                    "Vítimas de Sites de Phishing",
                    "Ocorrências",
                    f"{anchor_prefix}phishing",
                    label_header="Usuário / Site",
                    pct_col=True,
                ),
            ),
            (
                "web-apps",
                self._ranked_section(
                    mensal.top_web_apps,
                    styles,
                    "Principais Aplicativos Web por Largura de Banda",
                    "Banda",
                    f"{anchor_prefix}web-apps",
                    label_header="Aplicação",
                ),
            ),
            ("sdwan", None),
            (
                "banda-usuarios",
                self._ranked_section(
                    mensal.top_bandwidth_users,
                    styles,
                    "Top 10 Usuários — Consumo de Banda",
                    "Banda",
                    f"{anchor_prefix}banda-u",
                    label_header="Usuário",
                ),
            ),
            (
                "banda-top",
                self._ranked_section(
                    mensal.top_bandwidth_timeline_users,
                    styles,
                    "Top Maiores Consumidores de Largura de Banda",
                    "Banda",
                    f"{anchor_prefix}banda-top",
                    label_header="Usuário",
                ),
            ),
            (
                "pol-banda",
                self._ranked_section(
                    mensal.policy_by_bandwidth,
                    styles,
                    "Regras mais utilizadas (por banda)",
                    "Bytes",
                    f"{anchor_prefix}pol-bw",
                    label_header="Política",
                ),
            ),
            (
                "pol-sessao",
                self._ranked_section(
                    mensal.policy_by_session,
                    styles,
                    "Regras mais utilizadas (por sessão)",
                    "Sessões",
                    f"{anchor_prefix}pol-sess",
                    label_header="Política",
                ),
            ),
            ("pol-detalhes", self._policy_details_section(mensal, styles, anchor_prefix)),
        ]
        for key, block in sections:
            if key == "categorias-sites":
                flow.extend(self._categories_and_sites_sections(mensal, styles, anchor_prefix))
            elif key == "sdwan":
                flow.extend(self._sdwan_full_section(mensal, styles, anchor_prefix))
            elif block:
                flow.extend(self._pack_section(block))
        return flow

    def _summary_section(
        self, mensal: MensalGeralReport, styles, anchor_prefix: str
    ) -> list:
        s = mensal.summary
        rows = [
            ["Métrica", "Valor"],
            ["Requisições permitidas", s.allowed_requests or "—"],
            ["Requisições bloqueadas", s.blocked_requests or "—"],
            ["Total requisições (macro)", mensal.macros.get("Web Usage Request Count", s.total_requests or "—")],
            ["Usuários (macro)", str(s.users or mensal.macros.get("Web Usage User Count", "—"))],
            ["Categorias (macro)", str(s.categories or mensal.macros.get("Web Usage Category Count", "—"))],
            ["Aplicações (macro)", str(s.applications or mensal.macros.get("Web Usage Application Count", "—"))],
            ["Sites maliciosos", str(s.malicious_sites or mensal.macros.get("web Usage Total Malicious Websites Count", "—"))],
            ["SD-WAN disponibilidade", mensal.macros.get("SD-WAN Device Availability Percentage", "—")],
            ["SD-WAN banda total", mensal.macros.get("SD-WAN Total Bandwidth", "—")],
        ]
        flow: list = [
            *section_anchor(f"{anchor_prefix}resumo"),
            Spacer(1, _SECTION_GAP),
            Paragraph("RESUMO DE UTILIZAÇÃO WEB", styles["Heading2"]),
            data_table(
                rows,
                self.width,
                min_widths=[5.5 * cm, 4.0 * cm],
                font_size=8,
                header_font_size=9,
                nowrap_cols=frozenset({1}),
                stretch_col=0,
            ),
        ]
        return flow

    def _timeline_section(
        self, mensal: MensalGeralReport, styles, anchor_prefix: str
    ) -> list:
        if not mensal.bandwidth_timeline or not timeline_has_signal(mensal.bandwidth_timeline):
            return []
        flow: list = [
            *section_anchor(f"{anchor_prefix}timeline"),
            Spacer(1, _SECTION_GAP),
            Paragraph(
                "Tempo de Uso da Internet: Principais Consumidores de Banda",
                styles["Heading2"],
            ),
        ]
        try:
            if not self.settings.pdf_mensal_charts:
                return flow
            fig = bandwidth_timeline_chart(mensal.bandwidth_timeline)
            if fig:
                png = chart_to_png_bytes(
                    fig,
                    cache_key=f"timeline-v3:{mensal.device_name}",
                    cache_scope=self._current_chart_scope or None,
                )
                flow.append(embed_chart(png, max_width=16 * cm, max_height=8.5 * cm))
        except Exception:
            pass
        return flow

    def _append_chart(
        self,
        flow: list,
        fig,
        *,
        max_height: float = 7 * cm,
        cache_key: str | None = None,
        gap_before: float = 0.08,
    ) -> None:
        if not self.settings.pdf_mensal_charts:
            return
        try:
            if not fig:
                return
            png = chart_to_png_bytes(
                fig,
                cache_key=cache_key,
                cache_scope=self._current_chart_scope or None,
            )
            if gap_before > 0:
                flow.append(Spacer(1, gap_before * cm))
            flow.append(embed_chart(png, max_width=16 * cm, max_height=max_height))
        except Exception:
            pass

    def _categories_and_sites_sections(
        self, mensal: MensalGeralReport, styles, anchor_prefix: str
    ) -> list:
        """Categorias (tabela) → Top 20 Sites (tabela) → rosca, sem espaço entre tabela e gráfico."""
        flow: list = []
        tight_h2 = ParagraphStyle(
            "Heading2Tight",
            parent=styles["Heading2"],
            spaceBefore=0,
            spaceAfter=2,
        )
        cat_items = filter_ranked(mensal.top_categories)
        if cat_items:
            flow.extend(
                self._pack_section([
                    *section_anchor(f"{anchor_prefix}categorias"),
                    Spacer(1, _SECTION_GAP),
                    Paragraph(
                        "360 Security — Principais Categorias de Web Visitadas",
                        styles["Heading2"],
                    ),
                    ranked_table(
                        cat_items[:30],
                        self.width,
                        label_header="Categoria",
                        value_header="Contagem",
                        pct_col=True,
                    ),
                ])
            )

        site_items = filter_ranked(mensal.top_sites_by_browsing)
        if site_items:
            rows = [["#", "Site", "Categoria", "Tempo"]]
            for site in site_items:
                rows.append([
                    str(site.rank),
                    site.label,
                    site.category or "—",
                    site.value or "—",
                ])
            flow.extend(
                self._pack_section([
                    *section_anchor(f"{anchor_prefix}top-sites"),
                    Paragraph("Top 20 Sites por Tempo de Navegação", tight_h2),
                    data_table(
                        rows,
                        self.width,
                        min_widths=[0.8 * cm, 4.0 * cm, 3.0 * cm, 2.0 * cm],
                        font_size=7,
                        header_font_size=9,
                        nowrap_cols=frozenset({0, 3}),
                        stretch_col=1,
                    ),
                ])
            )
            if cat_items:
                self._append_chart(
                    flow,
                    category_pie_chart(cat_items),
                    max_height=6.5 * cm,
                    cache_key=f"categories:{anchor_prefix}",
                    gap_before=0,
                )
            labels, _ = ranked_chart_values(site_items, max_items=15)
            if len(labels) >= 3:
                self._append_chart(
                    flow,
                    ranked_horizontal_chart(
                        site_items,
                        title="Top sites — tempo de navegação (minutos)",
                        value_label="Minutos",
                        max_items=15,
                    ),
                    cache_key=f"sites:{anchor_prefix}",
                )
        elif cat_items:
            self._append_chart(
                flow,
                category_pie_chart(cat_items),
                max_height=6.5 * cm,
                cache_key=f"categories:{anchor_prefix}",
            )
        return flow

    def _app_visibility_section(
        self, mensal: MensalGeralReport, styles, anchor_prefix: str
    ) -> list:
        items = filter_ranked(mensal.app_visibility)
        if not items:
            return []
        rows = [["#", "Categoria de Aplicação", "Qtd. Apps", "% do Total"]]
        for item in items:
            rows.append([
                str(item.rank),
                item.label,
                item.value or "—",
                item.percentage or "—",
            ])
        flow: list = [
            *section_anchor(f"{anchor_prefix}app-vis"),
            Spacer(1, _SECTION_GAP),
            Paragraph("360° Application Visibility and Control", styles["Heading2"]),
            data_table(
                rows,
                self.width,
                min_widths=[0.7 * cm, 5.5 * cm, 2.0 * cm, 2.0 * cm],
                font_size=7,
                header_font_size=9,
                nowrap_cols=frozenset({0, 2, 3}),
                stretch_col=1,
            ),
        ]
        labels, _ = ranked_chart_values(items, max_items=12)
        if len(labels) >= 3:
            self._append_chart(
                flow,
                ranked_horizontal_chart(
                    items,
                    title="360° Application Visibility and Control",
                    value_label="Qtd. Apps",
                    max_items=12,
                ),
                cache_key=f"app-vis:{mensal.device_name}",
            )
        return flow

    def _users_section(
        self, items: list[RankedItem], styles, label: str, anchor_prefix: str
    ) -> list:
        items = filter_ranked(items)
        if not items:
            return []
        slug = "permitidas" if "Permit" in label else "bloqueadas"
        flow: list = [
            *section_anchor(f"{anchor_prefix}usuarios-{slug}"),
            Spacer(1, _SECTION_GAP),
            Paragraph(f"Top 10 Usuários por Requisições {label}", styles["Heading2"]),
            ranked_table(
                items,
                self.width,
                label_header="Usuário",
                value_header="Requisições",
                pct_col=True,
            ),
        ]
        labels, _ = ranked_chart_values(items, max_items=10)
        if len(labels) >= 4:
            self._append_chart(
                flow,
                top_users_bar_chart(items, title=f"Top usuários — {label}"),
                cache_key=f"users-{slug}:{anchor_prefix}",
            )
        return flow

    def _risk_section(self, mensal: MensalGeralReport, styles, anchor_prefix: str) -> list:
        items = filter_ranked(mensal.top_risk_users)
        if not items:
            return []
        return [
            *section_anchor(f"{anchor_prefix}risco"),
            Spacer(1, _SECTION_GAP),
            Paragraph("Principais Usuários que Acessam Sites de Risco", styles["Heading2"]),
            ranked_table(
                items,
                self.width,
                label_header="Usuário",
                value_header="Requisições",
                pct_col=True,
            ),
        ]

    def _ranked_section(
        self,
        items: list[RankedItem],
        styles,
        title: str,
        value_header: str,
        anchor: str,
        *,
        label_header: str = "Nome",
        pct_col: bool = False,
        category_col: bool = False,
        show_chart: bool = False,
        chart_min_items: int = 5,
    ) -> list:
        items = filter_ranked(items)
        if not items:
            return []
        flow: list = [
            *section_anchor(anchor),
            Spacer(1, _SECTION_GAP),
            Paragraph(title, styles["Heading2"]),
            ranked_table(
                items,
                self.width,
                label_header=label_header,
                value_header=value_header,
                pct_col=pct_col,
                category_col=category_col,
            ),
        ]
        if show_chart:
            labels, _ = ranked_chart_values(items, max_items=12)
            if len(labels) >= chart_min_items:
                self._append_chart(
                    flow,
                    ranked_horizontal_chart(items, title=title, value_label=value_header),
                    cache_key=f"ranked:{anchor}",
                )
        return flow

    def _sdwan_full_section(
        self, mensal: MensalGeralReport, styles, anchor_prefix: str
    ) -> list:
        if not (
            mensal.sdwan_apps
            or mensal.sdwan_destinations
            or mensal.sdwan_users
            or mensal.macros.get("SD-WAN Total Bandwidth")
        ):
            return []

        flow: list = [
            *section_anchor(f"{anchor_prefix}sdwan"),
        ]
        apps = filter_ranked(mensal.sdwan_apps) if mensal.sdwan_apps else []
        dest = filter_ranked(mensal.sdwan_destinations) if mensal.sdwan_destinations else []
        users = filter_ranked(mensal.sdwan_users) if mensal.sdwan_users else []

        header_block: list = [
            Spacer(1, _SECTION_GAP),
            Paragraph("Aplicações SD-WAN e Consumo de Banda", styles["Heading2"]),
        ]
        if apps:
            header_block.extend([
                Paragraph("<b>Distribuição de Tráfego por Aplicação</b>", styles["Normal"]),
                ranked_table(
                    apps,
                    self.width,
                    label_header="Aplicação",
                    value_header="Tráfego",
                ),
            ])
        flow.extend(self._pack_section(header_block))

        if dest:
            flow.extend(
                self._pack_section([
                    Spacer(1, 0.08 * cm),
                    Paragraph(
                        "<b>Principais fontes/destinos consumidores de banda</b>",
                        styles["Normal"],
                    ),
                    ranked_table(
                        dest,
                        self.width,
                        label_header="Origem / Destino",
                        value_header="Banda",
                    ),
                ])
            )

        if users:
            flow.extend(
                self._pack_section([
                    Spacer(1, 0.08 * cm),
                    Paragraph(
                        "<b>Top Usuários SD-WAN por Consumo de Banda</b>",
                        styles["Normal"],
                    ),
                    ranked_table(
                        users,
                        self.width,
                        label_header="Usuário",
                        value_header="Banda",
                    ),
                ])
            )

        if not apps and not dest and not users:
            flow.extend(
                self._pack_section([
                    Spacer(1, _SECTION_GAP),
                    Paragraph("Aplicações SD-WAN e Consumo de Banda", styles["Heading2"]),
                ])
            )
        return flow

    def _policy_details_section(
        self, mensal: MensalGeralReport, styles, anchor_prefix: str
    ) -> list:
        if not mensal.policy_details:
            return []
        rows = [["Política", "Bytes", "Sessões", "Origem", "Destino", "Último uso"]]
        for p in mensal.policy_details:
            rows.append([
                p.policy_name[:40],
                format_bandwidth(p.bytes_val) if p.bytes_val else "—",
                p.sessions or "—",
                p.source_interface or "—",
                p.destination_interface or "—",
                (p.last_used or "—")[:16],
            ])
        return [
            *section_anchor(f"{anchor_prefix}pol-detalhes"),
            Spacer(1, _SECTION_GAP),
            Paragraph("Principais Políticas com Detalhes por Consumo de Banda", styles["Heading2"]),
            data_table(
                rows,
                self.width,
                min_widths=[3.5 * cm, 1.5 * cm, 1.2 * cm, 2.0 * cm, 2.0 * cm, 2.0 * cm],
                font_size=6,
                header_font_size=9,
                nowrap_cols=frozenset({1, 2, 5}),
                stretch_col=0,
                allow_split=True,
            ),
        ]


def _regional_anchor(ru: RegionalUnit) -> str:
    return f"unidade-{ru.code}"


def _antenna_anchor(ru: RegionalUnit, antenna: AntennaInfo) -> str:
    return f"{ru.code}-{_slug(antenna.site_slug)}"


def _slug(value: str) -> str:
    return value.replace("-", "_")
