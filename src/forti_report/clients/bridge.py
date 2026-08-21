"""Converte ClientConfig → Settings do motor V1."""

from __future__ import annotations

from pathlib import Path

from forti_report.clients.models import ClientConfig
from forti_report.clients.store import resolve_automation_password
from forti_report.config import Settings, get_settings
from forti_report.faz.endpoint import parse_faz_endpoint
from forti_report.runtime_paths import project_root


def _resolve_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return project_root() / path


def settings_from_client(
    client: ClientConfig,
    base: Settings | None = None,
    *,
    use_automation_credentials: bool = False,
    faz_user: str | None = None,
    faz_password: str | None = None,
) -> Settings:
    """Monta Settings isolados para o tenant (paths, FAZ, agenda, e-mail)."""
    base = base or get_settings()
    subdir = client.output_subdir()
    out_root = base.output_dir if base.output_dir.is_absolute() else project_root() / base.output_dir
    # Se output_dir já for output/, aninha por slug; evita output/output/slug
    tenant_out = out_root / subdir

    auto_user = client.automation.faz_user or base.faz_user
    auto_pass = resolve_automation_password(client, base)

    user = faz_user if faz_user is not None else (auto_user if use_automation_credentials else base.faz_user)
    password = (
        faz_password
        if faz_password is not None
        else (auto_pass if use_automation_credentials else base.faz_password)
    )

    faz_host, faz_port_from_url, faz_ssl_from_url = parse_faz_endpoint(client.faz.host)
    faz_host = faz_host or client.faz.host
    faz_port = faz_port_from_url if faz_port_from_url is not None else client.faz.port
    faz_use_ssl = faz_ssl_from_url if faz_ssl_from_url is not None else client.faz.use_ssl

    updates: dict = {
        "client_slug": client.slug,
        "client_display_name": client.display_name,
        "cover_title": client.pdf.cover_title or "RELATÓRIO MENSAL  GERAL",
        "faz_host": faz_host,
        "faz_port": faz_port,
        "faz_use_ssl": faz_use_ssl,
        "faz_verify_ssl": client.faz.verify_ssl,
        "faz_adom": client.faz.adom,
        "faz_report_schedule": client.faz.report_schedule_mensal,
        "faz_wan_report_schedule": client.faz.report_schedule_wan,
        "faz_time_period": client.faz.time_period,
        "faz_user": user,
        "faz_password": password,
        "output_dir": tenant_out,
        "faz_mensal_cache_dir": tenant_out / "faz_mensal",
        "pdf_chart_cache_dir": tenant_out / "chart_cache",
        "mensal_schedule_state_dir": tenant_out / "scheduler",
        "pdf_cover_logo_image": (
            _resolve_path(client.pdf.cover_logo)
            if client.pdf.cover_logo.strip()
            else base.pdf_cover_logo_image
        ),
        "pdf_cover_logo_width_cm": client.pdf.cover_logo_width_cm,
        "pdf_cover_logo_align": client.pdf.cover_logo_align,
        "pdf_cover_logo_offset_x_cm": client.pdf.cover_logo_offset_x_cm,
        "pdf_cover_logo_offset_y_cm": client.pdf.cover_logo_offset_y_cm,
        # Faixas OL da capa — sempre o padrão global (não variam por tenant)
        "pdf_cover_header_image": base.pdf_cover_header_image,
        "pdf_cover_footer_image": base.pdf_cover_footer_image,
        "pdf_internal_header_image": (
            _resolve_path(client.pdf.internal_header)
            if client.pdf.internal_header.strip()
            else base.pdf_internal_header_image
        ),
        "pdf_header_logo_image": (
            _resolve_path(client.pdf.header_logo)
            if client.pdf.header_logo.strip()
            else base.pdf_header_logo_image
        ),
        "email_subject_prefix": client.pdf.email_subject_prefix,
        "device_pattern": client.hierarchy.device_pattern,
        "region_labels": dict(client.hierarchy.region_labels),
        "mensal_schedule_enabled": client.schedule.enabled,
        "mensal_schedule_day": client.schedule.day,
        "mensal_schedule_hour": client.schedule.hour,
        "mensal_schedule_minute": client.schedule.minute,
        "mensal_schedule_timezone": client.schedule.timezone,
        "mensal_schedule_days": client.schedule.days,
        "mensal_schedule_force_download": client.schedule.force_download,
        "mensal_schedule_retry_enabled": client.schedule.retry_enabled,
        "mensal_schedule_max_retries": client.schedule.max_retries,
        "mensal_schedule_retry_hours": client.schedule.retry_hours,
    }
    if client.email.smtp_from:
        updates["smtp_from"] = client.email.smtp_from
    if client.email.smtp_to:
        updates["smtp_to"] = client.email.smtp_to
    if client.email.smtp_cc is not None:
        updates["smtp_cc"] = client.email.smtp_cc
    if client.email.smtp_alert_to:
        updates["smtp_alert_to"] = client.email.smtp_alert_to

    return base.model_copy(update=updates)
