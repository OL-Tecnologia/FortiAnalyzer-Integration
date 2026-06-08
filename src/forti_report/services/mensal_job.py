"""Job de geração MENSAL com progresso (uso pela API web)."""

from __future__ import annotations

import threading
from pathlib import Path

from forti_report.config import Settings, get_settings
from forti_report.services.job_store import JobRecord, JobStore
from forti_report.services.mensal_pipeline import MensalReportPipeline
from forti_report.services.progress import ProgressCallback, ProgressEvent, ProgressUpdate, clamp_percent

_store = JobStore()


def get_job_store() -> JobStore:
    return _store


def start_mensal_job(
    *,
    days: int = 60,
    download: bool = True,
    force_download: bool = False,
    charts: bool = True,
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

    def run() -> None:
        _run_job(record, settings, days=days, download=download)

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


def _run_job(record: JobRecord, settings: Settings, *, days: int, download: bool) -> None:
    try:
        _emit(
            record,
            0,
            "init",
            f"Iniciando relatório MENSAL — ADOM {settings.faz_adom}",
            phase="faz",
            phase_percent=0,
        )

        def on_progress(update: ProgressUpdate) -> None:
            _emit(
                record,
                update.percent,
                update.step,
                update.message,
                phase=update.phase,
                phase_percent=update.phase_percent,
            )

        pipeline = MensalReportPipeline(settings)
        path = pipeline.generate_unified_pdf(
            days=days,
            download=download,
            on_progress=on_progress,
        )
        record.pdf_path = path
        _emit(
            record,
            100,
            "done",
            "Relatório gerado com sucesso.",
            status="completed",
            phase="finalize",
            phase_percent=100,
            extra={
                "pdf_filename": path.name,
                "download_url": f"/api/reports/mensal/jobs/{record.job_id}/download",
            },
        )
    except Exception as exc:
        record.error = str(exc)
        record.push(
            ProgressEvent(
                percent=record.events[-1].percent if record.events else 0,
                step="error",
                message=str(exc),
                status="failed",
                extra={"error": str(exc)},
            )
        )
