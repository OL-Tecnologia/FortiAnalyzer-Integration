"""PDF unificado MENSAL- RELATÓRIO GERAL — 6 unidades regionais, 11 dispositivos."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    NextPageTemplate,
)

from forti_report.charts.plotly_charts import (
    allowed_blocked_donut,
    bandwidth_timeline_chart,
    category_pie_chart,
    chart_to_png_bytes,
    create_bar_chart,
    create_donut_chart,
    create_gauge,
    parse_availability_percent,
    ranked_horizontal_chart,
    top_users_bar_chart,
)
from forti_report.services.mensal_cache import chart_scope_for_unit
from forti_report.services.progress import clamp_percent
from forti_report.config import Settings, get_settings
from forti_report.data.hierarchy import AntennaInfo, RegionalUnit
from forti_report.data.mensal_models import MensalGeralReport
from forti_report.data.parsers.mensal_utils import (
    filter_ranked,
    format_bandwidth,
    parse_numeric_value,
    pie_values_from_items,
    ranked_chart_values,
    timeline_has_signal,
)
from forti_report.data.wan_models import RankedItem
from forti_report.pdf.chart_utils import (
    BAR_MAX_HEIGHT,
    CHART_GAP,
    DONUT_MAX_HEIGHT,
    GAUGE_MAX_HEIGHT,
    TIMELINE_MAX_HEIGHT,
    append_chart_with_gap,
)
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
from forti_report.pdf.kpi_cards import kpi_cards_table
from forti_report.pdf.page_layout import apply_lateral_margins
from forti_report.pdf.table_utils import data_table, ranked_table
from forti_report.pdf.sections.resumo_executivo import (
    build_global_resumo_executivo_flowables,
    build_resumo_executivo_flowables,
)
from forti_report.pdf.sections.seguranca import build_seguranca_flowables

_BLOCKED_COLOR = "#E63946"


_SECTION_GAP = 0.12 * cm
_BLOCK_GAP = 0.35 * cm  # separação visual entre blocos no mesmo fluxo


class UnifiedMensalPdfBuilder:
    """Gera um único PDF com todos os dispositivos agrupados por unidade regional."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def build(
        self,
        regional_units: list[RegionalUnit],
        output_path: Path,
        *,
        adom: str = "",
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
            display_name=(self.settings.client_display_name or "").strip(),
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
        story.extend(
            self._pack_section(
                build_global_resumo_executivo_flowables(
                    self.regional_units,
                    width=self.width,
                    styles=getSampleStyleSheet(),
                    charts_enabled=self.settings.pdf_mensal_charts,
                )
            )
        )

        for ru in self.regional_units:
            story.append(PageBreak())
            self._tick_pdf(f"Unidade regional {ru.display_name} — introdução...")
            intro = self._regional_intro(ru)
            intro_markers = [x for x in intro if self._is_toc_flowable(x)]
            intro_content = [x for x in intro if not self._is_toc_flowable(x)]
            antennas = list(ru.antennas)
            if not antennas:
                story.extend(intro_markers + ([KeepTogether(intro_content)] if intro_content else []))
                continue

            # 1º dispositivo cola na tabela regional (evita página só com tabela + buraco).
            first = antennas[0]
            self._tick_pdf(f"PDF: {first.display_name} ({ru.display_name})...")
            story.extend(intro_markers)
            story.extend(self._antenna_detail(ru, first, glue_before=intro_content))
            for antenna in antennas[1:]:
                story.append(PageBreak())
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
        # Capa = texto + logo do tenant (sem cabeçalho/rodapé de imagem).
        # Rodapé tipográfico fica nas páginas internas (internal_page.py).
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
        flow: list = [
            *toc_marker(0, "RESUMO GLOBAL — UNIDADES E DISPOSITIVOS", "resumo-global"),
            Paragraph("Resumo global — Unidades e Dispositivos", styles["Heading1"]),
            Spacer(1, _SECTION_GAP),
        ]
        # Resumo global: tabela + (cards no bloco seguinte) — sem donut.
        flow.extend(
            [
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
        )
        return flow

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

    def _antenna_header(
        self,
        ru: RegionalUnit,
        antenna: AntennaInfo,
        *,
        styles,
    ) -> list:
        """Título + metadados em texto limpo (sem caixas/cards)."""
        rep = antenna.report
        meta_style = ParagraphStyle(
            "AntennaMeta",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#334455"),
            spaceAfter=1,
        )
        header: list = [
            Spacer(1, 0.18 * cm),
            Paragraph(
                f"{antenna.display_name} — {ru.display_name}",
                ParagraphStyle("H", parent=styles["Heading1"], textColor=colors.HexColor("#003366")),
            ),
            Paragraph(f"<b>Dispositivo:</b> {antenna.device_name}", meta_style),
        ]
        if antenna.ip:
            header.append(Paragraph(f"<b>IP:</b> {antenna.ip}", meta_style))
        if antenna.platform:
            header.append(Paragraph(f"<b>Plataforma:</b> {antenna.platform}", meta_style))
        if rep and rep.report_title:
            header.append(Paragraph(f"<b>Schedule:</b> {rep.report_title}", meta_style))
        if rep and rep.period_start and rep.period_end:
            header.append(
                Paragraph(
                    f"<b>Período:</b> {rep.period_start:%d/%m/%Y} — {rep.period_end:%d/%m/%Y}",
                    meta_style,
                )
            )
        header.append(Spacer(1, 0.1 * cm))
        return header

    def _split_resumo_cards_and_charts(self, exec_block: list) -> tuple[list, list, list]:
        """Separa marcadores TOC, parte textual/cards e gráficos do resumo executivo."""
        markers = [x for x in exec_block if self._is_toc_flowable(x)]
        content = [x for x in exec_block if not self._is_toc_flowable(x)]
        cards_part: list = []
        charts_part: list = []
        saw_chart = False
        for item in content:
            if isinstance(item, Image):
                saw_chart = True
            if saw_chart:
                charts_part.append(item)
            else:
                cards_part.append(item)
        return markers, cards_part, charts_part

    def _antenna_detail(
        self,
        ru: RegionalUnit,
        antenna: AntennaInfo,
        *,
        glue_before: list | None = None,
    ):
        styles = getSampleStyleSheet()
        body = ParagraphStyle("B", parent=styles["Normal"], fontSize=10, leading=14, alignment=4)
        anchor = _antenna_anchor(ru, antenna)
        rep = antenna.report
        markers = toc_marker(1, f"{antenna.display_name} — {ru.display_name}", anchor)
        header = self._antenna_header(ru, antenna, styles=styles)
        lead = list(glue_before or []) + header

        if not rep:
            lead.append(Paragraph("Nenhum relatório MENSAL vinculado no período.", styles["Italic"]))
            return markers + [KeepTogether(lead)]

        mensal = rep.mensal
        if mensal and mensal.has_content:
            prefix = f"{anchor}-"
            self._current_chart_scope = chart_scope_for_unit(rep)
            return self._antenna_with_mensal(
                markers=markers,
                lead=lead,
                mensal=mensal,
                styles=styles,
                body=body,
                anchor_prefix=prefix,
            )

        flow: list = markers + [KeepTogether(lead)]
        flow.append(Spacer(1, _SECTION_GAP))
        note = rep.import_note or "Conteúdo detalhado indisponível."
        flow.append(Paragraph(f"<i>{note}</i>", styles["Normal"]))
        flow.append(Spacer(1, 0.08 * cm))
        flow.append(
            Paragraph(
                "Seções previstas neste relatório (layout MENSAL GERAL): "
                "Resumo Executivo, Resumo de Utilização Web, Top Usuários (permitidos/bloqueados), "
                "Segurança Ampliada, Categorias de Sites, Top Sites por Navegação, "
                "SD-WAN e Consumo de Banda.",
                body,
            )
        )
        return flow

    def _antenna_with_mensal(
        self,
        *,
        markers: list,
        lead: list,
        mensal: MensalGeralReport,
        styles,
        body,
        anchor_prefix: str,
    ) -> list:
        """Header (+ intro regional) + cards KPI juntos; gráficos do resumo em bloco à parte."""
        charts_on = self.settings.pdf_mensal_charts
        chart_scope = self._current_chart_scope or None
        exec_block = build_resumo_executivo_flowables(
            mensal,
            width=self.width,
            styles=styles,
            anchor_prefix=anchor_prefix,
            charts_enabled=charts_on,
            chart_scope=chart_scope,
        )
        exec_markers, cards_part, charts_part = self._split_resumo_cards_and_charts(exec_block)

        flow: list = list(markers) + list(exec_markers)
        # Intro regional + metadados do dispositivo ficam juntos (sem página órfã).
        # Cards KPI vêm em seguida (bloco menor) para não estourar o KeepTogether.
        if lead:
            flow.append(KeepTogether(lead))
        if cards_part:
            flow.append(KeepTogether(cards_part))
        if charts_part:
            flow.append(KeepTogether(charts_part))

        flow.extend(
            self._mensal_sections(
                mensal,
                styles,
                body,
                anchor_prefix=anchor_prefix,
                skip_resumo=True,
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
        skip_resumo: bool = False,
    ) -> list:
        flow: list = []
        charts_on = self.settings.pdf_mensal_charts
        chart_scope = self._current_chart_scope or None
        if not skip_resumo:
            exec_block = build_resumo_executivo_flowables(
                mensal,
                width=self.width,
                styles=styles,
                anchor_prefix=anchor_prefix,
                charts_enabled=charts_on,
                chart_scope=chart_scope,
            )
            if exec_block:
                flow.extend(self._pack_section(exec_block))

        # Referência FAZ (inventário) fica fora do PDF do cliente final.

        flow.extend([
            Spacer(1, _SECTION_GAP),
            Paragraph("Análise da Unidade — Navegação, Segurança e Banda", styles["Heading2"]),
            Paragraph(
                f"Dispositivo <b>{mensal.device_name}</b>. "
                "Cada bloco traz gráfico (padrão) e tabela (valores exatos) para facilitar "
                "acompanhamento e decisão operacional.",
                body,
            ),
        ])
        # Rankings: gráfico + tabela. Segurança (bloqueio/risco/phishing) só no painel dedicado.
        sections = [
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
                    show_chart=True,
                    chart_min_items=3,
                    include_table=True,
                ),
            ),
            ("categorias-sites", None),
            ("seguranca", None),
            (
                "web-apps",
                self._ranked_section(
                    mensal.top_web_apps,
                    styles,
                    "Principais Aplicativos Web por Largura de Banda",
                    "Sessões / Banda",
                    f"{anchor_prefix}web-apps",
                    label_header="Aplicação",
                    category_col=True,
                    pct_col=True,
                    show_chart=True,
                    chart_min_items=3,
                    prefer_donut=True,
                    include_table=True,
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
                    show_chart=True,
                    chart_min_items=3,
                    max_chart_items=10,
                    include_table=True,
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
                    show_chart=True,
                    chart_min_items=3,
                    max_chart_items=10,
                    include_table=True,
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
                    show_chart=True,
                    chart_min_items=3,
                    max_chart_items=10,
                    include_table=True,
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
                    show_chart=True,
                    chart_min_items=3,
                    max_chart_items=10,
                    include_table=True,
                ),
            ),
            ("pol-detalhes", self._policy_details_section(mensal, styles, anchor_prefix)),
        ]
        for key, block in sections:
            if key == "categorias-sites":
                flow.extend(self._categories_and_sites_sections(mensal, styles, anchor_prefix))
            elif key == "seguranca":
                sec = build_seguranca_flowables(
                    mensal,
                    width=self.width,
                    styles=styles,
                    anchor_prefix=anchor_prefix,
                    charts_enabled=charts_on,
                    chart_scope=chart_scope,
                )
                if sec:
                    flow.extend(self._pack_section(sec))
            elif key == "sdwan":
                flow.extend(self._sdwan_full_section(mensal, styles, anchor_prefix))
            elif block:
                flow.extend(self._pack_section(block))
        return flow

    def _summary_section(
        self, mensal: MensalGeralReport, styles, anchor_prefix: str
    ) -> list:
        s = mensal.summary
        availability = mensal.macros.get("SD-WAN Device Availability Percentage", "—")
        cards = kpi_cards_table(
            [
                ("Permitidas", s.allowed_requests or "—"),
                ("Bloqueadas", s.blocked_requests or "—"),
                ("Usuários", str(s.users or mensal.macros.get("Web Usage User Count", "—"))),
                ("Categorias", str(s.categories or mensal.macros.get("Web Usage Category Count", "—"))),
                ("Aplicações", str(s.applications or mensal.macros.get("Web Usage Application Count", "—"))),
                (
                    "Sites maliciosos",
                    str(s.malicious_sites or mensal.macros.get("web Usage Total Malicious Websites Count", "—")),
                ),
                ("Disponibilidade", availability or "—"),
                ("Banda SD-WAN", mensal.macros.get("SD-WAN Total Bandwidth", "—")),
            ],
            self.width,
            cols=4,
        )
        flow: list = [
            *section_anchor(f"{anchor_prefix}resumo"),
            Spacer(1, _SECTION_GAP),
            Paragraph("RESUMO DE UTILIZAÇÃO WEB", styles["Heading2"]),
        ]
        if cards:
            flow.append(Spacer(1, 0.08 * cm))
            flow.append(cards)

        a_num = parse_numeric_value(s.allowed_requests or "")
        b_num = parse_numeric_value(s.blocked_requests or "")
        self._append_chart(
            flow,
            allowed_blocked_donut(a_num, b_num),
            max_height=DONUT_MAX_HEIGHT,
            cache_key=f"summary-donut:{mensal.device_name}",
        )
        avail = parse_availability_percent(availability if availability != "—" else None)
        if avail is not None:
            self._append_chart(
                flow,
                create_gauge(avail, title="Disponibilidade SD-WAN"),
                max_height=GAUGE_MAX_HEIGHT,
                cache_key=f"summary-gauge:{mensal.device_name}:{avail}",
            )
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
                append_chart_with_gap(
                    flow, png, max_width=16 * cm, max_height=TIMELINE_MAX_HEIGHT
                )
        except Exception:
            pass
        return flow

    def _append_chart(
        self,
        flow: list,
        fig,
        *,
        max_height: float = BAR_MAX_HEIGHT,
        cache_key: str | None = None,
        gap_before: float | None = None,
        gap_after: float | None = None,
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
            append_chart_with_gap(
                flow,
                png,
                max_width=16 * cm,
                max_height=max_height,
                gap_before=gap_before if gap_before is not None else CHART_GAP,
                gap_after=gap_after if gap_after is not None else CHART_GAP,
            )
        except Exception:
            pass

    def _categories_and_sites_sections(
        self, mensal: MensalGeralReport, styles, anchor_prefix: str
    ) -> list:
        """Categorias e sites: gráfico + tabela (categoria/tempo ficam legíveis)."""
        flow: list = []
        tight_h2 = ParagraphStyle(
            "Heading2Tight",
            parent=styles["Heading2"],
            spaceBefore=0,
            spaceAfter=2,
        )
        cat_items = filter_ranked(mensal.top_categories)
        if cat_items:
            cat_block: list = [
                *section_anchor(f"{anchor_prefix}categorias"),
                Spacer(1, _SECTION_GAP),
                Paragraph(
                    "360 Security — Principais Categorias de Web Visitadas",
                    styles["Heading2"],
                ),
                Paragraph(
                    "Distribuição do tráfego web por categoria — gráfico para padrão, tabela para volume/%.",
                    styles["Normal"],
                ),
            ]
            self._append_chart(
                cat_block,
                create_bar_chart(
                    cat_items,
                    title="Categorias web mais visitadas",
                    value_label="Contagem",
                    max_items=12,
                ),
                max_height=BAR_MAX_HEIGHT,
                cache_key=f"categories-bar:{anchor_prefix}",
            )
            self._append_chart(
                cat_block,
                category_pie_chart(cat_items, title="Distribuição de categorias"),
                max_height=DONUT_MAX_HEIGHT,
                cache_key=f"categories:{anchor_prefix}",
            )
            cat_block.append(
                ranked_table(
                    cat_items[:12],
                    self.width,
                    label_header="Categoria",
                    value_header="Contagem",
                    pct_col=True,
                )
            )
            flow.extend(self._pack_section(cat_block))

        site_items = filter_ranked(mensal.top_sites_by_browsing)
        if site_items:
            top_sites = site_items[:20]
            chart_sites = top_sites[:12]
            site_block: list = [
                *section_anchor(f"{anchor_prefix}top-sites"),
                Paragraph("Top 20 Sites por Tempo de Navegação", tight_h2),
                Paragraph(
                    "Sites que mais consomem tempo de navegação — use a tabela para categoria e duração exata.",
                    styles["Normal"],
                ),
            ]
            labels, _ = ranked_chart_values(chart_sites, max_items=12)
            if labels:
                self._append_chart(
                    site_block,
                    ranked_horizontal_chart(
                        chart_sites,
                        title="Top sites — tempo de navegação",
                        value_label="Minutos",
                        max_items=12,
                    ),
                    max_height=BAR_MAX_HEIGHT,
                    cache_key=f"sites-v2:{anchor_prefix}",
                )
            rows = [["#", "Site", "Categoria", "Tempo"]]
            for site in top_sites:
                rows.append([
                    str(site.rank),
                    site.label,
                    site.category or "—",
                    site.value or "—",
                ])
            site_block.append(
                data_table(
                    rows,
                    self.width,
                    min_widths=[0.8 * cm, 4.0 * cm, 3.0 * cm, 2.0 * cm],
                    font_size=7,
                    header_font_size=9,
                    nowrap_cols=frozenset({0, 3}),
                    stretch_col=1,
                    allow_split=True,
                )
            )
            flow.extend(self._pack_section(site_block))
        return flow

    def _app_visibility_section(
        self, mensal: MensalGeralReport, styles, anchor_prefix: str
    ) -> list:
        items = filter_ranked(mensal.app_visibility)
        if not items:
            return []
        flow: list = [
            *section_anchor(f"{anchor_prefix}app-vis"),
            Spacer(1, _SECTION_GAP),
            Paragraph("360° Application Visibility and Control", styles["Heading2"]),
        ]
        labels, values = pie_values_from_items(items, max_items=10)
        if labels:
            self._append_chart(
                flow,
                create_donut_chart(labels, values, title="Visibilidade de aplicações"),
                max_height=DONUT_MAX_HEIGHT,
                cache_key=f"app-vis-donut:{mensal.device_name}",
            )
        rows = [["#", "Categoria de Aplicação", "Qtd. Apps", "% do Total"]]
        for item in items:
            rows.append([
                str(item.rank),
                item.label,
                item.value or "—",
                item.percentage or "—",
            ])
        flow.append(
            data_table(
                rows,
                self.width,
                min_widths=[0.7 * cm, 5.5 * cm, 2.0 * cm, 2.0 * cm],
                font_size=7,
                header_font_size=9,
                nowrap_cols=frozenset({0, 2, 3}),
                stretch_col=1,
            )
        )
        return flow

    def _users_section(
        self, items: list[RankedItem], styles, label: str, anchor_prefix: str
    ) -> list:
        items = filter_ranked(items)
        if not items:
            return []
        slug = "permitidas" if "Permit" in label else "bloqueadas"
        color = None if "Permit" in label else _BLOCKED_COLOR
        flow: list = [
            *section_anchor(f"{anchor_prefix}usuarios-{slug}"),
            Spacer(1, _SECTION_GAP),
            Paragraph(f"Top 10 Usuários por Requisições {label}", styles["Heading2"]),
        ]
        labels, _ = ranked_chart_values(items, max_items=10)
        if labels:
            self._append_chart(
                flow,
                top_users_bar_chart(
                    items,
                    title=f"Top usuários — {label}",
                    color=color,
                ),
                max_height=BAR_MAX_HEIGHT,
                cache_key=f"users-{slug}:{anchor_prefix}",
            )
        flow.append(
            ranked_table(
                items[:10],
                self.width,
                label_header="Usuário",
                value_header="Requisições",
                pct_col=True,
            )
        )
        return flow

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
        chart_color: str | None = None,
        prefer_donut: bool = False,
        max_chart_items: int = 12,
        include_table: bool = True,
    ) -> list:
        """Ranking: gráfico para leitura rápida + tabela com valores exatos."""
        items = filter_ranked(items)
        if not items:
            return []
        flow: list = [
            *section_anchor(anchor),
            Spacer(1, _SECTION_GAP),
            Paragraph(title, styles["Heading2"]),
        ]
        if show_chart:
            labels, _values = ranked_chart_values(items, max_items=max_chart_items)
            if len(labels) >= chart_min_items:
                if prefer_donut:
                    pie_labels, pie_values = pie_values_from_items(items, max_items=8)
                    self._append_chart(
                        flow,
                        create_donut_chart(pie_labels, pie_values, title=title),
                        max_height=DONUT_MAX_HEIGHT,
                        cache_key=f"donut:{anchor}",
                    )
                else:
                    self._append_chart(
                        flow,
                        create_bar_chart(
                            items,
                            title=title,
                            value_label=value_header,
                            max_items=max_chart_items,
                            color=chart_color,
                        ),
                        max_height=BAR_MAX_HEIGHT,
                        cache_key=f"ranked:{anchor}",
                    )
        if include_table:
            flow.append(
                ranked_table(
                    items[:max_chart_items],
                    self.width,
                    label_header=label_header,
                    value_header=value_header,
                    pct_col=pct_col,
                    category_col=category_col,
                )
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
        avail = parse_availability_percent(
            mensal.macros.get("SD-WAN Device Availability Percentage")
        )
        if avail is not None:
            self._append_chart(
                header_block,
                create_gauge(avail, title="Disponibilidade SD-WAN"),
                max_height=GAUGE_MAX_HEIGHT,
                cache_key=f"sdwan-gauge:{mensal.device_name}:{avail}",
            )
        if apps:
            header_block.append(
                Paragraph("<b>Distribuição de Tráfego por Aplicação</b>", styles["Normal"])
            )
            pie_labels, pie_values = pie_values_from_items(apps, max_items=8)
            self._append_chart(
                header_block,
                create_donut_chart(pie_labels, pie_values, title="Aplicações SD-WAN"),
                max_height=DONUT_MAX_HEIGHT,
                cache_key=f"sdwan-apps:{mensal.device_name}",
            )
            header_block.append(
                ranked_table(
                    apps[:10],
                    self.width,
                    label_header="Aplicação",
                    value_header="Tráfego",
                )
            )
        flow.extend(self._pack_section(header_block))

        if dest:
            dest_block: list = [
                Spacer(1, 0.08 * cm),
                Paragraph(
                    "<b>Principais fontes/destinos consumidores de banda</b>",
                    styles["Normal"],
                ),
            ]
            self._append_chart(
                dest_block,
                create_bar_chart(
                    dest,
                    title="Fontes/destinos SD-WAN",
                    value_label="Banda",
                    max_items=10,
                ),
                max_height=BAR_MAX_HEIGHT,
                cache_key=f"sdwan-dest:{mensal.device_name}",
            )
            dest_block.append(
                ranked_table(
                    dest[:10],
                    self.width,
                    label_header="Origem / Destino",
                    value_header="Banda",
                )
            )
            flow.extend(self._pack_section(dest_block))

        if users:
            users_block: list = [
                Spacer(1, 0.08 * cm),
                Paragraph(
                    "<b>Top Usuários SD-WAN por Consumo de Banda</b>",
                    styles["Normal"],
                ),
            ]
            self._append_chart(
                users_block,
                create_bar_chart(
                    users,
                    title="Usuários SD-WAN",
                    value_label="Banda",
                    max_items=10,
                ),
                max_height=BAR_MAX_HEIGHT,
                cache_key=f"sdwan-users:{mensal.device_name}",
            )
            users_block.append(
                ranked_table(
                    users[:10],
                    self.width,
                    label_header="Usuário",
                    value_header="Banda",
                )
            )
            flow.extend(self._pack_section(users_block))

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
        has_type = any((p.policy_type or "").strip() for p in mensal.policy_details)
        if has_type:
            rows = [["#", "Política", "Tipo", "Bytes", "Sessões", "Origem", "Destino", "Último uso"]]
            for idx, p in enumerate(mensal.policy_details, start=1):
                rows.append([
                    str(idx),
                    p.policy_name[:36],
                    (p.policy_type or "—")[:12],
                    format_bandwidth(p.bytes_val) if p.bytes_val else "—",
                    p.sessions or "—",
                    (p.source_interface or "—")[:22],
                    (p.destination_interface or "—")[:22],
                    (p.last_used or "—")[:16],
                ])
            min_w = [0.6 * cm, 2.6 * cm, 1.2 * cm, 1.4 * cm, 1.2 * cm, 2.0 * cm, 2.0 * cm, 1.8 * cm]
            nowrap = frozenset({0, 2, 3, 4, 7})
            stretch = 1
        else:
            rows = [["#", "Política", "Bytes", "Sessões", "Origem", "Destino", "Último uso"]]
            for idx, p in enumerate(mensal.policy_details, start=1):
                rows.append([
                    str(idx),
                    p.policy_name[:40],
                    format_bandwidth(p.bytes_val) if p.bytes_val else "—",
                    p.sessions or "—",
                    p.source_interface or "—",
                    p.destination_interface or "—",
                    (p.last_used or "—")[:16],
                ])
            min_w = [0.6 * cm, 3.2 * cm, 1.5 * cm, 1.2 * cm, 2.0 * cm, 2.0 * cm, 1.8 * cm]
            nowrap = frozenset({0, 2, 3, 6})
            stretch = 1
        return [
            *section_anchor(f"{anchor_prefix}pol-detalhes"),
            Spacer(1, _SECTION_GAP),
            Paragraph("Principais Políticas com Detalhes por Consumo de Banda", styles["Heading2"]),
            Paragraph(
                "Regras com maior impacto em banda/sessão — base para ajuste de política e priorização.",
                styles["Normal"],
            ),
            data_table(
                rows,
                self.width,
                min_widths=min_w,
                font_size=6,
                header_font_size=8,
                nowrap_cols=nowrap,
                stretch_col=stretch,
                allow_split=True,
            ),
        ]


def _regional_anchor(ru: RegionalUnit) -> str:
    return f"unidade-{ru.code}"


def _antenna_anchor(ru: RegionalUnit, antenna: AntennaInfo) -> str:
    return f"{ru.code}-{_slug(antenna.site_slug)}"


def _slug(value: str) -> str:
    return value.replace("-", "_")
