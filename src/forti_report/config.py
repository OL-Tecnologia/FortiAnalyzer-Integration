from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from forti_report.runtime_paths import assets_dir, project_root

PROJECT_ROOT = project_root()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Super Admin do portal (multi-tenant) ---
    # Defina no .env: PORTAL_ADMIN_PASSWORD=sua_senha_forte
    portal_admin_password: str = ""
    portal_admin_cookie_name: str = "portal_admin_session"
    portal_admin_session_ttl_minutes: int = 60

    @field_validator("portal_admin_password", mode="before")
    @classmethod
    def _strip_admin_password(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().strip('"').strip("'")
        return value
    clients_dir: Path = Field(default=PROJECT_ROOT / "configs" / "clients")
    default_client_slug: str = ""

    # Tenant ativo (preenchido via settings_from_client)
    client_slug: str = ""
    client_display_name: str = ""
    cover_title: str = "RELATÓRIO MENSAL  GERAL"
    device_pattern: str = ""
    region_labels: dict[str, str] = Field(default_factory=dict)
    email_subject_prefix: str = ""

    faz_host: str = ""
    faz_port: int = 8090
    faz_use_ssl: bool = True
    faz_verify_ssl: bool = False
    faz_user: str = ""
    faz_password: str = ""
    faz_session_ttl_minutes: int = 60
    faz_session_cookie_name: str = "faz_portal_session"
    faz_session_cookie_secure: bool = False
    faz_adom: str = ""
    faz_report_schedule: str = ""
    faz_wan_report_schedule: str = "SEMANAL- RELATÓRIO TRÁFEGO WAN"
    faz_time_period: str = "last-30-days"
    wan_reference_pdf: Path = Field(
        default=PROJECT_ROOT / "tests" / "SEMANAL- RELATÓRIO TRÁFEGO WAN-2026-05-29-0801-0300_333.pdf"
    )
    faz_mensal_cache_dir: Path = Field(default=PROJECT_ROOT / "output" / "faz_mensal")
    faz_prefer_cache: bool = True  # reutiliza JSON só se .meta.json bater com relatório atual no FAZ
    pdf_mensal_charts: bool = True
    pdf_chart_cache_dir: Path = Field(default=PROJECT_ROOT / "output" / "chart_cache")
    pdf_chart_width: int = 720

    pdf_assets_dir: Path = Field(default_factory=assets_dir)
    pdf_cover_image: Path = Field(default_factory=lambda: assets_dir() / "cover.png")
    pdf_cover_header_image: Path = Field(default_factory=lambda: assets_dir() / "img" / "cabecalho_capa.png")
    pdf_cover_footer_image: Path = Field(default_factory=lambda: assets_dir() / "img" / "rodape_capa.png")
    # Logo do cliente vem do tenant (admin); padrão vazio evita embutir cliente na dist
    pdf_cover_logo_image: Path = Field(default_factory=lambda: assets_dir() / "img" / "logo_cliente.png")
    pdf_cover_logo_width_cm: float = 2.1
    pdf_cover_logo_align: str = "right"  # left | center | right
    pdf_cover_logo_offset_x_cm: float = 0.0
    pdf_cover_logo_offset_y_cm: float = 0.35
    pdf_internal_header_image: Path = Field(
        default_factory=lambda: assets_dir() / "img" / "cabecalho-interno.png"
    )
    pdf_header_logo_image: Path = Field(
        default_factory=lambda: assets_dir() / "img" / "logo-horizontal-gray.svg"
    )
    pdf_header_image: Path = Field(default_factory=lambda: assets_dir() / "header.png")
    pdf_footer_image: Path = Field(default_factory=lambda: assets_dir() / "footer.png")

    output_dir: Path = Field(default=PROJECT_ROOT / "output")

    # Agendamento mensal + e-mail
    mensal_schedule_enabled: bool = False
    mensal_schedule_day: int = 5
    mensal_schedule_hour: int = 6
    mensal_schedule_minute: int = 0
    mensal_schedule_timezone: str = "America/Sao_Paulo"
    mensal_schedule_days: int = 60
    mensal_schedule_force_download: bool = True
    mensal_schedule_retry_enabled: bool = True
    mensal_schedule_max_retries: int = 3
    mensal_schedule_retry_hours: int = 2
    mensal_schedule_state_dir: Path = Field(default=PROJECT_ROOT / "output" / "scheduler")

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    smtp_use_auth: bool = True
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_timeout: int = 60
    smtp_from: str = ""
    smtp_to: str = ""
    smtp_cc: str = ""
    smtp_alert_to: str = ""

    @property
    def jsonrpc_url(self) -> str:
        from forti_report.faz.endpoint import parse_faz_endpoint

        host, port_from_host, ssl_from_host = parse_faz_endpoint(self.faz_host)
        host = host or (self.faz_host or "").strip()
        port = port_from_host if port_from_host is not None else self.faz_port
        use_ssl = ssl_from_host if ssl_from_host is not None else self.faz_use_ssl
        scheme = "https" if use_ssl else "http"
        return f"{scheme}://{host}:{port}/jsonrpc"


def get_settings() -> Settings:
    return Settings()
