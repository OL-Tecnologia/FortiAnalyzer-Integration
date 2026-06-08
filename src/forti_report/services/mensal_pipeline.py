"""Pipeline MENSAL- RELATÓRIO GERAL → PDF unificado."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from forti_report.config import Settings, get_settings
from forti_report.data.hierarchy import RegionalUnit, parse_device_name, site_display_name
from forti_report.data.mensal_models import MensalGeralReport
from forti_report.data.parsers.faz_xml import decode_faz_payload, parse_report_xml_to_sections
from forti_report.data.parsers.mensal_json import parse_mensal_json
from forti_report.data.parsers.mensal_pdf import parse_mensal_geral_pdf
from forti_report.data.models import UnitReport
from forti_report.faz.client import FortiAnalyzerClient, FortiAnalyzerError
from forti_report.faz.devices import DeviceService
from forti_report.faz.reports import ReportService
from forti_report.pdf.unified_mensal_builder import UnifiedMensalPdfBuilder
from forti_report.services.mensal_cache import (
    MensalCacheMeta,
    chart_scope_for_unit,
    json_cache_is_fresh,
    load_cache_meta,
    mensal_pdf_filename,
    prune_stale_chart_cache,
    save_cache_meta,
)
from forti_report.services.pipeline import HierarchyImportResult, ReportPipeline, _parse_period
from forti_report.services.progress import ProgressCallback, ProgressReporter


class MensalReportPipeline:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._base = ReportPipeline(self.settings)

    def fetch_hierarchy(
        self,
        *,
        days: int = 60,
        download: bool = True,
        on_progress: ProgressCallback | None = None,
    ) -> HierarchyImportResult:
        prog = ProgressReporter(on_progress)

        prog.emit(phase="faz", step="faz", message="Conectando ao FortiAnalyzer...", phase_percent=2)
        if not download and self.settings.faz_prefer_cache:
            prog.emit(phase="faz", step="cache", message="Verificando cache local...", phase_percent=8)
            cached = self._fetch_hierarchy_from_cache(days=days)
            if cached is not None:
                total = sum(u.antenna_count for u in cached.regional_units)
                prog.emit(
                    phase="faz",
                    step="cache",
                    message=f"Cache validado — {total} antena(s).",
                    phase_percent=100,
                )
                return cached

        prog.emit(phase="faz", step="metadata", message="Consultando relatórios no FortiAnalyzer...", phase_percent=12)
        import_result = self._base.import_all_units(days=days, download=False)
        reports_map = {u.device_name: u for u in import_result.units}
        device_names = list(reports_map.keys())
        total_devices = max(len(device_names), 1)

        if download:
            with FortiAnalyzerClient(self.settings) as client:
                client.login()
                service = ReportService(client, self.settings)
                for idx, device_name in enumerate(device_names):
                    phase_pct = 15 + int(75 * (idx + 1) / total_devices)
                    display = _antenna_display_name(device_name)
                    prog.emit(
                        phase="faz",
                        step="antenna",
                        message=f"Antena {idx + 1}/{total_devices}: {display}",
                        phase_percent=phase_pct,
                    )
                    reports_map[device_name] = self._enrich_unit(
                        service, reports_map[device_name], days=days, download=download
                    )
        else:
            prog.emit(phase="faz", step="metadata", message="Metadados carregados (sem download).", phase_percent=85)

        prog.emit(phase="hierarchy", step="hierarchy", message="Montando hierarquia (unidades e antenas)...", phase_percent=20)
        with FortiAnalyzerClient(self.settings) as client:
            client.login()
            devices = DeviceService(client, self.settings).list_devices()

        from forti_report.data.hierarchy import build_regional_hierarchy

        out = HierarchyImportResult()
        out.regional_units = build_regional_hierarchy(devices, reports_map)
        out.import_result = import_result
        prog.emit(phase="hierarchy", step="hierarchy", message="Hierarquia pronta.", phase_percent=100)
        return out

    def _fetch_hierarchy_from_cache(self, *, days: int) -> HierarchyImportResult | None:
        """Hierarquia a partir de JSON local, só se cada arquivo for do relatório atual no FAZ."""
        cache_dir = self.settings.faz_mensal_cache_dir
        if not cache_dir.is_dir():
            return None

        json_devices = sorted(p.stem for p in cache_dir.glob("*.json"))
        if not json_devices:
            return None

        try:
            with FortiAnalyzerClient(self.settings) as client:
                client.login()
                service = ReportService(client, self.settings)
                reports_map: dict[str, UnitReport] = {}
                for device_name in json_devices:
                    latest = service.find_latest_report_for_device(device_name, days=days)
                    if not json_cache_is_fresh(cache_dir, device_name, latest):
                        return None
                    mensal = self._load_json_cache(device_name)
                    if not mensal:
                        return None
                    unit = UnitReport(
                        device_name=device_name,
                        display_name=_antenna_display_name(device_name),
                        mensal=mensal,
                        import_note="Cache JSON (relatório atual no FAZ)",
                    )
                    if latest:
                        unit.faz_tid = latest.get("tid")
                        unit.period_start = _parse_period(latest.get("period-start"))
                        unit.period_end = _parse_period(latest.get("period-end"))
                        unit.report_name = latest.get("name")
                        unit.report_title = latest.get("title")
                    reports_map[device_name] = unit
        except FortiAnalyzerError:
            return None

        if not reports_map:
            return None

        devices = [
            {"name": name, "ip": None, "platform_str": None, "dev_status": 1}
            for name in reports_map
        ]
        from forti_report.data.hierarchy import build_regional_hierarchy

        out = HierarchyImportResult()
        out.regional_units = build_regional_hierarchy(devices, reports_map)
        return out if out.regional_units else None

    def generate_unified_pdf(
        self,
        *,
        days: int = 60,
        download: bool = True,
        output_path: Path | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> Path:
        hierarchy = self.fetch_hierarchy(days=days, download=download, on_progress=on_progress)
        prog = ProgressReporter(on_progress)
        out = output_path or (
            self.settings.output_dir / mensal_pdf_filename(self.settings)
        )

        scopes = {
            chart_scope_for_unit(ant.report)
            for ru in hierarchy.regional_units
            for ant in ru.antennas
            if ant.report
        }

        def pdf_progress(phase_percent: int, message: str) -> None:
            prog.emit(phase="pdf", step="pdf", message=message, phase_percent=phase_percent)

        prog.emit(phase="pdf", step="pdf", message="Preparando montagem do PDF...", phase_percent=0)
        path = UnifiedMensalPdfBuilder(self.settings).build(
            hierarchy.regional_units,
            out,
            adom=self.settings.faz_adom,
            on_progress=pdf_progress,
        )
        prog.emit(phase="finalize", step="finalize", message="Atualizando cache de gráficos...", phase_percent=40)
        prune_stale_chart_cache(self.settings, scopes)
        prog.emit(phase="finalize", step="finalize", message=f"Salvando {path.name}...", phase_percent=100)
        return path

    def _enrich_unit(
        self, service: ReportService, unit: UnitReport, *, days: int, download: bool = True
    ) -> UnitReport:
        unit.display_name = _antenna_display_name(unit.device_name)
        mensal, note = self._load_mensal_content(service, unit, days=days, download=download)
        if mensal:
            unit.mensal = mensal
            unit.import_note = note or "Dados carregados com sucesso"
        elif note:
            unit.import_note = note
        return unit

    def _sync_unit_from_faz(self, unit: UnitReport, latest: dict | None) -> None:
        if not latest:
            return
        unit.faz_tid = latest.get("tid") or unit.faz_tid
        unit.period_start = _parse_period(latest.get("period-start")) or unit.period_start
        unit.period_end = _parse_period(latest.get("period-end")) or unit.period_end
        unit.report_name = latest.get("name") or unit.report_name
        unit.report_title = latest.get("title") or unit.report_title

    def _load_mensal_content(
        self,
        service: ReportService,
        unit: UnitReport,
        *,
        days: int,
        download: bool = True,
    ) -> tuple[MensalGeralReport | None, str | None]:
        latest = service.find_latest_report_for_device(unit.device_name, days=days)
        self._sync_unit_from_faz(unit, latest)

        cache_dir = self.settings.faz_mensal_cache_dir
        use_cache = (
            self.settings.faz_prefer_cache
            and download
            and latest
            and json_cache_is_fresh(cache_dir, unit.device_name, latest)
        )
        if use_cache:
            cached = self._load_json_cache(unit.device_name)
            if cached:
                return cached, "Cache JSON (relatório atual no FAZ)"

        tid = unit.faz_tid
        if not tid and latest:
            tid = latest.get("tid")
        if not tid:
            return None, "Nenhum relatório MENSAL no período"

        if not download:
            cached = self._load_json_cache(unit.device_name)
            if cached and latest and json_cache_is_fresh(cache_dir, unit.device_name, latest):
                return cached, "Cache JSON (relatório atual no FAZ)"
            if cached:
                return None, (
                    "Cache local desatualizado (relatório novo no FAZ). "
                    "Gere sem --metadata-only ou use --force-download."
                )
            return None, "Metadados apenas — use cache local ou habilite download"

        for fmt in ("JSON", "XML", "PDF"):
            try:
                payload = service.download_report(tid, fmt=fmt)  # type: ignore[arg-type]
                raw = decode_faz_payload(
                    payload.get("data", ""),
                    data_type=payload.get("data-type"),
                )
                self._save_cache(unit.device_name, fmt, raw)
                if latest:
                    meta = MensalCacheMeta.from_faz_report(latest)
                    if meta:
                        save_cache_meta(cache_dir, unit.device_name, meta)
                mensal = self._parse_raw(raw, fmt=fmt, device_name=unit.device_name)
                if mensal and mensal.has_content:
                    unit.sections = parse_report_xml_to_sections(raw) if fmt == "XML" else unit.sections
                    return mensal, f"Download {fmt} OK"
                if mensal:
                    return mensal, f"Download {fmt} OK (parcial)"
            except FortiAnalyzerError as e:
                if "Access denied" in str(e):
                    continue
                return None, str(e)
            except Exception as e:
                return None, str(e)

        cached = self._load_from_cache(unit.device_name)
        if cached:
            return cached, "Dados do cache local (PDF)"

        return None, (
            "Download negado pelo FAZ (Access denied). "
            "Coloque PDFs em output/faz_mensal/ ou libere permissão de export."
        )

    def _parse_raw(self, raw: bytes, *, fmt: str, device_name: str) -> MensalGeralReport | None:
        if fmt == "JSON":
            return parse_mensal_json(raw, device_name=device_name)
        if fmt == "PDF":
            cache_path = self._cache_path(device_name, "pdf")
            cache_path.write_bytes(raw)
            return parse_mensal_geral_pdf(cache_path, device_name=device_name)
        if fmt == "XML":
            sections = parse_report_xml_to_sections(raw)
            if not sections:
                return None
            mensal = MensalGeralReport(device_name=device_name)
            for section in sections:
                if section.site_ranking:
                    from forti_report.data.wan_models import RankedItem

                    mensal.top_sites_by_browsing = [
                        RankedItem(rank=i + 1, label=s.site, value=str(s.hits or ""))
                        for i, s in enumerate(section.site_ranking[:20])
                    ]
            return mensal if mensal.has_content else None
        return None

    def _cache_path(self, device_name: str, ext: str) -> Path:
        safe = device_name.replace("/", "-").replace("[", "_").replace("]", "")
        return self.settings.faz_mensal_cache_dir / f"{safe}.{ext.lower()}"

    def _save_cache(self, device_name: str, fmt: str, raw: bytes) -> None:
        self.settings.faz_mensal_cache_dir.mkdir(parents=True, exist_ok=True)
        ext = fmt.lower()
        self._cache_path(device_name, ext).write_bytes(raw)

    def _load_json_cache(self, device_name: str) -> MensalGeralReport | None:
        path = self._cache_path(device_name, "json")
        if not path.is_file():
            return None
        try:
            mensal = parse_mensal_json(path.read_bytes(), device_name=device_name)
            return mensal if mensal.has_content else None
        except Exception:
            return None

    def _load_from_cache(self, device_name: str) -> MensalGeralReport | None:
        cache_dir = self.settings.faz_mensal_cache_dir
        if not cache_dir.is_dir():
            return None
        needle = device_name.lower().replace("[root]", "")
        patterns = [
            cache_dir / f"{device_name.replace('/', '-')}.pdf",
            cache_dir / f"{device_name.replace('/', '-').replace('[', '_').replace(']', '')}.pdf",
        ]
        for path in patterns:
            if path.is_file():
                return parse_mensal_geral_pdf(path, device_name=device_name)
        for path in sorted(cache_dir.glob("*.pdf")):
            name = path.name.lower()
            if needle in name or device_name.lower() in name:
                return parse_mensal_geral_pdf(path, device_name=device_name)
        return None


def _antenna_display_name(device_name: str) -> str:
    parsed = parse_device_name(device_name)
    if parsed:
        return site_display_name(parsed[1])
    return device_name
