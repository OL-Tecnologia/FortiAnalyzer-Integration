"""Utilitários para identificar unidades a partir de relatórios."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

# Prefixo real dos arquivos gerados no FAZ. O sufixo (hostname) muda por cliente:
# MENSAL-RELATÓRIO DE ENDPOINT-fw-cas-cruz-azul-colegio[root]-2026-10-09-...
# MENSAL-RELATÓRIO DE ENDPOINT-MLGOMES_FG4H0E[root]-2026-10-09-...
DEFAULT_MENSAL_SCHEDULE = "MENSAL-RELATÓRIO DE ENDPOINT"
# Valor antigo da tela, que não existe no nome do arquivo gerado.
_LEGACY_MENSAL_SCHEDULES = frozenset({"mensal-relatoriogeral"})

# Hostname entre o prefixo e a data, com ou sem [vdom].
_DEVICE_IN_REPORT = re.compile(
    r"-(?P<device>[A-Za-z0-9][A-Za-z0-9_.-]*)(?:\[[^\]]+\])?-\d{4}-\d{2}-\d{2}-",
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


def normalize_schedule_key(value: str) -> str:
    """Ignora acento e espaços para comparar o prefixo do relatório."""
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", "", text).strip().lower()


def effective_mensal_schedule(schedule: str | None) -> str:
    """Prefixo usado na busca. Vazio ou o nome legado viram o prefixo real do FAZ."""
    raw = (schedule or "").strip()
    key = normalize_schedule_key(raw)
    if not key or key in _LEGACY_MENSAL_SCHEDULES:
        return DEFAULT_MENSAL_SCHEDULE
    return raw


def report_has_schedule(report: dict[str, Any], schedule: str | None) -> bool:
    """True se o nome ou o título do arquivo começa pelo prefixo do schedule."""
    needle = normalize_schedule_key(effective_mensal_schedule(schedule))
    if not needle:
        return False
    for key in ("name", "title"):
        if needle in normalize_schedule_key(str(report.get(key) or "")):
            return True
    return False


def extract_device_from_report_name(report_name: str) -> str | None:
    match = _DEVICE_IN_REPORT.search(report_name)
    if not match:
        return None
    return normalize_device_name(match.group("device"))
