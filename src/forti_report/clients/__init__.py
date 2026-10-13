"""Catálogo multi-tenant de clientes FAZ."""

from forti_report.clients.bridge import settings_from_client
from forti_report.clients.models import ClientConfig
from forti_report.clients.store import (
    ClientStoreError,
    automation_password_set,
    delete_client,
    ensure_default_client_file,
    get_client,
    list_clients,
    list_clients_or_legacy,
    require_client,
    resolve_automation_password,
    save_client,
)

__all__ = [
    "ClientConfig",
    "ClientStoreError",
    "automation_password_set",
    "delete_client",
    "ensure_default_client_file",
    "get_client",
    "list_clients",
    "list_clients_or_legacy",
    "require_client",
    "resolve_automation_password",
    "save_client",
    "settings_from_client",
]
