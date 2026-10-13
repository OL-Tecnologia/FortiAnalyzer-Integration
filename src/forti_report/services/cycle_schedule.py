"""Quando cada consolidado sai.

Diário: todo dia às 06:00.
Semanal: segunda-feira às 06:00, junto com o diário.
Mensal: dia 1 às 06:00, junto com o diário daquele dia.
Se o dia 1 cair numa segunda, os três saem na mesma leva.
Hora e minuto vêm do cliente; 06:00 é só o padrão.
"""

from __future__ import annotations

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


def cycles_due(when: datetime, *, hour: int = 6, minute: int = 0) -> tuple[str, ...]:
    """Ciclos que já podem sair neste instante. Antes da hora marcada, nenhum."""
    slot = when.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if when < slot:
        return ()
    due = ["diario"]
    if when.weekday() == 0:
        due.append("semanal")
    if when.day == 1:
        due.append("mensal")
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


def next_slot(when: datetime, *, hour: int = 6, minute: int = 0) -> datetime:
    slot = when.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if slot <= when:
        slot += timedelta(days=1)
    return slot


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
