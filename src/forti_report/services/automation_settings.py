"""Leitura/gravação das configs de automação (agendamento + e-mail) no .env."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from forti_report.config import Settings, get_settings
from forti_report.runtime_paths import project_root
from forti_report.services.env_file import apply_env_updates

# Chaves editáveis pelo painel (sem retornar valores de senha)
AUTOMATION_BOOL_KEYS = {
    "MENSAL_SCHEDULE_ENABLED",
    "MENSAL_SCHEDULE_FORCE_DOWNLOAD",
    "MENSAL_SCHEDULE_RETRY_ENABLED",
    "SMTP_USE_TLS",
    "SMTP_USE_SSL",
    "SMTP_USE_AUTH",
}

AUTOMATION_INT_KEYS = {
    "MENSAL_SCHEDULE_DAY",
    "MENSAL_SCHEDULE_HOUR",
    "MENSAL_SCHEDULE_MINUTE",
    "MENSAL_SCHEDULE_DAYS",
    "MENSAL_SCHEDULE_MAX_RETRIES",
    "MENSAL_SCHEDULE_RETRY_HOURS",
    "SMTP_PORT",
    "SMTP_TIMEOUT",
}

AUTOMATION_STR_KEYS = {
    "FAZ_USER",
    "MENSAL_SCHEDULE_TIMEZONE",
    "SMTP_HOST",
    "SMTP_USER",
    "SMTP_FROM",
    "SMTP_TO",
    "SMTP_CC",
    "SMTP_ALERT_TO",
}

SECRET_KEYS = {"FAZ_PASSWORD", "SMTP_PASSWORD"}


def env_path() -> Path:
    return project_root() / ".env"


@dataclass
class AutomationSettingsView:
    faz_user: str
    faz_password_set: bool
    mensal_schedule_enabled: bool
    mensal_schedule_day: int
    mensal_schedule_hour: int
    mensal_schedule_minute: int
    mensal_schedule_timezone: str
    mensal_schedule_days: int
    mensal_schedule_force_download: bool
    mensal_schedule_retry_enabled: bool
    mensal_schedule_max_retries: int
    mensal_schedule_retry_hours: int
    smtp_host: str
    smtp_port: int
    smtp_use_tls: bool
    smtp_use_ssl: bool
    smtp_use_auth: bool
    smtp_user: str
    smtp_password_set: bool
    smtp_timeout: int
    smtp_from: str
    smtp_to: str
    smtp_cc: str
    smtp_alert_to: str
    next_run_at: str = ""


def _as_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "sim", "s"}


def get_automation_settings(settings: Settings | None = None) -> AutomationSettingsView:
    settings = settings or get_settings()
    from forti_report.services.mensal_scheduler import get_scheduler_status

    status = get_scheduler_status(settings)
    return AutomationSettingsView(
        faz_user=settings.faz_user,
        faz_password_set=bool(settings.faz_password),
        mensal_schedule_enabled=settings.mensal_schedule_enabled,
        mensal_schedule_day=settings.mensal_schedule_day,
        mensal_schedule_hour=settings.mensal_schedule_hour,
        mensal_schedule_minute=settings.mensal_schedule_minute,
        mensal_schedule_timezone=settings.mensal_schedule_timezone,
        mensal_schedule_days=settings.mensal_schedule_days,
        mensal_schedule_force_download=settings.mensal_schedule_force_download,
        mensal_schedule_retry_enabled=settings.mensal_schedule_retry_enabled,
        mensal_schedule_max_retries=settings.mensal_schedule_max_retries,
        mensal_schedule_retry_hours=settings.mensal_schedule_retry_hours,
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_use_tls=settings.smtp_use_tls,
        smtp_use_ssl=settings.smtp_use_ssl,
        smtp_use_auth=settings.smtp_use_auth,
        smtp_user=settings.smtp_user,
        smtp_password_set=bool(settings.smtp_password),
        smtp_timeout=settings.smtp_timeout,
        smtp_from=settings.smtp_from,
        smtp_to=settings.smtp_to,
        smtp_cc=settings.smtp_cc,
        smtp_alert_to=settings.smtp_alert_to,
        next_run_at=status.next_run_at,
    )


def _bool_env(value: bool) -> str:
    return "true" if value else "false"


def update_automation_settings(payload: dict) -> AutomationSettingsView:
    """Atualiza .env. Senhas só mudam se enviadas não vazias."""
    updates: dict[str, str] = {}

    mapping = {
        "faz_user": "FAZ_USER",
        "mensal_schedule_enabled": "MENSAL_SCHEDULE_ENABLED",
        "mensal_schedule_day": "MENSAL_SCHEDULE_DAY",
        "mensal_schedule_hour": "MENSAL_SCHEDULE_HOUR",
        "mensal_schedule_minute": "MENSAL_SCHEDULE_MINUTE",
        "mensal_schedule_timezone": "MENSAL_SCHEDULE_TIMEZONE",
        "mensal_schedule_days": "MENSAL_SCHEDULE_DAYS",
        "mensal_schedule_force_download": "MENSAL_SCHEDULE_FORCE_DOWNLOAD",
        "mensal_schedule_retry_enabled": "MENSAL_SCHEDULE_RETRY_ENABLED",
        "mensal_schedule_max_retries": "MENSAL_SCHEDULE_MAX_RETRIES",
        "mensal_schedule_retry_hours": "MENSAL_SCHEDULE_RETRY_HOURS",
        "smtp_host": "SMTP_HOST",
        "smtp_port": "SMTP_PORT",
        "smtp_use_tls": "SMTP_USE_TLS",
        "smtp_use_ssl": "SMTP_USE_SSL",
        "smtp_use_auth": "SMTP_USE_AUTH",
        "smtp_user": "SMTP_USER",
        "smtp_timeout": "SMTP_TIMEOUT",
        "smtp_from": "SMTP_FROM",
        "smtp_to": "SMTP_TO",
        "smtp_cc": "SMTP_CC",
        "smtp_alert_to": "SMTP_ALERT_TO",
    }

    for field, env_key in mapping.items():
        if field not in payload or payload[field] is None:
            continue
        value = payload[field]
        if env_key in AUTOMATION_BOOL_KEYS:
            updates[env_key] = _bool_env(_as_bool(value))
        elif env_key in AUTOMATION_INT_KEYS:
            updates[env_key] = str(int(value))
        else:
            updates[env_key] = str(value).strip()

    faz_password = payload.get("faz_password")
    if isinstance(faz_password, str) and faz_password.strip():
        updates["FAZ_PASSWORD"] = faz_password.strip()

    smtp_password = payload.get("smtp_password")
    if isinstance(smtp_password, str) and smtp_password.strip():
        updates["SMTP_PASSWORD"] = smtp_password.strip()

    if not updates:
        return get_automation_settings()

    # Validação básica
    if "MENSAL_SCHEDULE_DAY" in updates:
        day = int(updates["MENSAL_SCHEDULE_DAY"])
        if day < 1 or day > 28:
            raise ValueError("MENSAL_SCHEDULE_DAY deve estar entre 1 e 28")
    if "MENSAL_SCHEDULE_HOUR" in updates:
        hour = int(updates["MENSAL_SCHEDULE_HOUR"])
        if hour < 0 or hour > 23:
            raise ValueError("MENSAL_SCHEDULE_HOUR deve estar entre 0 e 23")
    if "MENSAL_SCHEDULE_MINUTE" in updates:
        minute = int(updates["MENSAL_SCHEDULE_MINUTE"])
        if minute < 0 or minute > 59:
            raise ValueError("MENSAL_SCHEDULE_MINUTE deve estar entre 0 e 59")

    apply_env_updates(env_path(), updates)

    # Reinicia scheduler em background para pegar novo horário
    from forti_report.services.mensal_scheduler import (
        start_background_scheduler,
        stop_background_scheduler,
    )

    stop_background_scheduler()
    # Força releitura do .env (novo Settings)
    start_background_scheduler()

    return get_automation_settings()
