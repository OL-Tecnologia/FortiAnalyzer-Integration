"""Operações do módulo Report (api.json)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Literal

from forti_report.config import Settings, get_settings
from forti_report.data.units import report_matches_device
from forti_report.faz.client import FortiAnalyzerClient

ReportFormat = Literal["PDF", "HTML", "XML", "CSV", "JSON"]
ReportState = Literal["generated", "pending-running"]


class ReportService:
    def __init__(self, client: FortiAnalyzerClient, settings: Settings | None = None):
        self.client = client
        self.settings = settings or get_settings()
        self._adom_base = f"/report/adom/{self.settings.faz_adom}"

    def list_reports(
        self,
        *,
        state: ReportState = "generated",
        days: int = 30,
        title: str | None = None,
    ) -> list[dict[str, Any]]:
        end = datetime.now()
        start = end - timedelta(days=days)
        extra: dict[str, Any] = {
            "state": state,
            "time-range": {
                "start": start.strftime("%Y-%m-%dT%H:%M:%S"),
                "end": end.strftime("%Y-%m-%dT%H:%M:%S"),
            },
        }
        if title:
            extra["title"] = title

        result = self.client.get(f"{self._adom_base}/reports/state", extra=extra)
        return list((result or {}).get("data") or [])

    def list_by_device(
        self,
        device_name: str,
        *,
        days: int = 30,
        title: str | None = None,
    ) -> list[dict[str, Any]]:
        reports = self.list_reports(days=days, title=title)
        matches = [r for r in reports if report_matches_device(r, device_name)]
        if not matches and title:
            matches = [
                r for r in self.list_reports(days=days) if report_matches_device(r, device_name)
            ]
        schedule = self.settings.faz_report_schedule
        if schedule:
            preferred = [r for r in matches if schedule.lower() in (r.get("title") or "").lower()
                         or schedule.lower() in (r.get("name") or "").lower()]
            if preferred:
                matches = preferred
        return matches

    def find_latest_report_for_device(
        self,
        device_name: str,
        *,
        days: int = 30,
    ) -> dict[str, Any] | None:
        matches = self.list_by_device(device_name, days=days)
        return matches[0] if matches else None

    def find_latest_wan_report(self, *, days: int = 60) -> dict | None:
        schedule = self.settings.faz_wan_report_schedule.lower()
        reports = self.list_reports(days=days)
        matches = [
            r
            for r in reports
            if schedule in (r.get("title") or "").lower()
            or schedule in (r.get("name") or "").lower()
        ]
        return matches[0] if matches else None

    def download_report(
        self,
        tid: str,
        *,
        fmt: ReportFormat = "XML",
        data_type: str | None = None,
    ) -> dict[str, Any]:
        extra: dict[str, Any] = {"format": fmt}
        if data_type:
            extra["data-type"] = data_type
        result = self.client.get(f"{self._adom_base}/reports/data/{tid}", extra=extra)
        if not isinstance(result, dict):
            raise ValueError(f"Resposta inesperada ao baixar relatório {tid}")
        return result

    def run_report(
        self,
        *,
        schedule: str | None = None,
        device: str | None = None,
        layout_id: int | None = None,
        time_period: str | None = None,
    ) -> str:
        extra: dict[str, Any] = {}
        if schedule:
            extra["schedule"] = schedule
        if device or layout_id or time_period:
            extra["schedule-param"] = {
                k: v
                for k, v in {
                    "device": device,
                    "layout-id": layout_id,
                    "time-period": time_period or self.settings.faz_time_period,
                }.items()
                if v is not None
            }
        result = self.client.add(f"{self._adom_base}/run", extra=extra)
        tid = (result or {}).get("tid")
        if not tid:
            raise ValueError("run sem tid na resposta")
        return tid

    def get_run_status(self, tid: str) -> dict[str, Any]:
        result = self.client.get(f"{self._adom_base}/run/{tid}")
        return result if isinstance(result, dict) else {}
