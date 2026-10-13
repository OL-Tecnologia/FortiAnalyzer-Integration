"""Agendamento mensal: gera PDF MENSAL e envia por e-mail."""

from __future__ import annotations

import calendar
import json
import logging
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from forti_report.config import Settings, get_settings
from forti_report.services.cycle_runner import run_due_cycles, seconds_until_next_slot
from forti_report.services.email_delivery import send_failure_alert, send_mensal_report_email
from forti_report.services.mensal_pipeline import MensalReportPipeline

logger = logging.getLogger(__name__)

_STATE_FILENAME = "scheduler_state.json"

_background_stop: threading.Event | None = None
_background_thread: threading.Thread | None = None
_state_lock = threading.Lock()


@dataclass
class ScheduledRunResult:
    status: str  # skipped | success | failed
    period: str
    message: str
    pdf_path: str | None = None
    error: str | None = None


@dataclass
class SchedulerState:
    period: str = ""
    status: str = ""  # success | failed
    executed_at: str = ""
    attempts: int = 0
    last_attempt_at: str = ""
    pdf_path: str = ""
    error: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> SchedulerState:
        return cls(
            period=str(data.get("period", "")),
            status=str(data.get("status", "")),
            executed_at=str(data.get("executed_at", "")),
            attempts=int(data.get("attempts", 0) or 0),
            last_attempt_at=str(data.get("last_attempt_at", "")),
            pdf_path=str(data.get("pdf_path", "")),
            error=str(data.get("error", "")),
        )


@dataclass
class SchedulerStatus:
    enabled: bool
    period: str
    next_run_at: str
    last_success_period: str
    last_success_at: str
    last_status: str
    last_error: str
    attempts: int
    running: bool


def scheduler_state_path(settings: Settings) -> Path:
    path = settings.mensal_schedule_state_dir / _STATE_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def scheduler_log_path(settings: Settings) -> Path:
    logs_dir = settings.output_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir / f"scheduler-{datetime.now().strftime('%Y-%m-%d')}.log"


def _append_log(settings: Settings, message: str) -> None:
    line = f"{datetime.now().isoformat(timespec='seconds')} {message}\n"
    try:
        with scheduler_log_path(settings).open("a", encoding="utf-8") as handle:
            handle.write(line)
    except OSError:
        logger.warning("Não foi possível gravar log do scheduler")


def period_key(when: datetime | None = None, *, settings: Settings | None = None) -> str:
    ref = when or now_in_tz(settings)
    return ref.strftime("%Y-%m")


def now_in_tz(settings: Settings | None = None) -> datetime:
    settings = settings or get_settings()
    return datetime.now(ZoneInfo(settings.mensal_schedule_timezone))


def _clamp_day(year: int, month: int, day: int) -> int:
    return min(day, calendar.monthrange(year, month)[1])


def add_months(dt: datetime, months: int = 1) -> datetime:
    month_index = dt.month - 1 + months
    year = dt.year + month_index // 12
    month = month_index % 12 + 1
    day = _clamp_day(year, month, dt.day)
    return dt.replace(year=year, month=month, day=day)


def scheduled_datetime_for_period(
    period: str,
    settings: Settings,
) -> datetime:
    year, month = map(int, period.split("-"))
    day = _clamp_day(year, month, settings.mensal_schedule_day)
    tz = ZoneInfo(settings.mensal_schedule_timezone)
    return datetime(
        year,
        month,
        day,
        settings.mensal_schedule_hour,
        settings.mensal_schedule_minute,
        0,
        tzinfo=tz,
    )


def compute_next_run(settings: Settings, *, reference: datetime | None = None) -> datetime:
    ref = reference or now_in_tz(settings)
    tz = ZoneInfo(settings.mensal_schedule_timezone)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=tz)
    else:
        ref = ref.astimezone(tz)

    day = _clamp_day(ref.year, ref.month, settings.mensal_schedule_day)
    candidate = ref.replace(
        day=day,
        hour=settings.mensal_schedule_hour,
        minute=settings.mensal_schedule_minute,
        second=0,
        microsecond=0,
    )
    if candidate <= ref:
        candidate = add_months(candidate, 1)
        day = _clamp_day(candidate.year, candidate.month, settings.mensal_schedule_day)
        candidate = candidate.replace(day=day)
    return candidate


