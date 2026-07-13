"""Testes de leitura/gravação do .env."""

from __future__ import annotations

from pathlib import Path

from forti_report.services.env_file import apply_env_updates, parse_env_values, read_env_file


def test_parse_env_values_ignores_comments():
    text = "# comment\nFOO=bar\n\nBAZ=1\n"
    assert parse_env_values(text) == {"FOO": "bar", "BAZ": "1"}


def test_apply_env_updates_preserves_comments_and_order(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text(
        "# header\nFAZ_USER=old\nMENSAL_SCHEDULE_DAY=1\n",
        encoding="utf-8",
    )
    apply_env_updates(env, {"FAZ_USER": "new", "SMTP_HOST": "mail.test"})
    text = env.read_text(encoding="utf-8")
    assert "# header" in text
    assert "FAZ_USER=new" in text
    assert "MENSAL_SCHEDULE_DAY=1" in text
    assert "SMTP_HOST=mail.test" in text


def test_read_env_file_missing(tmp_path: Path):
    assert read_env_file(tmp_path / "missing.env") == {}
