"""Dados do relatório MENSAL- RELATÓRIO GERAL (por dispositivo)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from forti_report.data.wan_models import RankedItem, WebUsageSummary


@dataclass
class TimelineSlice:
    """Ponto da série temporal de consumo de banda."""

    label: str
    values: dict[str, float] = field(default_factory=dict)


@dataclass
class FazChartRecord:
    """Bloco exportado pelo FAZ (chart ou macro) com prévia textual."""

    title: str
    chart_type: str = "chart"  # chart | macro
    row_count: int = 0
    mapped_field: str = ""
    rendered_in_pdf: bool = False
    preview_rows: list[list[str]] = field(default_factory=list)

    @property
    def is_mapped(self) -> bool:
        return bool(self.mapped_field and self.mapped_field != "unmapped")


@dataclass
class PolicyDetailRow:
    policy_name: str
    policy_type: str = ""
    bytes_val: str = ""
    sessions: str = ""
    source_interface: str = ""
    destination_interface: str = ""
    device_name: str = ""
    last_used: str = ""


@dataclass
class MensalGeralReport:
    """Conteúdo parseado do layout MENSAL- RELATÓRIO GERAL (layout-id 12)."""

    device_name: str = ""
    title: str = "MENSAL- RELATÓRIO GERAL"
    period_label: str = ""
    source_file: str = ""
    summary: WebUsageSummary = field(default_factory=WebUsageSummary)
    macros: dict[str, str] = field(default_factory=dict)
    top_users_allowed: list[RankedItem] = field(default_factory=list)
    top_users_blocked: list[RankedItem] = field(default_factory=list)
    top_users_requests: list[RankedItem] = field(default_factory=list)
    top_categories: list[RankedItem] = field(default_factory=list)
    top_browsing_categories: list[RankedItem] = field(default_factory=list)
    top_sites_by_browsing: list[RankedItem] = field(default_factory=list)
    top_risk_users: list[RankedItem] = field(default_factory=list)
    phishing_victims: list[RankedItem] = field(default_factory=list)
    app_visibility: list[RankedItem] = field(default_factory=list)
    blocked_usage_summary: list[RankedItem] = field(default_factory=list)
    bandwidth_timeline: list[TimelineSlice] = field(default_factory=list)
    top_web_apps: list[RankedItem] = field(default_factory=list)
    sdwan_apps: list[RankedItem] = field(default_factory=list)
    sdwan_destinations: list[RankedItem] = field(default_factory=list)
    sdwan_users: list[RankedItem] = field(default_factory=list)
    top_bandwidth_users: list[RankedItem] = field(default_factory=list)
    top_bandwidth_timeline_users: list[RankedItem] = field(default_factory=list)
    policy_by_bandwidth: list[RankedItem] = field(default_factory=list)
    policy_by_session: list[RankedItem] = field(default_factory=list)
    policy_details: list[PolicyDetailRow] = field(default_factory=list)
    faz_section_titles: list[str] = field(default_factory=list)
    faz_charts: list[FazChartRecord] = field(default_factory=list)
    content_source: str = ""  # json | pdf
    generated_at: datetime = field(default_factory=datetime.now)

    @property
    def has_content(self) -> bool:
        return bool(
            self.summary.allowed_requests
            or self.summary.blocked_requests
            or self.macros
            or self.top_sites_by_browsing
            or self.top_users_allowed
            or self.top_users_blocked
            or self.top_categories
            or self.top_risk_users
            or self.phishing_victims
            or self.sdwan_apps
            or self.bandwidth_timeline
            or self.policy_details
            or self.faz_charts
        )