def load_scheduler_state(settings: Settings) -> SchedulerState:
    path = scheduler_state_path(settings)
    if not path.is_file():
        return SchedulerState()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return SchedulerState.from_dict(data)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return SchedulerState()


def save_scheduler_state(settings: Settings, state: SchedulerState) -> None:
    path = scheduler_state_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2), encoding="utf-8")


def _should_skip_run(settings: Settings, state: SchedulerState, *, force: bool) -> str | None:
    if force:
        return None

    current = period_key(settings=settings)
    if state.period == current and state.status == "success":
        return f"Relatório do período {current} já enviado com sucesso."

    if state.period == current and state.status == "failed":
        max_retries = (
            settings.mensal_schedule_max_retries
            if settings.mensal_schedule_retry_enabled
            else 1
        )
        if state.attempts >= max_retries:
            if not settings.mensal_schedule_retry_enabled:
                return (
                    f"Falha no período {current} e repetição desabilitada "
                    "(já houve 1 tentativa)."
                )
            return (
                f"Máximo de tentativas ({max_retries}) "
                f"atingido para o período {current}."
            )
        if state.last_attempt_at:
            last = datetime.fromisoformat(state.last_attempt_at)
            if last.tzinfo is None:
                last = last.replace(tzinfo=ZoneInfo(settings.mensal_schedule_timezone))
            retry_after = last + timedelta(hours=settings.mensal_schedule_retry_hours)
            if now_in_tz(settings) < retry_after:
                return f"Aguardando retry (próxima tentativa após {retry_after.isoformat()})."

    return None


def is_due_now(settings: Settings, *, reference: datetime | None = None) -> bool:
    ref = reference or now_in_tz(settings)
    current = period_key(ref, settings=settings)
    due_at = scheduled_datetime_for_period(current, settings)
    return ref >= due_at


def get_scheduler_status(settings: Settings | None = None) -> SchedulerStatus:
    settings = settings or get_settings()
    state = load_scheduler_state(settings)
    next_run = compute_next_run(settings)
    last_success_period = state.period if state.status == "success" else ""
    last_success_at = state.executed_at if state.status == "success" else ""
    return SchedulerStatus(
        enabled=settings.mensal_schedule_enabled,
        period=period_key(settings=settings),
        next_run_at=next_run.isoformat(),
        last_success_period=last_success_period,
        last_success_at=last_success_at,
        last_status=state.status,
        last_error=state.error,
        attempts=state.attempts,
        running=_background_thread is not None and _background_thread.is_alive(),
    )


