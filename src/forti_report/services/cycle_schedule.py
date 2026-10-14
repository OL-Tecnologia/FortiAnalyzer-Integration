"""Quando cada consolidado sai.

Cada PDF tem o próprio horário.
Sem configuração própria, o padrão é: diário todo dia, semanal na segunda e mensal no dia 1, às 06:00.
Se os três coincidirem, saem na mesma leva.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from forti_report.config import Settings, get_settings

CYCLE_ORDER: tuple[str, ...] = ("diario", "semanal", "mensal")
CYCLE_TITLES: dict[str, str] = {
    "diario": "RELATÓRIO DIÁRIO",
    "semanal": "RELATÓRIO SEMANAL",
    "mensal": "RELATÓRIO MENSAL",
}
# O FortiAnalyzer grava o diário às 08:00. Antes disso o arquivo do dia ainda não existe.
FAZ_READY_HOUR = 8


@dataclass(frozen=True)
class CycleClock:
    enabled: bool = True
    hour: int = 6
    minute: int = 0
    weekday: int = 0
    day: int = 1


def default_clocks(*, hour: int = 6, minute: int = 0) -> dict[str, CycleClock]:
    return {
        "diario": CycleClock(hour=hour, minute=minute),
        "semanal": CycleClock(hour=hour, minute=minute, weekday=0),
        "mensal": CycleClock(hour=hour, minute=minute, day=1),
    }


def clocks_from_settings(settings: Settings) -> dict[str, CycleClock]:
    if not settings.report_schedules_configured:
        return default_clocks(
            hour=settings.mensal_schedule_hour,
            minute=settings.mensal_schedule_minute,
        )
    return {
        "diario": CycleClock(
            enabled=settings.report_diario_enabled,
            hour=settings.report_diario_hour,
            minute=settings.report_diario_minute,
        ),
        "semanal": CycleClock(
            enabled=settings.report_semanal_enabled,
            hour=settings.report_semanal_hour,
            minute=settings.report_semanal_minute,
            weekday=settings.report_semanal_weekday,
        ),
        "mensal": CycleClock(
            enabled=settings.report_mensal_enabled,
            hour=settings.report_mensal_hour,
            minute=settings.report_mensal_minute,
            day=settings.report_mensal_day,
        ),
    }


def clocks_from_schedule(schedule) -> dict[str, CycleClock]:
    diario = schedule.diario
    semanal = schedule.semanal
    mensal = schedule.mensal
    return {
        "diario": CycleClock(enabled=diario.enabled, hour=diario.hour, minute=diario.minute),
        "semanal": CycleClock(
            enabled=semanal.enabled,
            hour=semanal.hour,
            minute=semanal.minute,
            weekday=semanal.weekday,
        ),
        "mensal": CycleClock(
            enabled=mensal.enabled,
            hour=mensal.hour,
            minute=mensal.minute,
            day=mensal.day,
        ),
    }


def cycles_due(
    when: datetime,
    clocks: dict[str, CycleClock] | None = None,
    *,
    hour: int = 6,
    minute: int = 0,
) -> tuple[str, ...]:
    """Ciclos cujo horário de hoje já passou. Cada PDF obedece o próprio relógio."""
    clocks = clocks or default_clocks(hour=hour, minute=minute)
    due: list[str] = []
    for cycle in CYCLE_ORDER:
        clock = clocks[cycle]
        if not clock.enabled or when < _slot_on(when, clock):
            continue
        if cycle == "semanal" and when.weekday() != clock.weekday:
            continue
        if cycle == "mensal" and when.day != clock.day:
            continue
        due.append(cycle)
    return tuple(due)


def period_key(cycle: str, when: datetime) -> str:
    """Chave que impede gerar o mesmo ciclo duas vezes no mesmo disparo."""
    if cycle == "diario":
        return when.date().isoformat()
    if cycle == "semanal":
        monday = when.date() - timedelta(days=when.weekday())
        return monday.isoformat()
    if cycle == "mensal":
        return when.strftime("%Y-%m")
    raise ValueError(f"ciclo desconhecido: {cycle}")


def next_slot(
    when: datetime,
    clocks: dict[str, CycleClock] | None = None,
    *,
    hour: int = 6,
    minute: int = 0,
) -> datetime:
    clocks = clocks or default_clocks(hour=hour, minute=minute)
    moments = [
        _next_occurrence(when, name, clock)
        for name, clock in clocks.items()
        if clock.enabled
    ]
    if not moments:
        return when + timedelta(hours=1)
    return min(moments)


def upcoming_runs(when: datetime, clocks: dict[str, CycleClock]) -> dict[str, datetime]:
    return {
        name: _next_occurrence(when, name, clock)
        for name, clock in clocks.items()
        if clock.enabled
    }


def _slot_on(when: datetime, clock: CycleClock) -> datetime:
    return when.replace(hour=clock.hour, minute=clock.minute, second=0, microsecond=0)


def _next_occurrence(when: datetime, cycle: str, clock: CycleClock) -> datetime:
    slot = _slot_on(when, clock)
    if cycle == "diario":
        if slot <= when:
            slot += timedelta(days=1)
        return slot
    if cycle == "semanal":
        days = (clock.weekday - slot.weekday()) % 7
        slot += timedelta(days=days)
        if slot <= when:
            slot += timedelta(days=7)
        return slot
    year, month = slot.year, slot.month
    day = min(clock.day, calendar.monthrange(year, month)[1])
    candidate = slot.replace(day=day)
    if candidate <= when:
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
        day = min(clock.day, calendar.monthrange(year, month)[1])
        candidate = candidate.replace(year=year, month=month, day=day)
    return candidate


def closed_through(when: datetime) -> date:
    """Último dia cujo arquivo das 08:00 já foi gravado no FortiAnalyzer."""
    if when.hour < FAZ_READY_HOUR:
        return when.date() - timedelta(days=1)
    return when.date()


def completed_week(when: datetime) -> tuple[date, date]:
    """Semana segunda–domingo já encerrada antes do dia de `when`."""
    today = when.date()
    days_after_sunday = (today.weekday() + 1) % 7
    if days_after_sunday == 0:
        days_after_sunday = 7
    sunday = today - timedelta(days=days_after_sunday)
    monday = sunday - timedelta(days=6)
    return monday, sunday


def previous_month(when: datetime) -> tuple[date, date]:
    first_this = when.date().replace(day=1)
    last_prev = first_this - timedelta(days=1)
    return last_prev.replace(day=1), last_prev


def now_in_tz(settings: Settings | None = None) -> datetime:
    settings = settings or get_settings()
    return datetime.now(ZoneInfo(settings.mensal_schedule_timezone))
