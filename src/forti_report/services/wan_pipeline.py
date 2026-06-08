"""Pipeline WAN: PDF referência + hierarquia → PDFs por unidade."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from forti_report.config import Settings, get_settings
from forti_report.data.hierarchy import RegionalUnit, build_regional_hierarchy
from forti_report.data.ip_mapping import (
    build_antenna_ip_profiles,
    filter_ranked_for_antennas,
    regional_unit_profiles,
)
from forti_report.data.parsers.wan_pdf import filter_wan_report_for_unit, parse_wan_traffic_pdf
from forti_report.data.wan_models import WanTrafficReport
from forti_report.faz.client import FortiAnalyzerClient, FortiAnalyzerError
from forti_report.faz.devices import DeviceService
from forti_report.faz.reports import ReportService
from forti_report.pdf.wan_regional_builder import WanRegionalPdfBuilder
from forti_report.services.pipeline import ReportPipeline


class WanReportPipeline:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.base_pipeline = ReportPipeline(settings)

    def load_wan_report(self, pdf_path: Path | None = None) -> WanTrafficReport:
        path = pdf_path or self.settings.wan_reference_pdf
        if not path.is_file():
            raise FileNotFoundError(f"PDF WAN de referência não encontrado: {path}")
        return parse_wan_traffic_pdf(path)

    def try_load_wan_from_faz(self, *, days: int = 60) -> WanTrafficReport | None:
        """Tenta baixar o SEMANAL WAN mais recente; retorna None se access denied."""
        with FortiAnalyzerClient(self.settings) as client:
            client.login()
            svc = ReportService(client, self.settings)
            reports = svc.list_reports(days=days)
            schedule = self.settings.faz_wan_report_schedule.lower()
            matches = [
                r
                for r in reports
                if schedule in (r.get("title") or "").lower()
                or schedule in (r.get("name") or "").lower()
            ]
            if not matches:
                return None
            latest = matches[0]
            tid = latest.get("tid")
            if not tid:
                return None
            try:
                payload = svc.download_report(tid, fmt="PDF")
            except FortiAnalyzerError:
                return None
            # salvar temp e parsear quando download liberado
            tmp = self.settings.output_dir / "_wan_download.pdf"
            tmp.parent.mkdir(parents=True, exist_ok=True)
            from forti_report.data.parsers.faz_xml import decode_faz_payload

            raw = decode_faz_payload(payload.get("data", ""), data_type=payload.get("data-type"))
            tmp.write_bytes(raw)
            return parse_wan_traffic_pdf(tmp)

    def build_hierarchy_with_wan(
        self,
        wan: WanTrafficReport,
        *,
        days: int = 60,
    ) -> tuple[list[RegionalUnit], dict[str, WanTrafficReport]]:
        hierarchy_result = self.base_pipeline.fetch_hierarchy(days=days, download=False)
        self._attach_wan_report_metadata(hierarchy_result.regional_units, days=days)
        with FortiAnalyzerClient(self.settings) as client:
            client.login()
            devices = DeviceService(client, self.settings).list_devices()
        ip_profiles = build_antenna_ip_profiles(devices)

        per_unit: dict[str, WanTrafficReport] = {}
        for ru in hierarchy_result.regional_units:
            profiles = regional_unit_profiles(ru, ip_profiles)
            device_names = [a.device_name for a in ru.antennas]
            filtered = filter_wan_report_for_unit(
                wan,
                unit_display_name=ru.display_name,
                antenna_device_names=device_names,
                antenna_labels=[a.display_name for a in ru.antennas],
                filtered_users_allowed=filter_ranked_for_antennas(wan.top_users_allowed, profiles),
                filtered_users_blocked=filter_ranked_for_antennas(wan.top_users_blocked, profiles),
                filtered_sites=wan.top_sites_by_browsing,  # sites globais até split por log
                filtered_risk_users=filter_ranked_for_antennas(wan.top_risk_users, profiles),
            )
            per_unit[ru.code] = filtered
        return hierarchy_result.regional_units, per_unit

    def generate_all_wan_pdfs(
        self,
        *,
        pdf_path: Path | None = None,
        days: int = 60,
    ) -> list[Path]:
        wan = self.try_load_wan_from_faz(days=days) or self.load_wan_report(pdf_path)
        units, per_unit = self.build_hierarchy_with_wan(wan, days=days)
        builder = WanRegionalPdfBuilder(self.settings)
        out_dir = self.settings.output_dir / "wan_unidades"
        paths: list[Path] = []
        for ru in units:
            wan_unit = per_unit.get(ru.code, wan)
            path = out_dir / f"WAN_{ru.code}_{datetime.now():%Y%m%d}.pdf"
            paths.append(builder.build(ru, wan_unit, path))
        return paths

    def generate_wan_pdf_for_unit(
        self,
        unit_code: str,
        *,
        pdf_path: Path | None = None,
        days: int = 60,
    ) -> Path:
        wan = self.try_load_wan_from_faz(days=days) or self.load_wan_report(pdf_path)
        units, per_unit = self.build_hierarchy_with_wan(wan, days=days)
        ru = next((u for u in units if u.code == unit_code.lower()), None)
        if not ru:
            raise ValueError(f"Unidade '{unit_code}' não encontrada")
        path = self.settings.output_dir / "wan_unidades" / f"WAN_{ru.code}_{datetime.now():%Y%m%d}.pdf"
        return WanRegionalPdfBuilder(self.settings).build(ru, per_unit[ru.code], path)

    def _attach_wan_report_metadata(self, units: list[RegionalUnit], *, days: int) -> None:
        from forti_report.data.models import UnitReport
        from forti_report.services.pipeline import _parse_period

        with FortiAnalyzerClient(self.settings) as client:
            client.login()
            svc = ReportService(client, self.settings)
            latest = svc.find_latest_wan_report(days=days)
        if not latest:
            return
        meta = UnitReport(
            device_name="consolidado",
            display_name=latest.get("title") or "SEMANAL WAN",
            period_start=_parse_period(latest.get("period-start")),
            period_end=_parse_period(latest.get("period-end")),
            faz_tid=latest.get("tid"),
            report_name=latest.get("name"),
            report_title=latest.get("title"),
            available_formats=list(latest.get("format") or []),
            import_note="Relatório WAN consolidado (todas as antenas)",
        )
        for ru in units:
            for ant in ru.antennas:
                ant.report = meta
