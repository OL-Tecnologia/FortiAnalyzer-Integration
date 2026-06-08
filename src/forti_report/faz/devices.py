"""Listagem de dispositivos (unidades) no ADOM."""

from __future__ import annotations

from typing import Any

from forti_report.config import Settings, get_settings
from forti_report.faz.client import FortiAnalyzerClient


class DeviceService:
    def __init__(self, client: FortiAnalyzerClient, settings: Settings | None = None):
        self.client = client
        self.settings = settings or get_settings()
        self._url = f"/dvmdb/adom/{self.settings.faz_adom}/device"

    def list_devices(self) -> list[dict[str, Any]]:
        data = self.client._request("get", [{"url": self._url}])
        result = data.get("result") or []
        if not result:
            return []
        payload = result[0]
        if isinstance(payload, dict) and "data" in payload:
            devices = payload["data"]
            return list(devices) if isinstance(devices, list) else []
        return []

    def list_device_names(self) -> list[str]:
        names = [d.get("name", "") for d in self.list_devices()]
        return sorted(n for n in names if n)
