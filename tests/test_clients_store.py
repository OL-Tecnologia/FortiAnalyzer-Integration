"""Testes do catálogo multi-tenant."""

from __future__ import annotations

from pathlib import Path

from forti_report.clients.bridge import settings_from_client
from forti_report.clients.models import ClientConfig
from forti_report.clients.store import (
    delete_client,
    list_clients,
    load_secret_password,
    save_client,
    save_secret_password,
)
from forti_report.config import Settings


def test_save_and_list_client(tmp_path: Path, monkeypatch):
    settings = Settings(
        clients_dir=tmp_path / "clients",
        output_dir=tmp_path / "output",
    )
    client = ClientConfig(
        slug="sde",
        display_name="SDE",
        faz={"host": "10.1.2.3", "port": 8090, "adom": "SDE"},
        automation={"faz_user": "svc"},
        schedule={"enabled": True, "day": 5},
        email={"smtp_to": "a@b.com"},
        output={"subdir": "sde"},
    )
    save_client(client, settings, automation_password="segredo")
    loaded = list_clients(settings)
    assert len(loaded) == 1
    assert loaded[0].faz.host == "10.1.2.3"
    assert load_secret_password("sde", settings) == "segredo"

    tenant = settings_from_client(client, settings, use_automation_credentials=True)
    assert tenant.faz_host == "10.1.2.3"
    assert tenant.faz_adom == "SDE"
    assert tenant.faz_password == "segredo"
    assert tenant.output_dir == tmp_path / "output" / "sde"
    assert "sde" in str(tenant.faz_mensal_cache_dir)


def test_secret_sidecar(tmp_path: Path):
    settings = Settings(clients_dir=tmp_path / "clients")
    save_secret_password("demo", "abc123", settings)
    assert load_secret_password("demo", settings) == "abc123"


def test_delete_client(tmp_path: Path, monkeypatch):
    clients = tmp_path / "clients"
    settings = Settings(clients_dir=clients, output_dir=tmp_path / "output")
    client = ClientConfig(
        slug="tmp_faz",
        display_name="Tmp FAZ",
        faz={"host": "10.0.0.1", "adom": "TMP"},
    )
    save_client(client, settings, automation_password="x")
    assert (clients / "tmp_faz.yaml").is_file()
    assert delete_client("tmp_faz", settings) is True
    assert not (clients / "tmp_faz.yaml").is_file()
    assert load_secret_password("tmp_faz", settings) == ""
    assert delete_client("tmp_faz", settings) is False
