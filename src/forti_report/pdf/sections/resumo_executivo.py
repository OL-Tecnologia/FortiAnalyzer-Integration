"""Seção Resumo Executivo — KPIs em cards + destaques."""

from __future__ import annotations

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer

from forti_report.charts.plotly_charts import (
    allowed_blocked_donut,
    chart_to_png_bytes,
    create_gauge,
    parse_availability_percent,
)
from forti_report.data.mensal_models import MensalGeralReport
from forti_report.data.parsers.mensal_utils import block_rate_percent, filter_ranked, parse_numeric_value
from forti_report.pdf.chart_utils import (
    DONUT_MAX_HEIGHT,
    GAUGE_MAX_HEIGHT,
    append_chart_with_gap,
)
from forti_report.pdf.kpi_cards import kpi_cards_table
from forti_report.pdf.mensal_toc import section_anchor

_SECTION_GAP = 0.12 * cm


def build_resumo_executivo_flowables(
    mensal: MensalGeralReport,
    *,
    width: float,
    styles,
    anchor_prefix: str = "",
    charts_enabled: bool = True,
    chart_scope: str | None = None,
) -> list:
    """KPIs e destaques operacionais no início de cada dispositivo."""
    if not mensal.has_content:
        return []

    s = mensal.summary
    allowed = s.allowed_requests or mensal.macros.get("Web Usage Request Count", "")
    blocked = s.blocked_requests or ""
    block_pct = block_rate_percent(allowed, blocked)
    availability = mensal.macros.get("SD-WAN Device Availability Percentage", "—")

    cards = kpi_cards_table(
        [
            ("Permitidas", allowed or "—"),
            ("Bloqueadas", blocked or "—"),
            ("Taxa bloqueio", block_pct or "—"),
            ("Usuários", str(s.users or mensal.macros.get("Web Usage User Count", "—"))),
            ("Categorias", str(s.categories or mensal.macros.get("Web Usage Category Count", "—"))),
            ("Aplicações", str(s.applications or mensal.macros.get("Web Usage Application Count", "—"))),
            (
                "Sites maliciosos",
                str(s.malicious_sites or mensal.macros.get("web Usage Total Malicious Websites Count", "—")),
            ),
            ("Disponibilidade SD-WAN", availability or "—"),
            ("Banda SD-WAN", mensal.macros.get("SD-WAN Total Bandwidth", "—")),
        ],
        width,
        cols=3,
    )

    highlights = _build_highlights(mensal)
    body = ParagraphStyle(
        "ExecBody",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        spaceAfter=4,
    )

    flow: list = [
        *section_anchor(f"{anchor_prefix}resumo-executivo"),
        Spacer(1, _SECTION_GAP),
        Paragraph("Resumo Executivo", styles["Heading2"]),
        Paragraph(
            "Indicadores do período em um só olhar. Os destaques abaixo apontam onde investigar primeiro.",
            body,
        ),
    ]
    if cards:
        flow.append(Spacer(1, 0.1 * cm))
        flow.append(cards)

    if charts_enabled:
        a_num = parse_numeric_value(allowed or "")
        b_num = parse_numeric_value(blocked or "")
        fig = allowed_blocked_donut(a_num, b_num)
        if fig:
            try:
                png = chart_to_png_bytes(
                    fig,
                    cache_key=f"kpi-donut:{mensal.device_name}",
                    cache_scope=chart_scope,
                )
                append_chart_with_gap(flow, png, max_width=width, max_height=DONUT_MAX_HEIGHT)
            except Exception:
                pass

        avail = parse_availability_percent(availability if availability != "—" else None)
        if avail is not None:
            gauge = create_gauge(avail, title="Disponibilidade SD-WAN")
            if gauge:
                try:
                    png = chart_to_png_bytes(
                        gauge,
                        cache_key=f"kpi-gauge:{mensal.device_name}:{avail}",
                        cache_scope=chart_scope,
                    )
                    append_chart_with_gap(
                        flow, png, max_width=width * 0.75, max_height=GAUGE_MAX_HEIGHT
                    )
                except Exception:
                    pass

    if highlights:
        flow.append(Spacer(1, 0.15 * cm))
        flow.append(Paragraph("<b>Destaques:</b>", body))
        for line in highlights:
            flow.append(Paragraph(f"• {line}", body))
    return flow


