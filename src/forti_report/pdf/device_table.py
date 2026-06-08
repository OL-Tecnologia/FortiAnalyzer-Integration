"""Tabelas de dispositivos nos PDFs (colunas padronizadas)."""

from __future__ import annotations

from forti_report.data.hierarchy import AntennaInfo, platform_model
from forti_report.data.models import UnitReport

DEVICE_TABLE_HEADER = [
    "Unidade",
    "Dispositivo",
    "IP",
    "Modelo",
    "Status",
    "Relatório",
    "FAZ",
]


def report_faz_cells(report: UnitReport | None) -> tuple[str, str]:
    if not report:
        return "Não", "Não"
    faz = "Sim" if report.faz_tid else "Não"
    if report.mensal and report.mensal.has_content:
        rel = "Sim"
    elif report.import_note and "Access denied" in report.import_note:
        rel = "Negado"
    elif report.faz_tid:
        rel = "Sim"
    else:
        rel = "Não"
    return rel, faz


def device_table_row(antenna: AntennaInfo) -> list[str]:
    rel, faz = report_faz_cells(antenna.report)
    return [
        antenna.display_name,
        antenna.device_name,
        antenna.ip or "—",
        platform_model(antenna.platform),
        "Online" if antenna.online else "Offline" if antenna.online is False else "—",
        rel,
        faz,
    ]


def device_table_min_widths() -> list:
    from reportlab.lib.units import cm

    return [2.0 * cm, 3.2 * cm, 1.7 * cm, 1.0 * cm, 1.1 * cm, 1.2 * cm, 0.9 * cm]
