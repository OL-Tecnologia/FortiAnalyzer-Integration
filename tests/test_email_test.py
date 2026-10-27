"""Teste de envio de e-mail: diagnóstico e API."""

from __future__ import annotations

import smtplib
import time
from pathlib import Path

from fastapi.testclient import TestClient

from forti_report.api.app import app
from forti_report.api.deps import require_admin_session, require_faz_session
from forti_report.admin.auth import AdminSession
from forti_report.config import Settings
from forti_report.faz.auth import FazPortalSession
from forti_report.services.email_delivery import send_test_message

client = TestClient(app)


def _settings(**kwargs) -> Settings:
    base = dict(
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        smtp_use_tls=True,
        smtp_use_ssl=False,
        smtp_use_auth=True,
        smtp_user="operador@exemplo.com",
        smtp_password="app-password",
        smtp_from="operador@exemplo.com",
        smtp_to="cliente@empresa.com",
    )
    base.update(kwargs)
    return Settings(**base)


def _session() -> FazPortalSession:
    return FazPortalSession(
        session_id="s",
        faz_user="op",
        faz_password="x",
        faz_rpc_session="rpc",
        adom="root",
        expires_at=time.time() + 3600,
    )


def test_missing_recipient_explains_how_to_fix(tmp_path: Path):
    result = send_test_message(
        _settings(smtp_to=""),
        env_path=tmp_path / ".env",
    )
    assert result.ok is False
    assert "destinatário" in result.problem.lower()
    assert "Destinatário (To)" in result.fix


def test_gmail_rejects_password_with_app_password_instructions(tmp_path: Path, monkeypatch):
    def _boom(*_args, **_kwargs):
        raise smtplib.SMTPAuthenticationError(535, b"Username and Password not accepted")

    monkeypatch.setattr("forti_report.services.email_delivery.send_email", _boom)
    result = send_test_message(_settings(), env_path=tmp_path / ".env")
    assert result.ok is False
    assert "Gmail recusou" in result.problem
    assert "senha de app" in result.fix


def test_sender_must_match_login_on_gmail(tmp_path: Path):
    result = send_test_message(
        _settings(smtp_from="outro@empresa.com"),
        env_path=tmp_path / ".env",
    )
    assert result.ok is False
    assert "remetente" in result.problem.lower()
    assert "operador@exemplo.com" in result.fix


def test_password_edge_space_in_env(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text("SMTP_PASSWORD= segredo\n", encoding="utf-8")
    result = send_test_message(_settings(), env_path=env)
    assert result.ok is False
    assert "espaço" in result.problem
    assert "SMTP_PASSWORD" in result.fix


def test_success_message_names_the_recipient(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("forti_report.services.email_delivery.send_email", lambda *a, **k: None)
    result = send_test_message(_settings(), env_path=tmp_path / ".env")
    assert result.ok is True
    assert "cliente@empresa.com" in result.message
    assert result.problem == ""


def test_email_test_requires_login():
    res = client.post(
        "/api/settings/email-test",
        json={"smtp_from": "operador@exemplo.com", "smtp_to": "cliente@empresa.com"},
    )
    assert res.status_code == 401


def test_email_test_api_returns_problem_and_fix(monkeypatch):
    monkeypatch.setattr("forti_report.api.app.get_settings", lambda: _settings(smtp_to=""))
    app.dependency_overrides[require_faz_session] = _session
    try:
        res = client.post(
            "/api/settings/email-test",
            json={"smtp_from": "operador@exemplo.com", "smtp_to": ""},
        )
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is False
    assert data["problem"]
    assert data["fix"]


def test_admin_email_test_requires_login():
    res = client.post("/api/admin/email-test", json={"smtp_to": "cliente@empresa.com"})
    assert res.status_code == 401


def test_admin_email_test_uses_form_addresses(monkeypatch):
    monkeypatch.setattr("forti_report.services.email_delivery.send_email", lambda *a, **k: None)
    monkeypatch.setattr(
        "forti_report.services.email_delivery._password_has_edge_space",
        lambda _path: False,
    )
    monkeypatch.setattr(
        "forti_report.api.app.get_settings",
        lambda: _settings(smtp_from="", smtp_to=""),
    )
    app.dependency_overrides[require_admin_session] = lambda: AdminSession(
        session_id="admin",
        expires_at=time.time() + 3600,
    )
    try:
        res = client.post(
            "/api/admin/email-test",
            json={"smtp_from": "operador@exemplo.com", "smtp_to": "cliente@empresa.com"},
        )
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 200
    assert res.json()["ok"] is True
