"""Inventário de títulos, widgets e texto tabular dos exports FAZ (JSON/PDF)."""

from __future__ import annotations

import base64
import re
import unicodedata

from forti_report.data.mensal_models import FazChartRecord

# Padrões título de chart → campo do parser (referência compare_mensal_coverage)
CHART_FIELD_PATTERNS: tuple[tuple[str, str], ...] = (
    ("total de requis", "summary"),
    ("permitid", "top_users_allowed"),
    ("bloquead", "top_users_blocked"),
    ("top 20 sites", "top_sites_by_browsing"),
    ("maior tempo de naveg", "top_browsing_categories"),
    ("360 security", "top_categories"),
    ("categorias de web visitad", "top_categories"),
    ("sites de risco", "top_risk_users"),
    ("acessam sites de risco", "top_risk_users"),
    ("phishing", "phishing_victims"),
    ("360 degree", "app_visibility"),
    ("bloqueados por requis", "blocked_usage_summary"),
    ("bloquead", "blocked_usage_summary"),
    ("aplicativos web", "top_web_apps"),
    ("distribuicao de trafego", "sdwan_apps"),
    ("sd-wan", "sdwan_apps"),
    ("fontes", "sdwan_destinations"),
    ("destinos", "sdwan_destinations"),
    ("consumo de banda", "top_bandwidth_users"),
    ("maiores consumidores", "top_bandwidth_timeline_users"),
    ("tempo de uso da internet", "bandwidth_timeline"),
    ("regras mais utilizadas", "policy_by_bandwidth"),
    ("politicas", "policy_details"),
    ("web usage request count", "macros"),
    ("device availability", "macros"),
)

_HEADING_KEYWORDS = (
    "resumo",
    "top ",
    "categor",
    "navega",
    "usuário",
    "usuario",
    "sd-wan",
    "sdwan",
    "banda",
    "risco",
    "sumário",
    "sumario",
    "análise",
    "analise",
    "aplic",
    "polític",
    "politic",
    "regra",
    "phishing",
    "360",
    "consumo",
    "largura",
    "atividade",
    "malicios",
    "fortianalyzer",
    "relatório",
    "relatorio",
    "mensal",
    "semanal",
)


# Campos que o PDF unificado renderiza hoje (via unified_mensal_builder)
RENDERED_FIELDS = frozenset({
    "summary",
    "top_users_allowed",
    "top_users_blocked",
    "top_categories",
    "top_browsing_categories",
    "top_sites_by_browsing",
    "top_risk_users",
    "phishing_victims",
    "app_visibility",
    "blocked_usage_summary",
    "top_web_apps",
    "sdwan_apps",
    "sdwan_destinations",
    "sdwan_users",
    "top_bandwidth_users",
    "top_bandwidth_timeline_users",
    "bandwidth_timeline",
    "policy_by_bandwidth",
    "policy_by_session",
    "policy_details",
    "macros",
})


def decode_chart_title(chart: dict) -> str:
    name = chart.get("name") or chart.get("title") or ""
    if not isinstance(name, str) or not name.strip():
        return ""
    if _is_readable(name) and not _looks_like_base64(name):
        return name.strip()
    try:
        decoded = base64.b64decode(name + "==").decode("utf-8", errors="replace").strip()
        if decoded and _is_readable(decoded):
            return decoded
    except Exception:
        pass
    return name.strip()


def _looks_like_base64(text: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9+/=]+", text.strip())) and len(text) > 16


def _is_readable(text: str) -> bool:
    if not text or len(text) < 3:
        return False
    printable = sum(1 for c in text if c.isprintable() and c not in "\x00\x0b")
    return printable / max(len(text), 1) > 0.75


def normalize_title(title: str) -> str:
    text = unicodedata.normalize("NFKD", title or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text).strip().lower()


def chart_target_field(title: str) -> str:
    t = normalize_title(title)
    if not t:
        return "unmapped"
    for pat, field_name in CHART_FIELD_PATTERNS:
        if pat in t:
            return field_name
    return "unmapped"


