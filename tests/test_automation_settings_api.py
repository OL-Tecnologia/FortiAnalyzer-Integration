"""Testes da API de configuração de automação (painel)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from forti_report.api.app import app
from forti_report.services.automation_settings import update_automation_settings

client = TestClient(app)


def _login():
    with patch("forti_report.faz.auth.FortiAnalyzerClient") as mock_cls:
        mock_client = MagicMock()
        mock_client.login.return_value = "rpc"
        mock_cls.return_value.__enter__.return_value = mock_client
        return client.post(
            "/api/auth/faz/login",
            json={"user": "operator", "password": "secret"},
        )


def test_get_automation_requires_auth():
    res = client.get("/api/settings/automation")
    assert res.status_code == 401


def test_get_and_put_automation_settings(tmp_path: Path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        "FAZ_USER=svc\nFAZ_PASSWORD=oldpass\n"
        "MENSAL_SCHEDULE_ENABLED=true\nMENSAL_SCHEDULE_DAY=5\n"
        "MENSAL_SCHEDULE_HOUR=6\nMENSAL_SCHEDULE_MINUTE=0\n"
        "SMTP_TO=cliente@test.com\nSMTP_PASSWORD=mailpass\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "forti_report.services.automation_settings.env_path",
        lambda: env,
    )
    monkeypatch.setattr(
        "forti_report.services.mensal_scheduler.stop_background_scheduler",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "forti_report.services.mensal_scheduler.start_background_scheduler",
        lambda: None,
    )

    login = _login()
    assert login.status_code == 200

    with patch("forti_report.services.automation_settings.get_settings") as mock_gs:
        from forti_report.config import Settings

        mock_gs.return_value = Settings(
            faz_user="svc",
            faz_password="oldpass",
            mensal_schedule_enabled=True,
            mensal_schedule_day=5,
            mensal_schedule_hour=6,
            mensal_schedule_minute=0,
            smtp_to="cliente@test.com",
            smtp_password="mailpass",
        )
        get_res = client.get("/api/settings/automation")

    assert get_res.status_code == 200
    data = get_res.json()
    assert data["faz_user"] == "svc"
    assert data["faz_password_set"] is True
    assert "faz_password" not in data
    assert data["smtp_to"] == "cliente@test.com"

    put_res = client.put(
        "/api/settings/automation",
        json={
            "mensal_schedule_day": 7,
            "smtp_to": "novo@cliente.com",
            "faz_password": "",
        },
    )
    assert put_res.status_code == 200
    text = env.read_text(encoding="utf-8")
    assert "MENSAL_SCHEDULE_DAY=7" in text
    assert "SMTP_TO=novo@cliente.com" in text
    assert "FAZ_PASSWORD=oldpass" in text


def test_update_skips_empty_password(tmp_path: Path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("FAZ_PASSWORD=keep\nSMTP_PASSWORD=keep2\n", encoding="utf-8")
    monkeypatch.setattr(
        "forti_report.services.automation_settings.env_path",
        lambda: env,
    )
    monkeypatch.setattr(
        "forti_report.services.mensal_scheduler.stop_background_scheduler",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "forti_report.services.mensal_scheduler.start_background_scheduler",
        lambda: None,
    )
    update_automation_settings({"faz_password": "", "smtp_to": "a@b.com"})
    text = env.read_text(encoding="utf-8")
    assert "FAZ_PASSWORD=keep" in text
    assert "SMTP_TO=a@b.com" in text