def run_scheduled_mensal(
    settings: Settings | None = None,
    *,
    force: bool = False,
    source: str = "cli",
) -> ScheduledRunResult:
    settings = settings or get_settings()
    current_period = period_key(settings=settings)

    with _state_lock:
        state = load_scheduler_state(settings)
        skip_reason = _should_skip_run(settings, state, force=force)
        if skip_reason:
            _append_log(settings, f"[{source}] skip period={current_period} — {skip_reason}")
            return ScheduledRunResult(
                status="skipped",
                period=current_period,
                message=skip_reason,
            )

        if not force and not is_due_now(settings):
            next_run = compute_next_run(settings)
            message = f"Fora da janela agendada. Próxima execução: {next_run.isoformat()}"
            _append_log(settings, f"[{source}] skip period={current_period} — {message}")
            return ScheduledRunResult(status="skipped", period=current_period, message=message)

        if not settings.faz_user or not settings.faz_password:
            error = "FAZ_USER e FAZ_PASSWORD são obrigatórios para a rotina agendada."
            _append_log(settings, f"[{source}] failed period={current_period} — {error}")
            try:
                send_failure_alert(settings, error, context=f"origem={source}")
            except Exception as alert_exc:
                _append_log(settings, f"[{source}] alert failed — {alert_exc}")
            return ScheduledRunResult(status="failed", period=current_period, message=error, error=error)

        attempt = state.attempts + 1 if state.period == current_period else 1
        _append_log(settings, f"[{source}] start period={current_period} attempt={attempt}")

        pipeline_settings = settings
        if settings.mensal_schedule_force_download:
            pipeline_settings = settings.model_copy(update={"faz_prefer_cache": False})

        try:
            pipeline = MensalReportPipeline(pipeline_settings)
            pdf_path = pipeline.generate_unified_pdf(
                days=settings.mensal_schedule_days,
                download=True,
            )
            if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
                raise RuntimeError(f"PDF inválido ou vazio: {pdf_path}")

            send_mensal_report_email(settings, pdf_path, when=now_in_tz(settings))

            executed_at = now_in_tz(settings).isoformat()
            save_scheduler_state(
                settings,
                SchedulerState(
                    period=current_period,
                    status="success",
                    executed_at=executed_at,
                    attempts=attempt,
                    last_attempt_at=executed_at,
                    pdf_path=str(pdf_path),
                    error="",
                ),
            )
            _append_log(settings, f"[{source}] success period={current_period} pdf={pdf_path}")
            return ScheduledRunResult(
                status="success",
                period=current_period,
                message="Relatório gerado e e-mail enviado.",
                pdf_path=str(pdf_path),
            )
        except Exception as exc:
            error = str(exc)
            executed_at = now_in_tz(settings).isoformat()
            save_scheduler_state(
                settings,
                SchedulerState(
                    period=current_period,
                    status="failed",
                    executed_at=executed_at,
                    attempts=attempt,
                    last_attempt_at=executed_at,
                    pdf_path="",
                    error=error,
                ),
            )
            _append_log(settings, f"[{source}] failed period={current_period} — {error}")
            try:
                send_failure_alert(settings, error, context=f"origem={source}, período={current_period}")
            except Exception as alert_exc:
                _append_log(settings, f"[{source}] alert failed — {alert_exc}")
            return ScheduledRunResult(
                status="failed",
                period=current_period,
                message="Falha na rotina agendada.",
                error=error,
            )


def _iter_schedule_settings() -> list[Settings]:
    """Settings por tenant com agenda ligada (multi-tenant)."""
    from forti_report.clients import list_clients_or_legacy, settings_from_client

    out: list[Settings] = []
    for client in list_clients_or_legacy():
        if not client.schedule.enabled:
            continue
        out.append(settings_from_client(client, use_automation_credentials=True))
    if out:
        return out
    # Fallback legado: .env global
    settings = get_settings()
    if settings.mensal_schedule_enabled:
        return [settings]
    return []


def _scheduler_loop(stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        scheduled = _iter_schedule_settings()
        if not scheduled:
            stop_event.wait(60)
            continue

        any_ran = False
        min_wait = 3600.0
        for settings in scheduled:
            ran = run_due_cycles(settings, source="scheduler")
            if ran:
                any_ran = True
            min_wait = min(min_wait, seconds_until_next_slot(settings))

        if any_ran:
            stop_event.wait(60)
        else:
            stop_event.wait(min(min_wait, 3600.0))


def start_background_scheduler() -> threading.Event | None:
    global _background_stop, _background_thread

    scheduled = _iter_schedule_settings()
    if not scheduled:
        return None

    if _background_thread and _background_thread.is_alive():
        return _background_stop

    stop_event = threading.Event()
    thread = threading.Thread(target=_scheduler_loop, args=(stop_event,), name="mensal-scheduler", daemon=True)
    thread.start()
    _background_stop = stop_event
    _background_thread = thread
    first = scheduled[0]
    logger.info(
        "Scheduler dos consolidados iniciado (%s tenant(s); ex.: %02d:%02d)",
        len(scheduled),
        first.mensal_schedule_hour,
        first.mensal_schedule_minute,
    )
    return stop_event


def stop_background_scheduler(stop_event: threading.Event | None = None) -> None:
    global _background_stop, _background_thread
    target = stop_event or _background_stop
    if target:
        target.set()
    if _background_thread:
        _background_thread.join(timeout=5.0)
    _background_stop = None
    _background_thread = None
