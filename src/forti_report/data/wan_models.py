"""Dados do relatório SEMANAL Tráfego WAN."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class WebUsageSummary:
    total_requests: str = ""
    allowed_requests: str = ""
    blocked_requests: str = ""
    applications: int = 0
    categories: int = 0
    users: int = 0
    sites: int = 0
    malicious_sites: int = 0


@dataclass
class RankedItem:
    rank: int
    label: str
    value: str
    percentage: str = ""
    category: str = ""


@dataclass
class WanTrafficReport:
    """Relatório WAN parseado (consolidado ou filtrado por antena/unidade)."""

    title: str = "Relatório Semanal Tráfego WAN"
    subtitle: str = ""
    period_label: str = ""
    source_file: str = ""
    scope_label: str = "Todos os dispositivos"
    device_names: list[str] = field(default_factory=list)
    summary: WebUsageSummary = field(default_factory=WebUsageSummary)
    top_users_allowed: list[RankedItem] = field(default_factory=list)
    top_users_blocked: list[RankedItem] = field(default_factory=list)
    top_categories: list[RankedItem] = field(default_factory=list)
    top_browsing_categories: list[RankedItem] = field(default_factory=list)
    top_sites_by_browsing: list[RankedItem] = field(default_factory=list)
    top_apps_bandwidth: list[RankedItem] = field(default_factory=list)
    top_risk_users: list[RankedItem] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)

    @property
    def has_traffic_data(self) -> bool:
        return bool(self.top_sites_by_browsing or self.summary.total_requests)
