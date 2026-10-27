"""Orquestra: FAZ → parse → PDF."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from forti_report.config import Settings, get_settings
from forti_report.data.hierarchy import RegionalUnit, build_regional_hierarchy, parse_device_name, site_display_name
from forti_report.data.models import ReportDocument, UnitReport
from forti_report.data.parsers.faz_xml import decode_faz_payload, parse_report_xml_to_sections
from forti_report.faz.client import FortiAnalyzerClient, FortiAnalyzerError
from forti_report.faz.devices import DeviceService
from forti_report.faz.reports import ReportService
from forti_report.pdf.builder import PdfReportBuilder
from forti_report.pdf.regional_builder import RegionalPdfBuilder
from forti_report.pdf.sections.registry import build_default_registry


class HierarchyImportResult:
    def __init__(self):
        self.regional_units: list[RegionalUnit] = []
        self.import_result: ImportResult | None = None


class ImportResult:
    def __init__(self):
        self.units: list[UnitReport] = []
        self.skipped: list[dict[str, str]] = []
        self.errors: list[dict[str, str]] = []
        self.download_denied: list[dict[str, str]] = []


class ReportPipeline:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.registry = build_default_registry()

    def list_unit_names(self) -> list[str]:
        with FortiAnalyzerClient(self.settings) as client:
            client.login()
            return DeviceService(client, self.settings).list_device_names()

    def import_unit_from_faz(
        self,
        device_name: str,
        *,
        days: int = 30,
        download_format: str = "XML",
        download: bool = True,
        service: ReportService | None = None,
    ) -> UnitReport:
        if service is not None:
            return self._import_unit(
                service,
                device_name,
                days=days,
                download_format=download_format,
                download=download,
            )

        with FortiAnalyzerClient(self.settings) as client:
            client.login()
            svc = ReportService(client, self.settings)
            return self._import_unit(
                svc, device_name, days=days, download_format=download_format, download=download
            )

    def import_all_units(
        self,
        *,
        days: int = 30,
        download_format: str = "XML",
        device_filter: str | None = None,
        download: bool = True,
    ) -> ImportResult:
        result = ImportResult()
        with FortiAnalyzerClient(self.settings) as client:
            client.login()
            devices = DeviceService(client, self.settings).list_device_names()
            if device_filter:
                needle = device_filter.lower()
                devices = [d for d in devices if needle in d.lower()]

            service = ReportService(client, self.settings)
            for device_name in devices:
                try:
                    unit = self._import_unit(
                        service,
                        device_name,
                        days=days,
                        download_format=download_format,
                        download=download,
                    )
                    result.units.append(unit)
                    if unit.import_note and "Access denied" in unit.import_note:
                        result.download_denied.append(
                            {"device": device_name, "reason": unit.import_note, "tid": unit.faz_tid or ""}
                        )
                    elif (
                        not unit.sections
                        and unit.faz_tid
                        and unit.import_note
                        and "download desabilitado" not in unit.import_note.lower()
                    ):
                        result.skipped.append(
                            {
                                "device": device_name,
                                "reason": unit.import_note or "Sem seções parseadas",
                                "tid": unit.faz_tid,
                            }
                        )
                except ValueError as e:
                    result.skipped.append({"device": device_name, "reason": str(e)})
                except FortiAnalyzerError as e:
                    result.errors.append({"device": device_name, "error": str(e)})
                except Exception as e:
                    result.errors.append({"device": device_name, "error": str(e)})
        return result

    def save_import_manifest(self, result: ImportResult, path: Path | None = None) -> Path:
        out = path or (self.settings.output_dir / "units_manifest.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": datetime.now().isoformat(),
            "adom": self.settings.faz_adom,
            "units_imported": len(result.units),
            "skipped": result.skipped,
            "download_denied": result.download_denied,
            "errors": result.errors,
            "units": [_unit_to_manifest(u) for u in result.units],
        }
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return out

    def _import_unit(
        self,
        service: ReportService,
        device_name: str,
        *,
        days: int,
        download_format: str,
        download: bool,
    ) -> UnitReport:
        latest = service.find_latest_report_for_device(device_name, days=days)
        if not latest:
            raise ValueError(f"Nenhum relatório encontrado nos últimos {days} dias")

        tid = latest.get("tid")
        if not tid:
            raise ValueError("Relatório sem tid")

        unit = UnitReport(
            device_name=device_name,
            display_name=_device_display_name(latest, device_name),
            period_start=_parse_period(latest.get("period-start")),
            period_end=_parse_period(latest.get("period-end")),
            faz_tid=tid,
            report_name=latest.get("name"),
            report_title=latest.get("title"),
            available_formats=list(latest.get("format") or []),
        )

        if not download:
            unit.import_note = "Metadados apenas (download desabilitado)"
            return unit

        try:
            payload = service.download_report(tid, fmt=download_format)  # type: ignore[arg-type]
            raw = decode_faz_payload(
                payload.get("data", ""),
                data_type=payload.get("data-type"),
            )
            unit.sections = parse_report_xml_to_sections(raw)
            if not unit.sections:
                unit.import_note = "Download OK, parser XML ainda não extrai seções deste layout"
        except FortiAnalyzerError as e:
            unit.import_note = str(e)

        return unit

    def generate_pdf(self, unit: UnitReport, output_path: Path | None = None) -> Path:
        out = output_path or (
            self.settings.output_dir
            / f"{unit.device_name.replace('/', '-')}_{datetime.now():%Y%m%d}.pdf"
        )
        builder = PdfReportBuilder(self.settings, self.registry)
        return builder.build_unit_pdf(unit, out)

    def generate_all_pdfs(self, result: ImportResult) -> list[Path]:
        paths: list[Path] = []
        for unit in result.units:
            if not unit.sections:
                continue
            paths.append(self.generate_pdf(unit))
        return paths

    def pull_all_units(
        self,
        *,
        days: int = 30,
        save_manifest: bool = True,
        download: bool = True,
    ) -> ImportResult:
        result = self.import_all_units(days=days, download=download)
        if save_manifest:
            manifest = self.save_import_manifest(result)
            print(f"Manifesto salvo: {manifest}")
        return result

    def run_for_device(self, device_name: str) -> Path:
        unit = self.import_unit_from_faz(device_name)
        if not unit.sections:
            raise ValueError(
                unit.import_note or "Sem dados para PDF. Verifique permissão de download no FAZ."
            )
        return self.generate_pdf(unit)

    def run_for_all_units(self, *, days: int = 30) -> tuple[ImportResult, list[Path]]:
        result = self.import_all_units(days=days, download=True)
        self.save_import_manifest(result)
        paths = self.generate_all_pdfs(result)
        return result, paths

    def run_demo(self, device_name: str = "fw-norte-matriz") -> Path:
        """PDF de demonstração com dados fictícios (sem FAZ)."""
        from forti_report.data.models import SectionData, SiteRankingItem

        unit = UnitReport(
            device_name=device_name,
            display_name=f"Unidade {device_name}",
            period_start=datetime.now(),
            period_end=datetime.now(),
            sections=[
                SectionData(
                    key="top-sites",
                    title="Ranking de sites acessados",
                    site_ranking=[
                        SiteRankingItem("google.com", hits=1200),
                        SiteRankingItem("microsoft.com", hits=890),
                        SiteRankingItem("youtube.com", hits=650),
                        SiteRankingItem("linkedin.com", hits=420),
                        SiteRankingItem("fortinet.com", hits=310),
                    ],
                )
            ],
        )
        doc = ReportDocument(title="Relatório de demonstração", units=[unit])
        paths = PdfReportBuilder(self.settings, self.registry).build_document(doc)
        return paths[0]

    def fetch_hierarchy(
        self,
        *,
        days: int = 60,
        download: bool = False,
    ) -> HierarchyImportResult:
        """Importa relatórios por dispositivo e agrupa por unidade regional."""
        import_result = self.import_all_units(days=days, download=download)
        reports_map = {u.device_name: u for u in import_result.units}

        with FortiAnalyzerClient(self.settings) as client:
            client.login()
            devices = DeviceService(client, self.settings).list_devices()

        hierarchy = build_regional_hierarchy(devices, reports_map)
        out = HierarchyImportResult()
        out.regional_units = hierarchy
        out.import_result = import_result
        return out

    def save_hierarchy_manifest(
        self,
        result: HierarchyImportResult,
        path: Path | None = None,
    ) -> Path:
        out = path or (self.settings.output_dir / "hierarchy.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": datetime.now().isoformat(),
            "adom": self.settings.faz_adom,
            "regional_units": [
                {
                    "code": ru.code,
                    "display_name": ru.display_name,
                    "antenna_count": ru.antenna_count,
                    "reports_linked": ru.reports_linked,
                    "antennas": [
                        {
                            "device_name": a.device_name,
                            "display_name": a.display_name,
                            "site_slug": a.site_slug,
                            "ip": a.ip,
                            "platform": a.platform,
                            "online": a.online,
                            "report": _unit_to_manifest(a.report) if a.report else None,
                        }
                        for a in ru.antennas
                    ],
                }
                for ru in result.regional_units
            ],
        }
        if result.import_result:
            payload["download_denied"] = result.import_result.download_denied
            payload["errors"] = result.import_result.errors
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return out

    def generate_regional_pdf(self, regional_unit: RegionalUnit, output_path: Path | None = None) -> Path:
        out = output_path or (
            self.settings.output_dir
            / "unidades"
            / f"{regional_unit.code}_{datetime.now():%Y%m%d}.pdf"
        )
        return RegionalPdfBuilder(self.settings, self.registry).build(regional_unit, out)

    def generate_all_regional_pdfs(self, result: HierarchyImportResult) -> list[Path]:
        paths: list[Path] = []
        for ru in result.regional_units:
            paths.append(self.generate_regional_pdf(ru))
        return paths

    def pull_hierarchy(self, *, days: int = 60, download: bool = False) -> HierarchyImportResult:
        result = self.fetch_hierarchy(days=days, download=download)
        manifest = self.save_hierarchy_manifest(result)
        print(f"Hierarquia salva: {manifest}")
        return result


def _unit_to_manifest(u: UnitReport) -> dict[str, Any]:
    return {
        "device_name": u.device_name,
        "display_name": u.display_name,
        "faz_tid": u.faz_tid,
        "report_name": u.report_name,
        "report_title": u.report_title,
        "available_formats": u.available_formats,
        "period_start": u.period_start.isoformat() if u.period_start else None,
        "period_end": u.period_end.isoformat() if u.period_end else None,
        "sections": [s.key for s in u.sections],
        "site_count": sum(len(s.site_ranking) for s in u.sections),
        "has_mensal_data": bool(u.mensal and u.mensal.has_content),
        "import_note": u.import_note,
    }


def _device_display_name(report: dict, device_name: str) -> str:
    parsed = parse_device_name(device_name)
    if parsed:
        return site_display_name(parsed[1])
    title = report.get("title") or ""
    name = report.get("name") or ""
    if device_name in name:
        return name.split(device_name)[0].strip(" -") or device_name
    return title or device_name


def _parse_period(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y/%m/%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None
