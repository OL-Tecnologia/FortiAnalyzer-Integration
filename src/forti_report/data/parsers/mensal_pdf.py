"""Parser do PDF MENSAL- RELATÓRIO GERAL (FortiAnalyzer, por dispositivo)."""

from __future__ import annotations

from pathlib import Path

from forti_report.data.mensal_models import MensalGeralReport
from forti_report.data.parsers.wan_pdf import parse_wan_traffic_pdf


def parse_mensal_geral_pdf(pdf_path: Path, *, device_name: str = "") -> MensalGeralReport:
    """
    O layout MENSAL GERAL compartilha seções de navegação web com o SEMANAL WAN.
    Reutiliza o parser WAN e normaliza para o modelo mensal.
    """
    base = parse_wan_traffic_pdf(pdf_path)
    scope = device_name or base.scope_label
    return MensalGeralReport(
        device_name=scope,
        title="MENSAL- RELATÓRIO GERAL",
        period_label=base.period_label,
        source_file=str(pdf_path),
        summary=base.summary,
        top_users_allowed=base.top_users_allowed,
        top_users_blocked=base.top_users_blocked,
        top_categories=base.top_categories,
        top_browsing_categories=base.top_browsing_categories,
        top_sites_by_browsing=base.top_sites_by_browsing,
        top_risk_users=base.top_risk_users,
        sdwan_apps=base.top_apps_bandwidth,
        top_bandwidth_users=base.top_users_allowed[:10],
        generated_at=base.generated_at,
        faz_section_titles=list(base.faz_section_titles),
        faz_charts=list(base.faz_charts),
        content_source="pdf",
    )
