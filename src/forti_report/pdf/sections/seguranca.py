"""Seção Segurança Ampliada — cards KPI + gráficos + tabelas com valores exatos."""

from __future__ import annotations

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer

from forti_report.charts.plotly_charts import chart_to_png_bytes, create_bar_chart, top_users_bar_chart
from forti_report.data.mensal_models import MensalGeralReport
from forti_report.data.parsers.mensal_utils import (
    block_rate_percent,
    filter_ranked,
    ranked_chart_values,
    split_phishing_item,
)
from forti_report.pdf.chart_utils import BAR_MAX_HEIGHT, append_chart_with_gap
from forti_report.pdf.kpi_cards import kpi_cards_table
from forti_report.pdf.mensal_toc import section_anchor
from forti_report.pdf.table_utils import data_table, ranked_table

_SECTION_GAP = 0.12 * cm
_TOP_N = 10
_BLOCKED_COLOR = "#E63946"


def build_seguranca_flowables(
    mensal: MensalGeralReport,
    *,
    width: float,
    styles,
    anchor_prefix: str = "",
    charts_enabled: bool = True,
    chart_scope: str | None = None,
) -> list:
    """Painel consolidado: visão rápida (gráfico) + detalhe operacional (tabela)."""
    s = mensal.summary
    blocked_users = filter_ranked(mensal.top_users_blocked)
    risk_users = filter_ranked(mensal.top_risk_users)
    phishing = filter_ranked(mensal.phishing_victims)
    blocked_cats = filter_ranked(mensal.blocked_usage_summary)

    has_data = bool(
        s.blocked_requests
        or s.malicious_sites
        or blocked_users
        or risk_users
        or phishing
        or blocked_cats
    )
    if not has_data:
        return []

    allowed = s.allowed_requests or ""
    blocked = s.blocked_requests or ""
    block_pct = block_rate_percent(allowed, blocked)

    cards = kpi_cards_table(
        [
            ("Bloqueadas", blocked or "—"),
            ("Taxa bloqueio", block_pct or "—"),
            (
                "Sites maliciosos",
                str(s.malicious_sites or mensal.macros.get("web Usage Total Malicious Websites Count", "—")),
            ),
            ("Usuários bloqueados", str(len(blocked_users)) if blocked_users else "—"),
            ("Usuários de risco", str(len(risk_users)) if risk_users else "—"),
            ("Phishing", str(len(phishing)) if phishing else "—"),
        ],
        width,
        cols=3,
    )

    body = ParagraphStyle(
        "SecBody",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        spaceAfter=4,
    )

    flow: list = [
        *section_anchor(f"{anchor_prefix}seguranca"),
        Spacer(1, _SECTION_GAP),
        Paragraph("Segurança Ampliada", styles["Heading2"]),
        Paragraph(
            "Onde agir primeiro: bloqueios, risco e phishing do período. "
            "Gráfico mostra o padrão; tabela traz usuário, volume e percentual.",
            body,
        ),
    ]
    if cards:
        flow.append(Spacer(1, 0.1 * cm))
        flow.append(cards)

    def _add_ranked(
        title: str,
        items: list,
        *,
        cache_key: str,
        label_header: str = "Usuário",
        value_header: str = "Requisições",
        pct_col: bool = True,
        category_col: bool = False,
        use_user_bar: bool = True,
    ) -> None:
        nonlocal flow
        if not items:
            return
        top = items[:_TOP_N]
        flow.append(Spacer(1, 0.15 * cm))
        flow.append(Paragraph(title, styles["Heading3"]))
        if charts_enabled and ranked_chart_values(top, max_items=_TOP_N)[0]:
            fig = (
                top_users_bar_chart(top, title=title, color=_BLOCKED_COLOR)
                if use_user_bar
                else create_bar_chart(
                    top,
                    title=title,
                    value_label=value_header,
                    max_items=_TOP_N,
                    color=_BLOCKED_COLOR,
                )
            )
            if fig:
                try:
                    png = chart_to_png_bytes(
                        fig,
                        cache_key=cache_key,
                        cache_scope=chart_scope,
                    )
                    append_chart_with_gap(
                        flow, png, max_width=width, max_height=BAR_MAX_HEIGHT
                    )
                except Exception:
                    pass
        flow.append(
            ranked_table(
                top,
                width,
                label_header=label_header,
                value_header=value_header,
                pct_col=pct_col,
                category_col=category_col,
            )
        )

    _add_ranked(
        "Top usuários bloqueados",
        blocked_users,
        cache_key=f"sec-blocked:{anchor_prefix}",
    )
    _add_ranked(
        "Top usuários de risco",
        risk_users,
        cache_key=f"sec-risk:{anchor_prefix}",
    )

    if phishing:
        top_phish = phishing[:_TOP_N]
        flow.append(Spacer(1, 0.15 * cm))
        flow.append(Paragraph("Principais vítimas de phishing", styles["Heading3"]))
        if charts_enabled and ranked_chart_values(top_phish, max_items=_TOP_N)[0]:
            fig = create_bar_chart(
                top_phish,
                title="Vítimas de phishing",
                value_label="Ocorrências",
                max_items=_TOP_N,
                color=_BLOCKED_COLOR,
            )
            if fig:
                try:
                    png = chart_to_png_bytes(
                        fig,
                        cache_key=f"sec-phish:{anchor_prefix}",
                        cache_scope=chart_scope,
                    )
                    append_chart_with_gap(
                        flow, png, max_width=width, max_height=BAR_MAX_HEIGHT
                    )
                except Exception:
                    pass
        rows = [["#", "Usuário", "Site", "Ocorrências", "%"]]
        for item in top_phish:
            user, site = split_phishing_item(item)
            rows.append([
                str(item.rank),
                user,
                site,
                item.value or "—",
                item.percentage or "—",
            ])
        flow.append(
            data_table(
                rows,
                width,
                min_widths=[0.7 * cm, 2.4 * cm, 5.0 * cm, 2.0 * cm, 1.3 * cm],
                font_size=7,
                header_font_size=8,
                nowrap_cols=frozenset({0, 3, 4}),
                stretch_col=2,
            )
        )

    _add_ranked(
        "Categorias e usuários mais bloqueados",
        blocked_cats,
        cache_key=f"sec-cats:{anchor_prefix}",
        category_col=True,
        use_user_bar=False,
    )

    return flow
