"""Disparo dos três consolidados no horário do cliente."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from forti_report.config import Settings
from forti_report.services.cycle_schedule import (
    clocks_from_settings,
    cycles_due,
    next_slot,
    now_in_tz,
    period_key,
)
from forti_report.services.consolidated import generate_consolidated

logger = logging.getLogger(__name__)

_STATE_FILENAME = "cycle_state.json"


@dataclass
class CycleRunResult:
    cycle: str
    status: str
    period: str
    message: str
    pdf_path: str | None = None


def cycle_state_path(settings: Settings) -> Path:
    path = settings.mensal_schedule_state_dir / _STATE_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load_cycle_state(settings: Settings) -> dict:
    path = cycle_state_path(settings)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_cycle_state(settings: Settings, state: dict) -> None:
    path = cycle_state_path(settings)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def run_due_cycles(
    settings: Settings,
    *,
    when: datetime | None = None,
    source: str = "scheduler",
) -> list[CycleRunResult]:
    """Gera os ciclos que já passaram das 06:00 (ou da hora do cliente) e ainda não saíram hoje."""
    moment = when or now_in_tz(settings)
    clocks = clocks_from_settings(settings)
    due = cycles_due(moment, clocks)
    state = load_cycle_state(settings)
    pending = [cycle for cycle in due if _needs_run(settings, state, cycle, moment)]
    if not pending:
        return []

    refreshed = False
    if settings.faz_user and settings.faz_password:
        try:
            from forti_report.services.harvest import harvest_reports

            harvest_reports(settings, days=90)
            refreshed = True
        except Exception as exc:
            logger.warning("Colheita antes do consolidado falhou: %s", exc)

    results: list[CycleRunResult] = []
    for cycle in pending:
        key = period_key(cycle, moment)
        try:
            path = generate_consolidated(settings, cycle, when=moment, refresh=False)
            _remember(state, cycle, key, "success", str(path), "")
            _maybe_email(settings, cycle, path, moment)
            results.append(
                CycleRunResult(cycle, "success", key, f"PDF gerado ({source})", str(path))
            )
        except Exception as exc:
            _remember(state, cycle, key, "failed", "", str(exc))
            results.append(CycleRunResult(cycle, "failed", key, str(exc)))
    save_cycle_state(settings, state)
    if refreshed:
        logger.info("Colheita atualizada antes de %s", ", ".join(pending))
    return results


def seconds_until_next_slot(settings: Settings, *, when: datetime | None = None) -> float:
    moment = when or now_in_tz(settings)
    slot = next_slot(moment, clocks_from_settings(settings))
    return max(1.0, (slot - moment).total_seconds())


def _needs_run(settings: Settings, state: dict, cycle: str, when: datetime) -> bool:
    key = period_key(cycle, when)
    entry = state.get(cycle) if isinstance(state.get(cycle), dict) else {}
    if entry.get("period") == key and entry.get("status") == "success":
        return False
    if entry.get("period") == key and entry.get("status") == "failed":
        attempts = int(entry.get("attempts") or 0)
        if attempts >= settings.mensal_schedule_max_retries:
            return False
        last = str(entry.get("last_attempt_at") or "")
        if last:
            try:
                tried = datetime.fromisoformat(last)
            except ValueError:
                tried = None
            if tried is not None and when < tried + timedelta(hours=settings.mensal_schedule_retry_hours):
                return False
    return True


def _remember(state: dict, cycle: str, period: str, status: str, pdf_path: str, error: str) -> None:
    previous = state.get(cycle) if isinstance(state.get(cycle), dict) else {}
    attempts = int(previous.get("attempts") or 0)
    if previous.get("period") != period:
        attempts = 0
    if status == "failed":
        attempts += 1
    state[cycle] = {
        "period": period,
        "status": status,
        "pdf_path": pdf_path,
        "error": error,
        "attempts": attempts,
        "last_attempt_at": datetime.now().isoformat(timespec="seconds"),
    }


def _maybe_email(settings: Settings, cycle: str, pdf_path: Path, when: datetime) -> None:
    if not settings.smtp_host or not settings.smtp_to:
        return
    from forti_report.services.cycle_schedule import CYCLE_TITLES
    from forti_report.services.email_delivery import _parse_recipients, send_email

    title = CYCLE_TITLES[cycle]
    client = settings.client_display_name or settings.client_slug or "FortiAnalyzer"
    try:
        send_email(
            settings,
            subject=f"{client} | {title}",
            body=f"Segue o {title.lower()} consolidado.\n",
            to_addrs=_parse_recipients(settings.smtp_to),
            cc_addrs=_parse_recipients(settings.smtp_cc),
            pdf_path=pdf_path,
        )
    except Exception as exc:
        logger.warning("PDF %s pronto; e-mail não enviado: %s", cycle, exc)
        return
    logger.info("E-mail %s enviado em %s", cycle, when.isoformat(timespec="seconds"))
