"""Testes da API — autenticação e proteção de rotas."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from forti_report.api.app import app
from forti_report.faz.auth import FazPortalSession

client = TestClient(app)


def test_generate_without_session_returns_401():
    res = client.post(
        "/api/reports/mensal/generate",
        json={"days": 60, "download": False, "charts": False},
    )
    assert res.status_code == 401


def test_auth_me_unauthenticated():
    res = client.get("/api/auth/me")
    assert res.status_code == 200
    data = res.json()
    assert data["authenticated"] is False


@patch("forti_report.api.app.authenticate_faz")
def test_login_sets_cookie(mock_auth):
    mock_auth.return_value = FazPortalSession(
        session_id="test-session-id",
        faz_user="operator",
        faz_password="secret",
        faz_rpc_session="rpc",
        adom="CRUZ_AZUL",
        expires_at=__import__("time").time() + 3600,
    )
    res = client.post(
        "/api/auth/faz/login",
        json={"user": "operator", "password": "secret"},
    )
    assert res.status_code == 200
    assert res.json()["authenticated"] is True
    assert "faz_portal_session" in res.cookies


@patch("forti_report.faz.auth.FortiAnalyzerClient")
@patch("forti_report.api.app.start_mensal_job")
def test_generate_with_session(mock_start, mock_client_cls):
    mock_client = MagicMock()
    mock_client.login.return_value = "rpc"
    mock_client_cls.return_value.__enter__.return_value = mock_client

    login = client.post(
        "/api/auth/faz/login",
        json={"user": "operator", "password": "secret"},
    )
    assert login.status_code == 200

    from forti_report.services.job_store import JobRecord

    mock_start.return_value = JobRecord(
        job_id="job123",
        adom="CRUZ_AZUL",
        portal_session_id=login.cookies.get("faz_portal_session", ""),
    )
    res = client.post(
        "/api/reports/mensal/generate",
        json={"days": 60},
    )
    assert res.status_code == 200
    assert res.json()["job_id"] == "job123"
