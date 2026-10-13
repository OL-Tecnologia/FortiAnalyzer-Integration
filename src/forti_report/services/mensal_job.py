"""Job de geração MENSAL com progresso (uso pela API web)."""

from __future__ import annotations

import threading
from pathlib import Path

from forti_report.config import Settings, get_settings
from forti_report.services.job_store import JobRecord, JobStore
from forti_report.services.progress import ProgressEvent, clamp_percent

_store = JobStore()


def get_job_store() -> JobStore:
    return _store


def start_mensal_job(
    *,
    days: int = 60,
    download: bool = True,
    force_download: bool = False,
    charts: bool = True,
    reports: list[str] | None = None,
    settings: Settings | None = None,
    portal_session_id: str = "",
) -> JobRecord:
    settings = settings or get_settings()
    updates: dict = {}
    if force_download:
        updates["faz_prefer_cache"] = False
    if not charts:
        updates["pdf_mensal_charts"] = False
    if updates:
        settings = settings.model_copy(update=updates)

    record = _store.create(adom=settings.faz_adom, portal_session_id=portal_session_id)
    cycles = _normalize_reports(reports)

    def run() -> None:
        _run_job(record, settings, days=days, download=download, reports=cycles)

    threading.Thread(target=run, daemon=True).start()
    return record


def _emit(
    record: JobRecord,
    percent: int,
    step: str,
    message: str,
    *,
    status: str = "running",
    phase: str = "",
    phase_percent: int = 0,
    extra: dict | None = None,
) -> None:
    record.push(
        ProgressEvent(
            percent=clamp_percent(percent),
            step=step,
            message=message,
            status=status,
            phase=phase,
            phase_percent=phase_percent,
            extra=extra,
        )
    )


def _normalize_reports(reports: list[str] | None) -> list[str]:
    allowed = ("diario", "semanal", "mensal")
    chosen = [cycle for cycle in allowed if cycle in set(reports or [])]
    return chosen or ["mensal"]


def _run_job(
    record: JobRecord,
    settings: Settings,
    *,
    days: int,
    download: bool,
    reports: list[str],
) -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    import zipfile

    from forti_report.services.consolidated import generate_consolidated
    from forti_report.services.cycle_schedule import CYCLE_TITLES

    try:
        moment = datetime.now(ZoneInfo(settings.mensal_schedule_timezone))
        paths: list[Path] = []
        for index, cycle in enumerate(reports):
            title = CYCLE_TITLES[cycle]
            _emit(
                record,
                int(index * 90 / max(len(reports), 1)),
                "pdf",
                f"Montando {title}…",
                phase="pdf",
                phase_percent=10,
            )
            path = generate_consolidated(
                settings,
                cycle,
                when=moment,
                refresh=download and index == 0,
            )
            paths.append(path)
            _emit(
                record,
                int((index + 1) * 90 / max(len(reports), 1)),
                "pdf",
                f"{title} pronto: {path.name}",
                phase="pdf",
                phase_percent=100,
            )

        final = paths[0]
        if len(paths) > 1:
            final = settings.output_dir / f"CONSOLIDADOS_{moment.strftime('%Y-%m-%d')}.zip"
            with zipfile.ZipFile(final, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in paths:
                    archive.write(path, arcname=path.name)
        record.pdf_path = final
        _emit(
            record,
            100,
            "done",
            "Relatório gerado com sucesso.",
            status="completed",
            phase="finalize",
            phase_percent=100,
            extra={
                "pdf_filename": final.name,
                "download_url": f"/api/reports/mensal/jobs/{record.job_id}/download",
            },
        )
    except Exception as exc:
        record.error = str(exc)
        _emit(record, 100, "done", str(exc), status="failed", phase="finalize", phase_percent=100)
