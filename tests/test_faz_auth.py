"""Testes do store de sessão FAZ (portal web)."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from forti_report.faz.auth import FazSessionStore, authenticate_faz, settings_for_session


def test_session_store_expires():
    store = FazSessionStore()
    rec = store.create(
        faz_user="u",
        faz_password="p",
        faz_rpc_session="rpc-1",
        adom="CRUZ_AZUL",
        ttl_seconds=1,
    )
    assert store.get(rec.session_id) is not None
    time.sleep(1.05)
    assert store.get(rec.session_id) is None


def test_settings_for_session_injects_credentials():
    store = FazSessionStore()
    rec = store.create(
        faz_user="operator",
        faz_password="secret",
        faz_rpc_session="rpc-1",
        adom="CRUZ_AZUL",
        ttl_seconds=3600,
    )
    from forti_report.config import get_settings

    base = get_settings()
    merged = settings_for_session(rec, base)
    assert merged.faz_user == "operator"
    assert merged.faz_password == "secret"
    assert merged.faz_adom == base.faz_adom


@patch("forti_report.faz.auth.FortiAnalyzerClient")
def test_authenticate_faz_success(mock_client_cls):
    mock_client = MagicMock()
    mock_client.login.return_value = "faz-session-abc"
    mock_client_cls.return_value.__enter__.return_value = mock_client

    from forti_report.config import get_settings

    session = authenticate_faz("user1", "pass1", get_settings())
    assert session.faz_user == "user1"
    assert session.faz_rpc_session == "faz-session-abc"
    assert session.adom == "CRUZ_AZUL"


@patch("forti_report.faz.auth.FortiAnalyzerClient")
def test_authenticate_faz_invalid(mock_client_cls):
    from forti_report.faz.auth import FazAuthError
    from forti_report.faz.client import FortiAnalyzerError
    from forti_report.config import get_settings

    mock_client = MagicMock()
    mock_client.login.side_effect = FortiAnalyzerError("bad")
    mock_client_cls.return_value.__enter__.return_value = mock_client

    with pytest.raises(FazAuthError, match="Credenciais inválidas"):
        authenticate_faz("user1", "wrong", get_settings())


@patch("forti_report.faz.auth.FortiAnalyzerClient")
def test_authenticate_faz_timeout(mock_client_cls):
    import httpx
    from forti_report.faz.auth import FazConnectionError
    from forti_report.config import get_settings

    mock_client = MagicMock()
    mock_client.login.side_effect = httpx.ConnectTimeout("timed out")
    mock_client_cls.return_value.__enter__.return_value = mock_client

    with pytest.raises(FazConnectionError, match="Timeout"):
        authenticate_faz("user1", "pass1", get_settings())
