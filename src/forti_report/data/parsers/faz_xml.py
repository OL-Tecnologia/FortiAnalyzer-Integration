"""
Parser de relatórios XML exportados pelo FortiAnalyzer.

O layout XML varia por chart/schedule. Hoje o MENSAL unificado usa
principalmente `mensal_json.py`; este módulo é fallback para download XML
e será calibrado com amostras reais do schedule **MENSAL- RELATÓRIO GERAL**.
Ver README → seção «Próximos passos».
"""

from __future__ import annotations

import base64
import io
import zipfile
from xml.etree import ElementTree as ET

from forti_report.data.models import SectionData, SiteRankingItem


def decode_faz_payload(data_field: str, *, data_type: str | None = None) -> bytes:
    """Decodifica payload zip/base64 padrão da API de download."""
    if data_type == "text":
        return data_field.encode("utf-8")
    raw = base64.b64decode(data_field)
    if raw[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            names = zf.namelist()
            if not names:
                raise ValueError("ZIP do relatório vazio")
            return zf.read(names[0])
    return raw


def parse_report_xml_to_sections(xml_bytes: bytes) -> list[SectionData]:
    """
    Extrai seções do XML do FAZ.

    Implementação inicial: placeholder (ranking genérico de sites).
    Calibrar com XML real do MENSAL- RELATÓRIO GERAL — ver README «Próximos passos».
    """
    root = ET.fromstring(xml_bytes)
    items: list[SiteRankingItem] = []

    for row in root.iter("row"):
        cells = [c.text or "" for c in row.findall(".//cell") or row.findall("cell")]
        if len(cells) >= 2 and _looks_like_site_row(cells):
            items.append(
                SiteRankingItem(
                    site=cells[0].strip(),
                    hits=_safe_int(cells[1]),
                    bandwidth_mb=_safe_float(cells[2]) if len(cells) > 2 else None,
                )
            )

    if not items:
        return []

    return [
        SectionData(
            key="top-sites",
            title="Ranking de sites acessados",
            site_ranking=items[:50],
        )
    ]


def _looks_like_site_row(cells: list[str]) -> bool:
    first = cells[0].strip().lower()
    if not first or first.isdigit():
        return False
    return "." in first or first.startswith("www")


def _safe_int(value: str) -> int | None:
    try:
        return int(value.replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def _safe_float(value: str) -> float | None:
    try:
        return float(value.replace(",", "").strip())
    except (ValueError, AttributeError):
        return None
