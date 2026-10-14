"""Schemas da API web."""

from typing import Any

from pydantic import BaseModel, Field


class FazLoginRequest(BaseModel):
    user: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=1, max_length=256)
    client_slug: str | None = Field(None, max_length=64)


class AuthMeResponse(BaseModel):
    authenticated: bool
    adom: str
    user: str | None = None
    expires_at: str | None = None
    client_slug: str | None = None
    display_name: str | None = None


class AdminLoginRequest(BaseModel):
    password: str = Field(..., min_length=1, max_length=256)


class AdminMeResponse(BaseModel):
    authenticated: bool
    configured: bool
    expires_at: str | None = None


class ClientPublicResponse(BaseModel):
    slug: str
    display_name: str
    adom: str
    enabled: bool = True


class ClientConnectionTestRequest(BaseModel):
    faz_user: str | None = Field(None, max_length=128)
    faz_password: str | None = Field(None, max_length=256)
    # Permite testar payload ainda não salvo
    draft: dict[str, Any] | None = None


class ClientConnectionTestResponse(BaseModel):
    ok: bool
    detail: str
    jsonrpc_url: str | None = None
    adom: str | None = None


class ClientUpsertRequest(BaseModel):
    """Body completo ou parcial para criar/atualizar tenant."""

    slug: str | None = Field(None, max_length=64)
    display_name: str | None = Field(None, max_length=128)
    enabled: bool | None = None
    faz: dict[str, Any] | None = None
    automation: dict[str, Any] | None = None
    hierarchy: dict[str, Any] | None = None
    pdf: dict[str, Any] | None = None
    output: dict[str, Any] | None = None
    schedule: dict[str, Any] | None = None
    email: dict[str, Any] | None = None
    automation_faz_password: str | None = Field(None, max_length=256)
    require_connection_ok: bool = True


class GenerateMensalRequest(BaseModel):
    days: int = Field(60, ge=1, le=365)
    download: bool = True
    force_download: bool = False
    charts: bool = True
    reports: list[str] = Field(default_factory=lambda: ["mensal"])


class JobCreatedResponse(BaseModel):
    job_id: str
    adom: str
    stream_url: str
    download_url: str


class ClientInfoResponse(BaseModel):
    adom: str
    display_name: str
    report_schedule: str


class SchedulerStatusResponse(BaseModel):
    enabled: bool
    period: str
    next_run_at: str
    last_success_period: str
    last_success_at: str
    last_status: str
    last_error: str
    attempts: int
    running: bool
    schedule_day: int
    schedule_time: str
    timezone: str


class AutomationSettingsResponse(BaseModel):
    faz_user: str
    faz_password_set: bool
    mensal_schedule_enabled: bool
    mensal_schedule_day: int = Field(..., ge=1, le=28)
    mensal_schedule_hour: int = Field(..., ge=0, le=23)
    mensal_schedule_minute: int = Field(..., ge=0, le=59)
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
    schedules: dict[str, Any] = Field(default_factory=dict)
    next_runs: dict[str, str] = Field(default_factory=dict)


class AutomationSettingsUpdate(BaseModel):
    """Campos opcionais; senhas só atualizam se enviadas (não vazias)."""

    faz_user: str | None = Field(None, max_length=128)
    faz_password: str | None = Field(None, max_length=256)
    mensal_schedule_enabled: bool | None = None
    mensal_schedule_day: int | None = Field(None, ge=1, le=28)
    mensal_schedule_hour: int | None = Field(None, ge=0, le=23)
    mensal_schedule_minute: int | None = Field(None, ge=0, le=59)
    mensal_schedule_timezone: str | None = Field(None, max_length=64)
    mensal_schedule_days: int | None = Field(None, ge=1, le=365)
    mensal_schedule_force_download: bool | None = None
    mensal_schedule_retry_enabled: bool | None = None
    mensal_schedule_max_retries: int | None = Field(None, ge=1, le=20)
    mensal_schedule_retry_hours: int | None = Field(None, ge=1, le=168)
    smtp_host: str | None = Field(None, max_length=255)
    smtp_port: int | None = Field(None, ge=1, le=65535)
    smtp_use_tls: bool | None = None
    smtp_use_ssl: bool | None = None
    smtp_use_auth: bool | None = None
    smtp_user: str | None = Field(None, max_length=255)
    smtp_password: str | None = Field(None, max_length=256)
    smtp_timeout: int | None = Field(None, ge=10, le=300)
    smtp_from: str | None = Field(None, max_length=255)
    smtp_to: str | None = Field(None, max_length=512)
    smtp_cc: str | None = Field(None, max_length=512)
    smtp_alert_to: str | None = Field(None, max_length=512)
    schedules: dict[str, Any] | None = None
