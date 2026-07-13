"""Seção Resumo Executivo — KPIs consolidados por dispositivo."""

from __future__ import annotations

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer

from forti_report.data.mensal_models import MensalGeralReport
from forti_report.data.parsers.mensal_utils import block_rate_percent, filter_ranked, parse_numeric_value
from forti_report.pdf.mensal_toc import section_anchor
from forti_report.pdf.table_utils import data_table

_SECTION_GAP = 0.12 * cm


def build_resumo_executivo_flowables(
    mensal: MensalGeralReport,
    *,
    width: float,
    styles,
    anchor_prefix: str = "",
) -> list:
    """KPIs e destaques operacionais no início de cada dispositivo."""
    if not mensal.has_content:
        return []

    s = mensal.summary
    allowed = s.allowed_requests or mensal.macros.get("Web Usage Request Count", "")
    blocked = s.blocked_requests or ""
    block_pct = block_rate_percent(allowed, blocked)

    rows = [
        ["Indicador", "Valor"],
        ["Requisições permitidas", allowed or "—"],
        ["Requisições bloqueadas", blocked or "—"],
        ["Taxa de bloqueio", block_pct or "—"],
        ["Usuários ativos", str(s.users or mensal.macros.get("Web Usage User Count", "—"))],
        ["Categorias monitoradas", str(s.categories or mensal.macros.get("Web Usage Category Count", "—"))],
        ["Aplicações identificadas", str(s.applications or mensal.macros.get("Web Usage Application Count", "—"))],
        [
            "Sites maliciosos detectados",
            str(s.malicious_sites or mensal.macros.get("web Usage Total Malicious Websites Count", "—")),
        ],
        ["Disponibilidade SD-WAN", mensal.macros.get("SD-WAN Device Availability Percentage", "—")],
        ["Consumo SD-WAN (total)", mensal.macros.get("SD-WAN Total Bandwidth", "—")],
    ]

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
            "Visão sintética dos indicadores do período para apoio à gestão e tomada de decisão.",
            body,
        ),
        data_table(
            rows,
            width,
            min_widths=[6.0 * cm, 4.5 * cm],
            font_size=8,
            header_font_size=9,
            nowrap_cols=frozenset({1}),
            stretch_col=0,
        ),
    ]
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

    rows = [
        ["Indicador", "Valor"],
        ["Dispositivos no escopo", str(total)],
        ["Dispositivos online", str(online)],
        ["Com relatório MENSAL vinculado", str(with_report)],
        ["Com dados parseados", str(with_data)],
    ]
    if has_metrics:
        rows.extend([
            ["Requisições permitidas (soma)", f"{int(allowed_sum):,}".replace(",", ".")],
            ["Requisições bloqueadas (soma)", f"{int(blocked_sum):,}".replace(",", ".")],
            ["Taxa de bloqueio (agregada)", block_pct],
            ["Sites maliciosos (soma)", str(malicious_sum)],
        ])

    body = ParagraphStyle(
        "GlobalExecBody",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
    )
    return [
        Spacer(1, _SECTION_GAP),
        Paragraph("Resumo Executivo — Visão Geral", styles["Heading2"]),
        Paragraph(
            "Consolidado de todas as unidades regionais e dispositivos incluídos neste relatório.",
            body,
        ),
        data_table(
            rows,
            width,
            min_widths=[6.5 * cm, 4.0 * cm],
            font_size=8,
            header_font_size=9,
            nowrap_cols=frozenset({1}),
            stretch_col=0,
        ),
        Spacer(1, _SECTION_GAP),
    ]


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
