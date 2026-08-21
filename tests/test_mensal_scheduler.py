"""Testes do agendamento mensal."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from forti_report.config import Settings
from forti_report.services.email_delivery import format_email_subject
from forti_report.services.mensal_scheduler import (
    SchedulerState,
    compute_next_run,
    is_due_now,
    load_scheduler_state,
    run_scheduled_mensal,
    save_scheduler_state,
    scheduled_datetime_for_period,
)


def _settings(tmp_path: Path, **overrides) -> Settings:
    base = {
        "faz_user": "svc",
        "faz_password": "secret",
        "output_dir": tmp_path / "output",
        "mensal_schedule_state_dir": tmp_path / "output" / "scheduler",
        "mensal_schedule_enabled": True,
        "mensal_schedule_day": 5,
        "mensal_schedule_hour": 6,
        "mensal_schedule_minute": 0,
        "mensal_schedule_timezone": "America/Sao_Paulo",
        "mensal_schedule_max_retries": 3,
        "mensal_schedule_retry_hours": 2,
        "smtp_host": "smtp.test",
        "smtp_from": "from@test",
        "smtp_to": "to@test",
        "smtp_alert_to": "alert@test",
    }
    base.update(overrides)
    return Settings(**base)


def test_format_email_subject():
    when = datetime(2026, 7, 5, 6, 0)
    assert format_email_subject(when) == "Relatório Mensal FortiAnalyzer – 07/2026"


def test_compute_next_run_same_month_before_due():
    settings = _settings(Path("/tmp"))
    ref = datetime(2026, 7, 4, 10, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
    nxt = compute_next_run(settings, reference=ref)
    assert nxt == datetime(2026, 7, 5, 6, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))


def test_compute_next_run_after_due_goes_to_next_month():
    settings = _settings(Path("/tmp"))
    ref = datetime(2026, 7, 5, 7, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
    nxt = compute_next_run(settings, reference=ref)
    assert nxt == datetime(2026, 8, 5, 6, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))


def test_scheduled_datetime_for_period():
    settings = _settings(Path("/tmp"))
    due = scheduled_datetime_for_period("2026-02", settings)
    assert due == datetime(2026, 2, 5, 6, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))


def test_is_due_now():
    settings = _settings(Path("/tmp"))
    before = datetime(2026, 7, 5, 5, 59, tzinfo=ZoneInfo("America/Sao_Paulo"))
    after = datetime(2026, 7, 5, 6, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
    assert is_due_now(settings, reference=before) is False
    assert is_due_now(settings, reference=after) is True


def test_idempotency_skips_success(tmp_path: Path):
    settings = _settings(tmp_path)
    save_scheduler_state(
        settings,
        SchedulerState(
            period="2026-07",
            status="success",
            executed_at="2026-07-05T06:10:00-03:00",
            attempts=1,
        ),
    )
    ref = datetime(2026, 7, 5, 7, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))
    with patch("forti_report.services.mensal_scheduler.now_in_tz", return_value=ref):
        with patch("forti_report.services.mensal_scheduler.period_key", return_value="2026-07"):
            result = run_scheduled_mensal(settings)
    assert result.status == "skipped"
    assert "já enviado" in result.message.lower()


def test_run_scheduled_mensal_success(tmp_path: Path):
    settings = _settings(tmp_path)
    pdf_path = tmp_path / "output" / "MENSAL_UNIFICADO_CRUZ_AZUL.pdf"
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(b"%PDF-1.4 test")

    ref = datetime(2026, 7, 5, 6, 30, tzinfo=ZoneInfo("America/Sao_Paulo"))

    with patch("forti_report.services.mensal_scheduler.now_in_tz", return_value=ref):
        with patch("forti_report.services.mensal_scheduler.period_key", return_value="2026-07"):
            with patch(
                "forti_report.services.mensal_scheduler.MensalReportPipeline.generate_unified_pdf",
                return_value=pdf_path,
            ):
                with patch("forti_report.services.mensal_scheduler.send_mensal_report_email") as send_mail:
                    result = run_scheduled_mensal(settings, force=True)

    assert result.status == "success"
    send_mail.assert_called_once()

    state = load_scheduler_state(settings)
    assert state.status == "success"
    assert state.period == "2026-07"


def test_scheduler_state_roundtrip(tmp_path: Path):
    settings = _settings(tmp_path)
    state = SchedulerState(period="2026-07", status="failed", attempts=2, error="boom")
    save_scheduler_state(settings, state)
    loaded = load_scheduler_state(settings)
    assert loaded.period == "2026-07"
    assert loaded.attempts == 2
    assert loaded.error == "boom"
    raw = json.loads((settings.mensal_schedule_state_dir / "scheduler_state.json").read_text())
    assert raw["status"] == "failed"
