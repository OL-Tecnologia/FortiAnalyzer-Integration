"""Teste de conectividade com FortiAnalyzer (admin)."""

from __future__ import annotations

import httpx

from forti_report.clients.bridge import settings_from_client
from forti_report.clients.models import ClientConfig
from forti_report.clients.store import resolve_automation_password
from forti_report.config import Settings, get_settings
from forti_report.faz.client import FortiAnalyzerClient, FortiAnalyzerError


def test_faz_connection(
    client: ClientConfig,
    *,
    faz_user: str | None = None,
    faz_password: str | None = None,
    settings: Settings | None = None,
) -> dict:
    """
    Testa JSON-RPC + login no FAZ do tenant.
    Usa user/senha informados, senão a conta de automação do client.
    """
    settings = settings or get_settings()
    user = (faz_user or client.automation.faz_user or "").strip()
    password = (faz_password or resolve_automation_password(client, settings) or "").strip()
    if not user or not password:
        return {
            "ok": False,
            "detail": "Informe usuário/senha do FAZ (ou configure a conta de automação do tenant).",
        }

    probe = settings_from_client(
        client,
        settings,
        faz_user=user,
        faz_password=password,
    )
    try:
        with FortiAnalyzerClient(probe) as faz:
            faz.login()
            faz.logout()
    except httpx.TimeoutException:
        return {
            "ok": False,
            "detail": f"Timeout ao conectar em {probe.jsonrpc_url}. Verifique rede/VPN e host/porta.",
        }
    except httpx.RequestError as exc:
        return {
            "ok": False,
            "detail": f"Falha de rede ao conectar em {probe.jsonrpc_url}: {exc}",
        }
    except FortiAnalyzerError:
        return {
            "ok": False,
            "detail": "Conectou ao host, mas o login FAZ foi rejeitado (credenciais ou ADOM).",
        }
    except Exception as exc:
        return {"ok": False, "detail": f"Erro inesperado: {exc}"}

    return {
        "ok": True,
        "detail": f"Conexão OK com {client.faz.host}:{client.faz.port} (ADOM {client.faz.adom}).",
        "jsonrpc_url": probe.jsonrpc_url,
        "adom": client.faz.adom,
    }
