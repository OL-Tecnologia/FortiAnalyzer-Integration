"""Persistência de ClientConfig em YAML + secrets por slug."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any

import yaml

from forti_report.clients.models import ClientConfig
from forti_report.config import Settings, get_settings
from forti_report.runtime_paths import project_root

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class ClientStoreError(Exception):
    pass


def clients_dir(settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    path = settings.clients_dir
    if not path.is_absolute():
        path = project_root() / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def secrets_dir(settings: Settings | None = None) -> Path:
    path = clients_dir(settings) / ".secrets"
    path.mkdir(parents=True, exist_ok=True)
    gitignore = path / ".gitignore"
    if not gitignore.is_file():
        gitignore.write_text("*\n!.gitignore\n", encoding="utf-8")
    return path


def _client_path(slug: str, settings: Settings | None = None) -> Path:
    return clients_dir(settings) / f"{slug}.yaml"


def _secret_path(slug: str, settings: Settings | None = None) -> Path:
    return secrets_dir(settings) / f"{slug}.yaml"


def load_secret_password(slug: str, settings: Settings | None = None) -> str:
    path = _secret_path(slug, settings)
    if not path.is_file():
        return ""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return ""
    return str(data.get("faz_password") or "").strip()


def save_secret_password(slug: str, password: str, settings: Settings | None = None) -> None:
    path = _secret_path(slug, settings)
    payload = {"faz_password": password}
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def resolve_automation_password(client: ClientConfig, settings: Settings | None = None) -> str:
    if client.automation.faz_password_env:
        env_val = os.environ.get(client.automation.faz_password_env, "").strip()
        if env_val:
            return env_val
    return load_secret_password(client.slug, settings)


def automation_password_set(client: ClientConfig, settings: Settings | None = None) -> bool:
    return bool(resolve_automation_password(client, settings))


def load_client(slug: str, settings: Settings | None = None) -> ClientConfig | None:
    slug = slug.strip().lower()
    path = _client_path(slug, settings)
    if not path.is_file():
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ClientStoreError(f"YAML inválido: {path}")
    raw.setdefault("slug", slug)
    return ClientConfig.model_validate(raw)


def list_clients(settings: Settings | None = None, *, include_disabled: bool = False) -> list[ClientConfig]:
    root = clients_dir(settings)
    clients: list[ClientConfig] = []
    for path in sorted(root.glob("*.yaml")):
        if path.name.endswith(".example.yaml"):
            continue
        try:
            client = load_client(path.stem, settings)
        except Exception:
            continue
        if client is None:
            continue
        if not include_disabled and not client.enabled:
            continue
        clients.append(client)
    return clients


def get_client(slug: str, settings: Settings | None = None, *, include_disabled: bool = False) -> ClientConfig | None:
    client = load_client(slug, settings)
    if client is None:
        return None
    if not include_disabled and not client.enabled:
        return None
    return client


def require_client(slug: str, settings: Settings | None = None) -> ClientConfig:
    client = get_client(slug, settings, include_disabled=True)
    if not client:
        raise ClientStoreError(f"Cliente não encontrado: {slug}")
    return client


def save_client(
    client: ClientConfig,
    settings: Settings | None = None,
    *,
    automation_password: str | None = None,
) -> ClientConfig:
    if not _SLUG_RE.match(client.slug):
        raise ClientStoreError("slug inválido")
    path = _client_path(client.slug, settings)
    data = client.model_dump()
    # Nunca gravar senha no YAML público
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    if automation_password is not None and automation_password.strip():
        save_secret_password(client.slug, automation_password.strip(), settings)
    return client


def delete_client(slug: str, settings: Settings | None = None) -> bool:
    """Remove YAML do tenant, senha de automação e pasta de assets do cliente."""
    path = _client_path(slug, settings)
    secret = _secret_path(slug, settings)
    deleted = False
    if path.is_file():
        path.unlink()
        deleted = True
    if secret.is_file():
        secret.unlink()
        deleted = True
    # Branding do tenant (logo etc.) — não apaga output/histórico de PDFs.
    assets = project_root() / "assets" / "clients" / slug
    if assets.is_dir():
        shutil.rmtree(assets, ignore_errors=True)
        deleted = True
    return deleted


def client_from_legacy_settings(settings: Settings | None = None) -> ClientConfig:
    """Sintetiza um tenant a partir do .env global (migração / fallback)."""
    settings = settings or get_settings()
    slug = (settings.default_client_slug or settings.faz_adom or "default").strip().lower()
    slug = re.sub(r"[^a-z0-9_-]+", "_", slug) or "default"
    return ClientConfig(
        slug=slug,
        display_name=settings.faz_adom or slug,
        enabled=True,
        faz={
            "host": settings.faz_host,
            "port": settings.faz_port,
            "use_ssl": settings.faz_use_ssl,
            "verify_ssl": settings.faz_verify_ssl,
            "adom": settings.faz_adom,
            "report_schedule_mensal": settings.faz_report_schedule or "MENSAL-RELATÓRIO DE ENDPOINT",
            "report_schedule_wan": settings.faz_wan_report_schedule,
            "time_period": settings.faz_time_period,
        },
        automation={"faz_user": settings.faz_user, "faz_password_env": "FAZ_PASSWORD"},
        schedule={
            "enabled": settings.mensal_schedule_enabled,
            "day": settings.mensal_schedule_day,
            "hour": settings.mensal_schedule_hour,
            "minute": settings.mensal_schedule_minute,
            "timezone": settings.mensal_schedule_timezone,
            "days": settings.mensal_schedule_days,
            "force_download": settings.mensal_schedule_force_download,
            "retry_enabled": settings.mensal_schedule_retry_enabled,
            "max_retries": settings.mensal_schedule_max_retries,
            "retry_hours": settings.mensal_schedule_retry_hours,
        },
        email={
            "smtp_from": settings.smtp_from,
            "smtp_to": settings.smtp_to,
            "smtp_cc": settings.smtp_cc,
            "smtp_alert_to": settings.smtp_alert_to,
        },
        output={"subdir": slug},
        pdf={
            "cover_logo": str(settings.pdf_cover_logo_image),
            "cover_header": str(settings.pdf_cover_header_image),
            "cover_footer": str(settings.pdf_cover_footer_image),
            "internal_header": str(settings.pdf_internal_header_image),
            "header_logo": str(settings.pdf_header_logo_image),
            "email_subject_prefix": f"{settings.faz_adom} | Relatório Mensal FortiAnalyzer",
        },
    )


def list_clients_or_legacy(settings: Settings | None = None) -> list[ClientConfig]:
    """Lista apenas tenants YAML (cadastro via admin). Não inventa cliente a partir do .env."""
    return list_clients(settings, include_disabled=False)


def ensure_default_client_file(settings: Settings | None = None) -> ClientConfig | None:
    """Não auto-cria tenant (LGPD / multi-tenant). Clientes só via /admin.html."""
    return None
