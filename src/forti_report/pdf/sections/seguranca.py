"""Seção Segurança Ampliada — indicadores e rankings de segurança."""

from __future__ import annotations

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer

from forti_report.data.mensal_models import MensalGeralReport
from forti_report.data.parsers.mensal_utils import block_rate_percent, filter_ranked
from forti_report.pdf.mensal_toc import section_anchor
from forti_report.pdf.table_utils import data_table, ranked_table

_SECTION_GAP = 0.12 * cm
_TOP_N = 5


def build_seguranca_flowables(
    mensal: MensalGeralReport,
    *,
    width: float,
    styles,
    anchor_prefix: str = "",
) -> list:
    """Painel consolidado de segurança: bloqueios, risco, phishing e categorias bloqueadas."""
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

    kpi_rows = [
        ["Indicador de segurança", "Valor"],
        ["Requisições bloqueadas", blocked or "—"],
        ["Taxa de bloqueio", block_pct or "—"],
        [
            "Sites maliciosos",
            str(s.malicious_sites or mensal.macros.get("web Usage Total Malicious Websites Count", "—")),
        ],
        ["Usuários no ranking de bloqueio", str(len(blocked_users)) if blocked_users else "—"],
        ["Usuários de risco identificados", str(len(risk_users)) if risk_users else "—"],
        ["Registros de phishing (ranking)", str(len(phishing)) if phishing else "—"],
    ]

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
            "Consolidação de bloqueios, sites maliciosos, usuários de risco e tentativas de phishing "
            "detectados pelo FortiGate no período.",
            body,
        ),
        data_table(
            kpi_rows,
            width,
            min_widths=[6.5 * cm, 4.0 * cm],
            font_size=8,
            header_font_size=9,
            nowrap_cols=frozenset({1}),
            stretch_col=0,
        ),
    ]

    if blocked_users:
        flow.append(Spacer(1, 0.2 * cm))
        flow.append(Paragraph("Top usuários bloqueados", styles["Heading3"]))
        flow.append(
            ranked_table(
                blocked_users[:_TOP_N],
                width,
                label_header="Usuário",
                value_header="Requisições",
                pct_col=True,
            )
        )

    if risk_users:
        flow.append(Spacer(1, 0.15 * cm))
        flow.append(Paragraph("Top usuários de risco", styles["Heading3"]))
        flow.append(
            ranked_table(
                risk_users[:_TOP_N],
                width,
                label_header="Usuário",
                value_header="Requisições",
                pct_col=True,
            )
        )

    if phishing:
        flow.append(Spacer(1, 0.15 * cm))
        flow.append(Paragraph("Principais vítimas de phishing", styles["Heading3"]))
        flow.append(
            ranked_table(
                phishing[:_TOP_N],
                width,
                label_header="Usuário / Site",
                value_header="Ocorrências",
                pct_col=True,
            )
        )

    if blocked_cats:
        flow.append(Spacer(1, 0.15 * cm))
        flow.append(Paragraph("Categorias e usuários mais bloqueados", styles["Heading3"]))
        flow.append(
            ranked_table(
                blocked_cats[:_TOP_N],
                width,
                label_header="Usuário",
                value_header="Requisições",
                pct_col=True,
                category_col=True,
            )
        )

    return flow
