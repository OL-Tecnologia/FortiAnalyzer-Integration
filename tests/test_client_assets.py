"""Upload de assets por tenant."""

from __future__ import annotations

from pathlib import Path

from forti_report.clients.assets import save_client_asset
from forti_report.clients.models import ClientConfig
from forti_report.clients.store import get_client, save_client
from forti_report.config import Settings


def test_save_client_asset_updates_yaml(tmp_path: Path, monkeypatch):
    root = tmp_path
    monkeypatch.setattr("forti_report.clients.assets.project_root", lambda: root)

    settings = Settings(clients_dir=root / "configs" / "clients", output_dir=root / "output")
    save_client(
        ClientConfig(slug="sde", display_name="SDE", faz={"adom": "SDE", "host": "1.1.1.1"}),
        settings,
    )
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    result = save_client_asset(
        "sde",
        "cover_logo",
        filename="logo-cliente.png",
        content=png,
        settings=settings,
    )
    assert result["path"] == "assets/clients/sde/logo.png"
    assert (root / "assets" / "clients" / "sde" / "logo.png").is_file()
    client = get_client("sde", settings, include_disabled=True)
    assert client is not None
    assert client.pdf.cover_logo == "assets/clients/sde/logo.png"