def build_global_resumo_executivo_flowables(
    regional_units,
    *,
    width: float,
    styles,
    charts_enabled: bool = True,
) -> list:
    """Resumo executivo agregado de todos os dispositivos Cruz Azul."""
    total = 0
    online = 0
    with_report = 0
    with_data = 0
    allowed_sum = 0.0
    blocked_sum = 0.0
    malicious_sum = 0
    has_metrics = False

    for ru in regional_units:
        for ant in ru.antennas:
            total += 1
            if ant.online:
                online += 1
            rep = ant.report
            if rep and rep.faz_tid:
                with_report += 1
            mensal = rep.mensal if rep else None
            if mensal and mensal.has_content:
                with_data += 1
                s = mensal.summary
                a = parse_numeric_value(s.allowed_requests or "")
                b = parse_numeric_value(s.blocked_requests or "")
                if a is not None:
                    allowed_sum += a
                    has_metrics = True
                if b is not None:
                    blocked_sum += b
                    has_metrics = True
                m = s.malicious_sites or mensal.macros.get("web Usage Total Malicious Websites Count", "")
                mn = parse_numeric_value(str(m))
                if mn is not None:
                    malicious_sum += int(mn)

    block_pct = block_rate_percent(str(int(allowed_sum)), str(int(blocked_sum))) if has_metrics else "—"
    offline = max(total - online, 0)

    card_items = [
        ("Dispositivos", str(total)),
        ("Online", str(online)),
        ("Offline", str(offline)),
        ("Com relatório", str(with_report)),
        ("Com dados", str(with_data)),
    ]
    if has_metrics:
        card_items.extend(
            [
                ("Permitidas (soma)", f"{int(allowed_sum):,}".replace(",", ".")),
                ("Bloqueadas (soma)", f"{int(blocked_sum):,}".replace(",", ".")),
                ("Taxa bloqueio", block_pct),
                ("Sites maliciosos", str(malicious_sum)),
            ]
        )

    # Abertura global: só cards/tabela — sem donuts (espaço e leitura).
    _ = charts_enabled
    cards = kpi_cards_table(card_items, width, cols=3)
    body = ParagraphStyle(
        "GlobalExecBody",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
    )
    flow: list = [
        Spacer(1, _SECTION_GAP),
        Paragraph("Resumo Executivo — Visão Geral", styles["Heading2"]),
        Paragraph(
            "Consolidado de todas as unidades regionais e dispositivos incluídos neste relatório.",
            body,
        ),
    ]
    if cards:
        flow.append(Spacer(1, 0.1 * cm))
        flow.append(cards)

    flow.append(Spacer(1, _SECTION_GAP))
    return flow


def _build_highlights(mensal: MensalGeralReport) -> list[str]:
    lines: list[str] = []

    blocked_users = filter_ranked(mensal.top_users_blocked)
    if blocked_users:
        top = blocked_users[0]
        lines.append(
            f"Maior volume bloqueado: <b>{top.label}</b> ({top.value or '—'} requisições)"
        )

    risk_users = filter_ranked(mensal.top_risk_users)
    if risk_users:
        top = risk_users[0]
        lines.append(f"Principal usuário de risco: <b>{top.label}</b> ({top.value or '—'})")

    bandwidth = filter_ranked(mensal.top_bandwidth_users)
    if bandwidth:
        top = bandwidth[0]
        lines.append(f"Maior consumo de banda: <b>{top.label}</b> ({top.value or '—'})")

    phishing = filter_ranked(mensal.phishing_victims)
    if phishing:
        lines.append(f"Registros de phishing: <b>{len(phishing)}</b> usuário(s)/site(s) no top ranking")

    malicious = mensal.summary.malicious_sites or mensal.macros.get(
        "web Usage Total Malicious Websites Count", ""
    )
    if malicious and str(malicious) not in {"0", "—", ""}:
        lines.append(f"Sites maliciosos no período: <b>{malicious}</b>")

    return lines[:5]
