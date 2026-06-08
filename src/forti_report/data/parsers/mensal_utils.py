"""Utilitários de validação e conversão de métricas dos relatórios MENSAL."""

from __future__ import annotations

import re

from forti_report.data.mensal_models import TimelineSlice
from forti_report.data.wan_models import RankedItem


def filter_ranked(items: list[RankedItem], *, require_value: bool = True) -> list[RankedItem]:
    """Remove linhas sem rótulo ou sem métrica utilizável."""
    out: list[RankedItem] = []
    for item in items:
        if not (item.label or "").strip():
            continue
        if require_value and not _has_metric(item):
            continue
        out.append(item)
    return out


def _has_metric(item: RankedItem) -> bool:
    if (item.percentage or "").strip():
        return True
    val = (item.value or "").strip()
    if not val:
        return False
    if val in {"—", "-", "0", "0.0"}:
        return False
    return True


def parse_numeric_value(raw: str) -> float | None:
    """Converte requisições, bytes, % ou duração hh:mm:ss em número."""
    text = (raw or "").strip()
    if not text:
        return None
    if _TIME_RE.match(text):
        return float(duration_to_seconds(text))
    cleaned = text.replace(",", "").replace("%", "").strip()
    mult = 1.0
    upper = text.upper()
    if "GB" in upper:
        mult = 1024**3
        cleaned = re.sub(r"[^\d.]", "", cleaned)
    elif "MB" in upper:
        mult = 1024**2
        cleaned = re.sub(r"[^\d.]", "", cleaned)
    elif "KB" in upper or "K" in upper.split()[-1:]:
        mult = 1024
        cleaned = re.sub(r"[^\d.]", "", cleaned)
    elif "M" in upper and "MB" not in upper:
        mult = 1_000_000
        cleaned = re.sub(r"[^\d.]", "", cleaned)
    try:
        return float(cleaned) * mult
    except ValueError:
        return None


_TIME_RE = re.compile(r"^\d{1,3}:\d{2}:\d{2}$")


def duration_to_seconds(text: str) -> int:
    parts = text.strip().split(":")
    if len(parts) != 3:
        return 0
    try:
        h, m, s = (int(p) for p in parts)
        return h * 3600 + m * 60 + s
    except ValueError:
        return 0


def format_bandwidth(value: str) -> str:
    """Normaliza bytes crus ou strings GB/MB para exibição uniforme."""
    raw = (value or "").strip()
    if not raw:
        return "—"
    num = parse_numeric_value(raw)
    if num is None:
        return raw

    gb = num / (1024**3)
    if gb >= 1:
        return f"{gb:.2f} GB"
    mb = num / (1024**2)
    if mb >= 1:
        return f"{mb:.2f} MB"
    kb = num / 1024
    if kb >= 1:
        return f"{kb:.2f} KB"
    return f"{num:.0f} B"


def bytes_to_gb(value: float) -> float:
    return value / (1024**3)


def pie_values_from_items(items: list[RankedItem], *, max_items: int = 8) -> tuple[list[str], list[float]]:
    """Agrega por rótulo (categoria) para evitar fatias duplicadas no gráfico."""
    acc: dict[str, float] = {}
    for item in items:
        num = None
        if (item.percentage or "").strip():
            num = parse_numeric_value(item.percentage)
        if num is None and (item.value or "").strip():
            num = parse_numeric_value(item.value)
        if num is None or num <= 0:
            continue
        key = (item.label.split(" — ")[0] if " — " in item.label else item.label)[:40]
        acc[key] = acc.get(key, 0.0) + num
    ranked = sorted(acc.items(), key=lambda x: x[1], reverse=True)[:max_items]
    return [k for k, _ in ranked], [v for _, v in ranked]


def timeline_has_signal(slices: list[TimelineSlice]) -> bool:
    for sl in slices:
        if any(v > 0 for v in sl.values.values()):
            return True
    return False


def ranked_chart_values(items: list[RankedItem], *, max_items: int = 15) -> tuple[list[str], list[float]]:
    labels: list[str] = []
    values: list[float] = []
    for item in items[:max_items]:
        num = parse_numeric_value(item.value or "")
        if num is None and (item.percentage or "").strip():
            num = parse_numeric_value(item.percentage)
        if num is None or num <= 0:
            continue
        labels.append(item.label[:50])
        values.append(num)
    return labels, values
