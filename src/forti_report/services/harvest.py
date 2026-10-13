"""Colheita: baixa os relatórios já gerados no FAZ e guarda o JSON local."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from forti_report.config import Settings
from forti_report.data.harvest_catalog import HARVEST_LAYOUTS, HarvestLayout
from forti_report.data.parsers.faz_xml import decode_faz_payload
from forti_report.data.units import (
    extract_device_from_report_name,
    normalize_device_name,
    normalize_schedule_key,
    report_device_text,
)
from forti_report.faz.client import FortiAnalyzerClient, FortiAnalyzerError
from forti_report.faz.reports import ReportService


@dataclass
class HarvestItem:
    cycle: str
    prefix: str
    device: str
    tid: str
    name: str
    period_start: str
    period_end: str
    fmt: str
    path: str
    bytes: int


@dataclass
class HarvestResult:
    root: Path
    listed: int = 0
    items: list[HarvestItem] = field(default_factory=list)
    outside: list[dict[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def index_path(self) -> Path:
        return self.root / "index.json"


def classify_report(report: dict[str, Any]) -> HarvestLayout | None:
    """Escolhe o layout pelo prefixo. Um diário não vira semanal nem mensal."""
    name = normalize_schedule_key(str(report.get("name") or ""))
    title = normalize_schedule_key(str(report.get("title") or ""))
    ranked = sorted(
        HARVEST_LAYOUTS,
        key=lambda layout: len(normalize_schedule_key(layout.prefix)),
        reverse=True,
    )
    for layout in ranked:
        needle = normalize_schedule_key(layout.prefix)
        if needle and (needle in name or needle in title):
            return layout
    return None


def harvest_reports(
    settings: Settings,
    *,
    days: int = 90,
    on_saved: Callable[[HarvestItem], None] | None = None,
) -> HarvestResult:
    """Lista o período, baixa JSON (ou XML) de cada layout do catálogo e grava o índice."""
    root = settings.output_dir / "colheita"
    root.mkdir(parents=True, exist_ok=True)
    result = HarvestResult(root=root)

    with FortiAnalyzerClient(settings) as client:
        client.login()
        service = ReportService(client, settings)
        reports = service.list_reports(days=days)
        result.listed = len(reports)
        for report in reports:
            layout = classify_report(report)
            if layout is None:
                result.outside.append(_outside_row(report))
                continue
            try:
                item = _download_one(service, root, layout, report)
            except (FortiAnalyzerError, ValueError, OSError) as exc:
                name = str(report.get("name") or report.get("tid") or "relatório")
                result.errors.append(f"{layout.prefix}: {name}: {exc}")
                continue
            if item:
                result.items.append(item)
                if on_saved:
                    on_saved(item)

    _write_index(result, settings, days=days)
    return result


def _outside_row(report: dict[str, Any]) -> dict[str, str]:
    return {
        "name": str(report.get("name") or ""),
        "title": str(report.get("title") or ""),
        "tid": str(report.get("tid") or ""),
    }


def _outside_titles(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    counts = Counter(row.get("title") or row.get("name") or "sem-titulo" for row in rows)
    return [{"title": title, "count": count} for title, count in counts.most_common()]


def _download_one(
    service: ReportService,
    root: Path,
    layout: HarvestLayout,
    report: dict[str, Any],
) -> HarvestItem | None:
    tid = str(report.get("tid") or "").strip()
    if not tid:
        return None
    name = str(report.get("name") or report.get("title") or tid)
    device = _device_label(report, name)
    folder = root / layout.cycle / folder_name(layout.prefix)
    folder.mkdir(parents=True, exist_ok=True)
    stem = _file_stem(device, report, tid)
    existing = _existing_file(folder, stem)
    if existing is not None:
        return _item_from_file(layout, device, tid, name, report, existing, root)

    last_error: Exception | None = None
    for fmt in ("JSON", "XML"):
        try:
            payload = service.download_report(tid, fmt=fmt)  # type: ignore[arg-type]
            raw = decode_faz_payload(
                payload.get("data", ""),
                data_type=payload.get("data-type"),
            )
        except (FortiAnalyzerError, ValueError) as exc:
            last_error = exc
            continue
        suffix = ".json" if fmt == "JSON" else ".xml"
        path = folder / f"{stem}{suffix}"
        path.write_bytes(raw)
        return _item_from_file(layout, device, tid, name, report, path, root)
    if last_error:
        raise ValueError(str(last_error))
    return None


def folder_name(prefix: str) -> str:
    """Nome de pasta sem acento, barra ou espaço."""
    text = unicodedata.normalize("NFKD", prefix or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")
    return text or "sem_titulo"


def _device_label(report: dict[str, Any], name: str) -> str:
    found = extract_device_from_report_name(name)
    if not found:
        found = normalize_device_name(report_device_text(report))
    return _safe_part(found or "sem-dispositivo")


def _safe_part(value: str) -> str:
    text = value.replace("\\", "-").replace("/", "-")
    text = re.sub(r'[<>:"|?*]+', "-", text)
    text = re.sub(r"\s+", "_", text).strip("._- ")
    return text or "sem-nome"


def _file_stem(device: str, report: dict[str, Any], tid: str) -> str:
    period = str(report.get("period-end") or "")
    match = re.search(r"(\d{4})[/-](\d{2})[/-](\d{2})", period)
    day = f"{match.group(1)}-{match.group(2)}-{match.group(3)}" if match else "sem-data"
    return f"{_safe_part(device)}__{day}__{tid[:8]}"


def _existing_file(folder: Path, stem: str) -> Path | None:
    for suffix in (".json", ".xml"):
        path = folder / f"{stem}{suffix}"
        if path.is_file() and path.stat().st_size > 0:
            return path
    return None


def _item_from_file(
    layout: HarvestLayout,
    device: str,
    tid: str,
    name: str,
    report: dict[str, Any],
    path: Path,
    root: Path,
) -> HarvestItem:
    return HarvestItem(
        cycle=layout.cycle,
        prefix=layout.prefix,
        device=device,
        tid=tid,
        name=name,
        period_start=str(report.get("period-start") or ""),
        period_end=str(report.get("period-end") or ""),
        fmt="JSON" if path.suffix.lower() == ".json" else "XML",
        path=str(path.relative_to(root)).replace("\\", "/"),
        bytes=path.stat().st_size,
    )


def _write_index(result: HarvestResult, settings: Settings, *, days: int) -> None:
    payload = {
        "harvested_at": datetime.now().isoformat(timespec="seconds"),
        "client": settings.client_slug,
        "display_name": settings.client_display_name,
        "adom": settings.faz_adom,
        "days": days,
        "saved": len(result.items),
        "outside_catalog": len(result.outside),
        "errors": result.errors,
        "items": [item.__dict__ for item in result.items],
        "outside_titles": _outside_titles(result.outside),
    }
    result.index_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
