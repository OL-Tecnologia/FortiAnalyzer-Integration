"""Modelos internos entre importação FAZ e geração de PDF."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from forti_report.data.hierarchy import RegionalUnit
    from forti_report.data.mensal_models import MensalGeralReport


@dataclass
class SiteRankingItem:
    site: str
    hits: int | None = None
    bandwidth_mb: float | None = None
    category: str | None = None


@dataclass
class SectionData:
    """Conteúdo de uma seção do PDF (alimenta Plotly + tabelas)."""

    key: str
    title: str
    site_ranking: list[SiteRankingItem] = field(default_factory=list)
    extra: dict = field(default_factory=dict)


@dataclass
class UnitReport:
    """Relatório de um dispositivo (FortiGate / site)."""

    device_name: str
    display_name: str
    period_start: datetime | None = None
    period_end: datetime | None = None
    faz_tid: str | None = None
    report_name: str | None = None
    report_title: str | None = None
    available_formats: list[str] = field(default_factory=list)
    sections: list[SectionData] = field(default_factory=list)
    mensal: MensalGeralReport | None = None
    import_note: str | None = None


@dataclass
class ReportDocument:
    """Documento completo a ser renderizado em PDF."""

    title: str
    subtitle: str = ""
    generated_at: datetime = field(default_factory=datetime.now)
    units: list[UnitReport] = field(default_factory=list)
    regional_units: list[RegionalUnit] = field(default_factory=list)
