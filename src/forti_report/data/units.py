"""Utilitários para identificar unidades a partir de relatórios."""

from __future__ import annotations

import re
from typing import Any

# Padrão: MENSAL- RELATÓRIO GERAL-fw-spo-cruz-azul-centro[root]-...
_DEVICE_IN_REPORT = re.compile(
    r"(?:fw|hafw\d?)-[a-z0-9-]+(?:\[[^\]]+\])?",
    re.IGNORECASE,
)


def normalize_device_name(value: str) -> str:
    """Remove sufixos como [root] do nome do dispositivo."""
    return re.sub(r"\[.*\]$", "", value.strip())


def report_device_text(report: dict[str, Any]) -> str:
    """Extrai texto do campo device (string ou objeto da API)."""
    device = report.get("device")
    if isinstance(device, str):
        return device
    if isinstance(device, dict):
        data = device.get("data")
        if isinstance(data, str):
            return data
        if isinstance(data, list):
            return " ".join(str(x) for x in data)
    name = report.get("name") or ""
    extracted = extract_device_from_report_name(name)
    return extracted or ""


def report_matches_device(report: dict[str, Any], device_name: str) -> bool:
    needle = device_name.lower()
    haystacks = [
        report.get("name") or "",
        report.get("title") or "",
        report_device_text(report),
    ]
    return any(needle in str(h).lower() for h in haystacks)


def extract_device_from_report_name(report_name: str) -> str | None:
    match = _DEVICE_IN_REPORT.search(report_name)
    if not match:
        return None
    return normalize_device_name(match.group(0))
