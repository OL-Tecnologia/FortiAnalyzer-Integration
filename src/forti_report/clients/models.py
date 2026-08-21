"""Modelo de configuração por cliente (tenant)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from forti_report.faz.endpoint import parse_faz_endpoint


class FazClientConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = Field(8090, ge=1, le=65535)
    use_ssl: bool = True
    verify_ssl: bool = False
    adom: str = ""
    report_schedule_mensal: str = "MENSAL- RELATÓRIO GERAL"
    report_schedule_wan: str = ""
    time_period: str = "last-30-days"

    @model_validator(mode="before")
    @classmethod
    def _normalize_endpoint(cls, data: Any) -> Any:
        """Permite colar URL completa; grava só host (+ porta/SSL se vierem na URL)."""
        if not isinstance(data, dict):
            return data
        raw = data.get("host")
        if raw is None:
            return data
        host, port, use_ssl = parse_faz_endpoint(str(raw))
        if host:
            data["host"] = host
        if port is not None:
            data["port"] = port
        if use_ssl is not None:
            data["use_ssl"] = use_ssl
        return data


class AutomationClientConfig(BaseModel):
    faz_user: str = ""
    # Senha resolvida de: faz_password (secrets file) ou faz_password_env
    faz_password_env: str = ""


class HierarchyClientConfig(BaseModel):
    # Padrão genérico — cada tenant deve ajustar ao naming do próprio FAZ
    device_pattern: str = (
        r"^(?:(?P<prefix>hafw\d+)|fw)-(?P<region>[a-z0-9]+)-(?P<site>.+)$"
    )
    region_labels: dict[str, str] = Field(default_factory=dict)


class PdfClientConfig(BaseModel):
    # Capa completa: faixas OL (compartilhadas) + logo do cliente
    cover_logo: str = ""
    cover_logo_width_cm: float = Field(2.1, ge=0.5, le=10.0)
    cover_logo_align: Literal["left", "center", "right"] = "right"
    # offset_x: positivo = direita; offset_y: positivo = sobe (afasta da faixa inferior)
    cover_logo_offset_x_cm: float = Field(0.0, ge=-5.0, le=5.0)
    cover_logo_offset_y_cm: float = Field(0.35, ge=0.0, le=8.0)
    cover_header: str = "assets/img/cabecalho_capa.png"
    cover_footer: str = "assets/img/rodape_capa.png"
    # Páginas internas (corpo do PDF) — rodapé tipográfico em internal_page.py
    internal_header: str = "assets/img/cabecalho-interno.png"
    header_logo: str = "assets/img/logo-horizontal-gray.svg"
    cover_title: str = "RELATÓRIO MENSAL GERAL"
    email_subject_prefix: str = "Relatório Mensal FortiAnalyzer"


class OutputClientConfig(BaseModel):
    subdir: str = ""


class ScheduleClientConfig(BaseModel):
    enabled: bool = False
    day: int = Field(5, ge=1, le=28)
    hour: int = Field(6, ge=0, le=23)
    minute: int = Field(0, ge=0, le=59)
    timezone: str = "America/Sao_Paulo"
    days: int = Field(60, ge=1, le=365)
    force_download: bool = True
    retry_enabled: bool = True
    max_retries: int = Field(3, ge=1, le=20)
    retry_hours: int = Field(2, ge=1, le=168)


class EmailClientConfig(BaseModel):
    smtp_from: str = ""
    smtp_to: str = ""
    smtp_cc: str = ""
    smtp_alert_to: str = ""


class ClientConfig(BaseModel):
    slug: str
    display_name: str
    enabled: bool = True
    faz: FazClientConfig = Field(default_factory=FazClientConfig)
    automation: AutomationClientConfig = Field(default_factory=AutomationClientConfig)
    hierarchy: HierarchyClientConfig = Field(default_factory=HierarchyClientConfig)
    pdf: PdfClientConfig = Field(default_factory=PdfClientConfig)
    output: OutputClientConfig = Field(default_factory=OutputClientConfig)
    schedule: ScheduleClientConfig = Field(default_factory=ScheduleClientConfig)
    email: EmailClientConfig = Field(default_factory=EmailClientConfig)

    @field_validator("slug")
    @classmethod
    def _slug_ok(cls, value: str) -> str:
        cleaned = value.strip().lower().replace(" ", "_")
        if not cleaned or not all(c.isalnum() or c in "-_" for c in cleaned):
            raise ValueError("slug inválido (use letras, números, - ou _)")
        return cleaned

    def output_subdir(self) -> str:
        return (self.output.subdir or self.slug).strip().strip("/\\")

    def public_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "display_name": self.display_name,
            "adom": self.faz.adom,
            "enabled": self.enabled,
        }

    def admin_dict(self, *, automation_password_set: bool) -> dict[str, Any]:
        data = self.model_dump()
        data["automation_password_set"] = automation_password_set
        data["automation"] = {
            "faz_user": self.automation.faz_user,
            "faz_password_env": self.automation.faz_password_env,
            "faz_password_set": automation_password_set,
        }
        return data