def preview_rows_from_json(rows: list, *, max_rows: int = 5, max_cols: int = 6) -> list[list[str]]:
    out: list[list[str]] = []
    for row in rows[:max_rows]:
        if not isinstance(row, dict):
            continue
        cols = row.get("cols") or []
        cells: list[str] = []
        for col in cols[:max_cols]:
            if not isinstance(col, dict):
                continue
            name = (col.get("name") or "").strip()
            val = (col.get("value") or "").strip()
            if name and val:
                cells.append(f"{name}: {val}")
            elif val:
                cells.append(val)
            elif name:
                cells.append(name)
        if cells:
            out.append(cells)
    return out


def record_from_json_chart(chart: dict, *, title: str) -> FazChartRecord:
    chart_type = chart.get("type") or "chart"
    if chart_type == "macro":
        name = (chart.get("name") or title or "Widget").strip()
        value = (chart.get("value") or "").strip()
        field_name = chart_target_field(name)
        if field_name == "unmapped" and value:
            field_name = "macros"
        return FazChartRecord(
            title=name or title,
            chart_type="macro",
            row_count=1 if value else 0,
            mapped_field=field_name,
            rendered_in_pdf=field_name in RENDERED_FIELDS,
            preview_rows=[[name, value]] if value else [],
        )

    rows = chart.get("rows") or []
    field_name = chart_target_field(title)
    return FazChartRecord(
        title=title,
        chart_type="chart",
        row_count=len(rows),
        mapped_field=field_name,
        rendered_in_pdf=field_name in RENDERED_FIELDS and bool(rows),
        preview_rows=preview_rows_from_json(rows),
    )


def build_inventory_from_json_charts(charts: list) -> tuple[list[str], list[FazChartRecord]]:
    titles: list[str] = []
    records: list[FazChartRecord] = []
    seen_titles: set[str] = set()

    for chart in charts:
        if not isinstance(chart, dict):
            continue
        title = decode_chart_title(chart)
        if chart.get("type") == "macro":
            name = (chart.get("name") or title).strip()
            if name and name not in seen_titles:
                seen_titles.add(name)
                titles.append(name)
        elif title and title not in seen_titles:
            seen_titles.add(title)
            titles.append(title)

        if chart.get("type") == "macro" or (chart.get("rows") or []):
            records.append(record_from_json_chart(chart, title=title))

    return titles, records


def extract_pdf_section_headings(text: str) -> list[str]:
    """Títulos de seção detectados no texto extraído do PDF FAZ."""
    headings: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if len(line) < 8 or len(line) > 120:
            continue
        lower = line.lower()
        if not any(k in lower for k in _HEADING_KEYWORDS):
            continue
        if line.isupper() or re.match(r"^[A-ZÁÉÍÓÚÂÊÔÃÕÇ0-9]", line):
            key = normalize_title(line)
            if key not in seen:
                seen.add(key)
                headings.append(line)
    return headings


def build_inventory_from_pdf_text(
    text: str,
    *,
    summary_rows: list[list[str]] | None = None,
    section_blocks: list[tuple[str, list[list[str]]]] | None = None,
) -> tuple[list[str], list[FazChartRecord]]:
    titles = extract_pdf_section_headings(text)
    records: list[FazChartRecord] = []

    if summary_rows:
        records.append(
            FazChartRecord(
                title="RESUMO DE UTILIZAÇÃO WEB (widgets PDF)",
                chart_type="chart",
                row_count=len(summary_rows),
                mapped_field="summary",
                rendered_in_pdf=True,
                preview_rows=summary_rows,
            )
        )

    for block_title, rows in section_blocks or []:
        field_name = chart_target_field(block_title)
        records.append(
            FazChartRecord(
                title=block_title,
                chart_type="chart",
                row_count=len(rows),
                mapped_field=field_name,
                rendered_in_pdf=field_name in RENDERED_FIELDS and bool(rows),
                preview_rows=rows[:5],
            )
        )

    return titles, records
