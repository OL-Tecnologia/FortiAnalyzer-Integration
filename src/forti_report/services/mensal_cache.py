"""Cache MENSAL: metadados, validação contra FAZ e escopo de gráficos por relatório."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from forti_report.config import Settings
from forti_report.data.models import UnitReport


@dataclass(frozen=True)
class MensalCacheMeta:
    tid: str
    period_start: str | None = None
    period_end: str | None = None
    report_name: str | None = None
    cached_at: str = ""

    @classmethod
    def from_faz_report(cls, report: dict[str, Any]) -> MensalCacheMeta | None:
        tid = report.get("tid")
        if not tid:
            return None
        return cls(
            tid=str(tid),
            period_start=_iso_or_none(report.get("period-start")),
            period_end=_iso_or_none(report.get("period-end")),
            report_name=report.get("name") or report.get("title"),
            cached_at=datetime.now().isoformat(timespec="seconds"),
        )

    def matches_report(self, report: dict[str, Any] | None) -> bool:
        if not report:
            return False
        latest_tid = report.get("tid")
        if not latest_tid or str(latest_tid) != self.tid:
            return False
        faz_end = report.get("period-end")
        if self.period_end and faz_end is not None:
            return _period_key(faz_end) == _period_key(self.period_end)
        return True


def _period_key(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value).strip()


def _iso_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def meta_path(cache_dir: Path, device_name: str) -> Path:
    safe = device_name.replace("/", "-").replace("[", "_").replace("]", "")
    return cache_dir / f"{safe}.meta.json"


def save_cache_meta(cache_dir: Path, device_name: str, meta: MensalCacheMeta) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    meta_path(cache_dir, device_name).write_text(
        json.dumps(
            {
                "tid": meta.tid,
                "period_start": meta.period_start,
                "period_end": meta.period_end,
                "report_name": meta.report_name,
                "cached_at": meta.cached_at,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def load_cache_meta(cache_dir: Path, device_name: str) -> MensalCacheMeta | None:
    path = meta_path(cache_dir, device_name)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        tid = data.get("tid")
        if not tid:
            return None
        return MensalCacheMeta(
            tid=str(tid),
            period_start=data.get("period_start"),
            period_end=data.get("period_end"),
            report_name=data.get("report_name"),
            cached_at=data.get("cached_at") or "",
        )
    except (json.JSONDecodeError, OSError):
        return None


def json_cache_is_fresh(
    cache_dir: Path,
    device_name: str,
    latest_report: dict[str, Any] | None,
) -> bool:
    """
    True se o arquivo local (mesmo nome sempre) ainda é o relatório atual no FAZ.
    Nome do JSON não muda; o conteúdo válido depende do TID/período em .meta.json.
    """
    meta = load_cache_meta(cache_dir, device_name)
    if not meta:
        return False
    json_path = cache_dir / f"{device_name.replace('/', '-').replace('[', '_').replace(']', '')}.json"
    if not json_path.is_file():
        return False
    return meta.matches_report(latest_report)


def chart_scope_for_unit(unit: UnitReport) -> str:
    """Identificador estável do relatório para cache de gráficos (muda a cada execução mensal)."""
    if unit.faz_tid:
        return f"tid:{unit.faz_tid}"
    if unit.period_end:
        return f"period:{unit.period_end:%Y%m%d}"
    if unit.period_start:
        return f"period:{unit.period_start:%Y%m}"
    return f"device:{unit.device_name}"


def chart_scope_dir(settings: Settings, cache_scope: str) -> Path:
    digest = hashlib.sha256(cache_scope.encode()).hexdigest()[:16]
    return settings.pdf_chart_cache_dir / digest


def prune_stale_chart_cache(settings: Settings, active_scopes: set[str]) -> None:
    """Remove pastas de gráficos de relatórios antigos (não reutiliza mês anterior)."""
    root = settings.pdf_chart_cache_dir
    if not root.is_dir():
        return
    active_dirs = {chart_scope_dir(settings, s).name for s in active_scopes if s}
    for child in root.iterdir():
        if not child.is_dir():
            continue
        if child.name not in active_dirs:
            shutil.rmtree(child, ignore_errors=True)
    # PNG legados (hash flat, sem escopo) — não usar em relatório novo
    for png in root.glob("*.png"):
        if png.name.startswith("logo_"):
            continue
        png.unlink(missing_ok=True)


def mensal_pdf_filename(settings: Settings) -> str:
    """Nome fixo de entrega; cada geração sobrescreve com dados do relatório atual."""
    return f"MENSAL_UNIFICADO_{settings.faz_adom}.pdf"
