"""Testes Super Admin + login com client_slug."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from forti_report.admin.auth import authenticate_admin, get_admin_store
from forti_report.api.app import app
from forti_report.clients.models import ClientConfig
from forti_report.clients.store import save_client
from forti_report.config import Settings
from forti_report.faz.auth import FazPortalSession


client = TestClient(app)


def test_admin_login_requires_env_password(monkeypatch):
    monkeypatch.setenv("PORTAL_ADMIN_PASSWORD", "")
    # Settings caches from env file; force empty via patch
    with patch("forti_report.admin.auth.get_settings") as gs:
        gs.return_value = Settings(portal_admin_password="")
        res = client.post("/api/admin/login", json={"password": "x"})
        assert res.status_code == 401


def test_admin_login_ok(monkeypatch):
    with patch("forti_report.admin.auth.get_settings") as gs:
        gs.return_value = Settings(portal_admin_password="super-secret")
        get_admin_store().invalidate(None)
        res = client.post("/api/admin/login", json={"password": "super-secret"})
        assert res.status_code == 200
        assert res.json()["authenticated"] is True
        assert "portal_admin_session" in res.cookies


def test_admin_login_wrong_length_is_401_not_500():
    """hmac.compare_digest quebrava com senhas de tamanho diferente (500)."""
    with patch("forti_report.admin.auth.get_settings") as gs:
        gs.return_value = Settings(portal_admin_password="super-secret")
        res = client.post("/api/admin/login", json={"password": "x"})
        assert res.status_code == 401
        assert res.json()["detail"] == "Senha inválida"


def test_faz_login_with_client_slug(tmp_path: Path):
    settings = Settings(
        clients_dir=tmp_path / "clients",
        output_dir=tmp_path / "output",
        faz_session_ttl_minutes=60,
    )
    save_client(
        ClientConfig(
            slug="sde",
            display_name="SDE",
            faz={"host": "127.0.0.1", "port": 8090, "adom": "SDE"},
        ),
        settings,
    )

    fake = FazPortalSession(
        session_id="sid",
        faz_user="op",
        faz_password="pw",
        faz_rpc_session="rpc",
        adom="SDE",
        expires_at=9_999_999_999,
        client_slug="sde",
    )

    with (
        patch("forti_report.api.app.list_clients_or_legacy") as lc,
        patch("forti_report.api.app.get_client") as gc,
        patch("forti_report.api.app.settings_from_client") as sfc,
        patch("forti_report.api.app.authenticate_faz") as auth,
    ):
        cfg = ClientConfig(slug="sde", display_name="SDE", faz={"adom": "SDE", "host": "1.1.1.1"})
        lc.return_value = [cfg]
        gc.return_value = cfg
        sfc.return_value = settings
        auth.return_value = fake
        res = client.post(
            "/api/auth/faz/login",
            json={"user": "op", "password": "pw", "client_slug": "sde"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["authenticated"] is True
    assert body["client_slug"] == "sde"
    assert body["display_name"] == "SDE"
