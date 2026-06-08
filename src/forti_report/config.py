from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from forti_report.runtime_paths import assets_dir, project_root

PROJECT_ROOT = project_root()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    faz_host: str = "172.16.8.39"
    faz_port: int = 8090
    faz_use_ssl: bool = True
    faz_verify_ssl: bool = False
    faz_user: str = ""
    faz_password: str = ""
    faz_session_ttl_minutes: int = 60
    faz_session_cookie_name: str = "faz_portal_session"
    faz_session_cookie_secure: bool = False
    faz_adom: str = "CRUZ_AZUL"
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
    pdf_cover_logo_image: Path = Field(default_factory=lambda: assets_dir() / "img" / "logo_cruz-azul.png")
    pdf_internal_header_image: Path = Field(
        default_factory=lambda: assets_dir() / "img" / "cabecalho-interno.png"
    )
    pdf_header_logo_image: Path = Field(
        default_factory=lambda: assets_dir() / "img" / "logo-horizontal-gray.svg"
    )
    pdf_header_image: Path = Field(default_factory=lambda: assets_dir() / "header.png")
    pdf_footer_image: Path = Field(default_factory=lambda: assets_dir() / "footer.png")

    output_dir: Path = Field(default=PROJECT_ROOT / "output")

    @property
    def jsonrpc_url(self) -> str:
        scheme = "https" if self.faz_use_ssl else "http"
        return f"{scheme}://{self.faz_host}:{self.faz_port}/jsonrpc"


def get_settings() -> Settings:
    return Settings()
