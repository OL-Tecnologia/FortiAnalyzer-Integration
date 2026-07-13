"""Parser JSON exportado pelo FortiAnalyzer (MENSAL- RELATÓRIO GERAL)."""

from __future__ import annotations

import base64
import json
import re
import unicodedata
from datetime import datetime
from typing import Any

from forti_report.data.mensal_models import FazChartRecord, MensalGeralReport, PolicyDetailRow, TimelineSlice
from forti_report.data.parsers.faz_inventory import build_inventory_from_json_charts
from forti_report.data.parsers.mensal_utils import filter_ranked
from forti_report.data.wan_models import RankedItem, WebUsageSummary

# Prioridade de colunas para rótulo e valor conforme tipo de chart
_LABEL_PRIORITY = {
    "sites": ("Sites", "Site", "Hostname", "URL"),
    "category": ("Categories", "Category", "Categoria"),
    "user": ("User", "Usuário", "Usuario"),
    "policy": ("Policy", "Rule", "Policy Name", "Regra"),
    "application": ("Application", "Aplicação", "App"),
    "phishing": ("Site Phishing", "Site", "Victim", "User"),
    "generic": ("Sites", "Categories", "Category", "User", "Application", "Policy", "Name"),
}

_VALUE_PRIORITY = {
    "time": ("Browsing Time (hh:mm:ss)", "Browsing Time", "Time", "Tempo"),
    "requests": (
        "Requests",
        "Requisições",
        "Count",
        "Apps",
        "Sessions",
        "Bytes",
        "Banda",
        "Bandwidth",
    ),
    "percent": ("% do Total", "% do Subtotal", "%"),
}


def parse_mensal_json(raw: bytes, *, device_name: str = "") -> MensalGeralReport:
    payload = json.loads(raw.decode("utf-8", errors="replace"))
    report = MensalGeralReport(device_name=device_name)
    root = payload.get("fortianalyzer-report") or payload
    charts = root.get("charts") if isinstance(root, dict) else None
    if not isinstance(charts, list):
        _walk(payload, report)
        return report

    for chart in charts:
        if not isinstance(chart, dict):
            continue
        if chart.get("type") == "macro":
            _apply_macro(report, chart)
            continue
        title = _chart_title(chart)
        rows = chart.get("rows") or []
        if not rows:
            continue
        _assign_chart(report, title, rows)

    if isinstance(charts, list):
        report.faz_section_titles, report.faz_charts = build_inventory_from_json_charts(charts)
        report.content_source = "json"

    _enrich_summary_from_macros(report)
    return report


def _chart_title(chart: dict) -> str:
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


def _normalize_title(title: str) -> str:
    text = unicodedata.normalize("NFKD", title)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text).strip().lower()


def _apply_macro(report: MensalGeralReport, macro: dict) -> None:
    name = (macro.get("name") or "").strip()
    value = (macro.get("value") or "").strip()
    if name and value:
        report.macros[name] = value


def _enrich_summary_from_macros(report: MensalGeralReport) -> None:
    s = report.summary
    for key, val in report.macros.items():
        kn = _normalize_title(key)
        if "request count" in kn and not s.total_requests:
            s.total_requests = val
        elif "application count" in kn:
            try:
                s.applications = int(val.replace(",", "").split()[0])
            except ValueError:
                pass
        elif "category count" in kn:
            try:
                s.categories = int(val.replace(",", "").split()[0])
            except ValueError:
                pass
        elif "user count" in kn:
            try:
                s.users = int(val.replace(",", "").split()[0])
            except ValueError:
                pass
        elif "malicious" in kn:
            try:
                s.malicious_sites = int(val.replace(",", "").split()[0])
            except ValueError:
                pass
    if s.allowed_requests or s.blocked_requests:
        if not s.total_requests:
            s.total_requests = "calculado"


def _assign_chart(report: MensalGeralReport, title: str, rows: list) -> None:
    if _looks_like_base64(title):
        try:
            title = base64.b64decode(title + "==").decode("utf-8", errors="replace").strip()
        except Exception:
            return
    t = _normalize_title(title)
    if not t:
        return

    if "total de requis" in t:
        _apply_summary(report, rows)
        return

    if "tempo de uso da internet" in t or (
        "principais consumidores de banda" in t and "top 10" not in t
    ):
        if len(rows) > 5:
            report.bandwidth_timeline = _parse_timeline(rows)
        return

    if "top 20 sites" in t and "naveg" in t:
        report.top_sites_by_browsing = filter_ranked(
            _rows_to_ranked(rows, label_hint="sites", value_hint="time")[:20]
        )
        return

    if "categoria" in t and "maior tempo" in t and "naveg" in t:
        report.top_browsing_categories = filter_ranked(
            _rows_to_ranked(rows, label_hint="category", value_hint="time")[:15]
        )
        return

    if ("360 security" in t or "categorias de web visitad" in t) and "categor" in t:
        items = filter_ranked(
            _rows_to_ranked(
                rows, label_hint="category", value_hint="requests", combine_user=True
            )[:50]
        )
        if len(items) >= len(report.top_categories):
            report.top_categories = items
        return

    if "phishing" in t and ("vitima" in t or "site" in t):
        report.phishing_victims = filter_ranked(
            _rows_to_ranked(rows, label_hint="phishing", value_hint="requests")[:25]
        )
        return

    if "sites de risco" in t or "acessam sites de risco" in t:
        items = filter_ranked(
            _rows_to_ranked(rows, label_hint="user", value_hint="requests")[:15]
        )
        if len(items) >= len(report.top_risk_users):
            report.top_risk_users = items
        return

    if "360 degree" in t and "application" in t:
        items = filter_ranked(_rows_to_ranked(rows, label_hint="application", value_hint="requests"))
        if items:
            report.app_visibility = items[:20]
        return

    if "bloqueados por requis" in t or ("bloquead" in t and "categor" in t and "usuario" in t):
        report.blocked_usage_summary = filter_ranked(
            _rows_to_ranked(rows, label_hint="user", value_hint="requests")[:15]
        )
        return

    if "top 10" in t and "usuario" in t and "requis" in t:
        items = filter_ranked(
            _rows_to_ranked(rows, label_hint="user", value_hint="requests")[:10]
        )
        if "permitid" in t:
            report.top_users_allowed = items
        elif "bloquead" in t:
            report.top_users_blocked = items
        else:
            report.top_users_requests = items
        return

    if "aplicativos web" in t and "banda" in t:
        report.top_web_apps = filter_ranked(
            _rows_to_ranked(rows, label_hint="application", value_hint="requests")[:15]
        )
        return

    if "distribuicao" in t and "trafego" in t:
        report.sdwan_apps = filter_ranked(
            _rows_to_ranked(rows, label_hint="application", value_hint="requests")[:15]
        )
        return

    if "fontes" in t and "destinos" in t:
        report.sdwan_destinations = filter_ranked(
            _rows_to_ranked(rows, label_hint="generic", value_hint="requests")[:15]
        )
        return

    if "sd-wan" in t and "consumo" in t and "banda" in t:
        report.sdwan_users = filter_ranked(
            _rows_to_ranked(rows, label_hint="user", value_hint="requests")[:20]
        )
        return

    if "maiores consumidores" in t and "largura de banda" in t:
        report.top_bandwidth_timeline_users = filter_ranked(
            _rows_to_ranked(rows, label_hint="user", value_hint="requests")[:15]
        )
        return

    if "consumo de banda" in t and "top 10" in t and "usuario" in t:
        report.top_bandwidth_users = filter_ranked(
            _rows_to_ranked(rows, label_hint="user", value_hint="requests")[:10]
        )
        return

    if "regras mais utilizadas" in t and "sess" in t:
        report.policy_by_session = filter_ranked(
            _rows_to_ranked(rows, label_hint="policy", value_hint="requests")[:15]
        )
        return

    if "regras mais utilizadas" in t:
        report.policy_by_bandwidth = filter_ranked(
            _rows_to_ranked(rows, label_hint="policy", value_hint="requests")[:15]
        )
        return

    if "politicas" in t and "detalhes" in t:
        details = _parse_policy_details(rows)
        if details:
            report.policy_details = details
        return


def _apply_summary(report: MensalGeralReport, rows: list) -> None:
    for row in rows:
        if not isinstance(row, dict):
            continue
        cols = {c.get("name", ""): (c.get("value") or "").strip() for c in row.get("cols") or []}
        kind = cols.get("Type", cols.get("Tipo", "")).lower()
        requests = cols.get("Requests", cols.get("Requisições", "")).strip()
        if "allow" in kind or "permit" in kind:
            report.summary.allowed_requests = requests
        elif "block" in kind or "bloq" in kind:
            report.summary.blocked_requests = requests


def _parse_timeline(rows: list) -> list[TimelineSlice]:
    slices: list[TimelineSlice] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        cols_list = row.get("cols") or []
        label = ""
        values: dict[str, float] = {}
        for c in cols_list:
            name = (c.get("name") or "").strip()
            val = (c.get("value") or "").strip()
            if not name and val.isdigit() and len(val) >= 8:
                label = _format_epoch(val)
            elif name:
                try:
                    values[name] = float(val.replace(",", "") or 0)
                except ValueError:
                    values[name] = 0.0
        if values:
            slices.append(TimelineSlice(label=label or str(len(slices) + 1), values=values))
    return slices[:60]


def _format_epoch(epoch_str: str) -> str:
    try:
        return datetime.fromtimestamp(int(epoch_str)).strftime("%Y-%m-%d")
    except (ValueError, OSError):
        return epoch_str


def _parse_policy_details(rows: list) -> list[PolicyDetailRow]:
    details: list[PolicyDetailRow] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        cols = {c.get("name", ""): (c.get("value") or "").strip() for c in row.get("cols") or []}
        name = (
            cols.get("Policy Name")
            or cols.get("Policy")
            or cols.get("Rule Name")
            or cols.get("Rule")
            or ""
        )
        if not name or name.lower() in {"policy name", "policy", "rule", "#"}:
            continue
        if not (cols.get("Bytes") or cols.get("Sessions")):
            continue
        details.append(
            PolicyDetailRow(
                policy_name=name,
                policy_type=cols.get("Policy Type", ""),
                bytes_val=cols.get("Bytes", cols.get("Bandwidth", "")),
                sessions=cols.get("Sessions", ""),
                source_interface=cols.get("Source Interface", ""),
                destination_interface=cols.get("Destination Interface", ""),
                device_name=cols.get("Device Name", ""),
                last_used=cols.get("Last Used", ""),
            )
        )
    return details[:20]


def _pick_label(cols: dict[str, str], hint: str, cols_list: list | None = None) -> str:
    keys = _LABEL_PRIORITY.get(hint, _LABEL_PRIORITY["generic"])
    for key in keys:
        if cols.get(key):
            return cols[key]
    if cols_list:
        for c in cols_list:
            name = (c.get("name") or "").strip()
            val = (c.get("value") or "").strip()
            if not name and val and not (c.get("attr") or {}).get("name"):
                return val
    for k, v in cols.items():
        if k not in _all_value_keys() and v:
            return v
    return ""


def _pick_value(cols_list: list, cols: dict[str, str], hint: str) -> str:
    if hint == "time":
        keys = _VALUE_PRIORITY["time"]
    elif hint == "percent":
        keys = _VALUE_PRIORITY["percent"]
    else:
        keys = _VALUE_PRIORITY["requests"]

    for key in keys:
        if cols.get(key):
            return cols[key]

    for c in cols_list:
        merged = c.get("merged-cols")
        if isinstance(merged, list) and merged:
            return (merged[0].get("value") or "").strip()
        if "time" in (c.get("name") or "").lower() and c.get("value"):
            return (c.get("value") or "").strip()

    for c in cols_list:
        val = (c.get("value") or "").strip()
        if not val:
            continue
        attr = c.get("attr") or {}
        if attr.get("name") in ("Count", "Bytes", "Sessions", "Time Span"):
            return val

    for c in cols_list:
        if not (c.get("name") or "").strip() and (c.get("value") or "").strip():
            attr = c.get("attr") or {}
            if attr.get("name") in ("Count", "Bytes", "Sessions"):
                return (c.get("value") or "").strip()

    return ""


def _pick_percent(cols: dict[str, str]) -> str:
    for key in _VALUE_PRIORITY["percent"]:
        if cols.get(key):
            pct = cols[key].strip()
            return pct if pct.endswith("%") else f"{pct}%"
    return ""


def _all_value_keys() -> set[str]:
    out: set[str] = set()
    for group in _VALUE_PRIORITY.values():
        out.update(group)
    return out


def _rows_to_ranked(
    rows: list,
    *,
    label_hint: str = "generic",
    value_hint: str = "requests",
    combine_user: bool = False,
) -> list[RankedItem]:
    items: list[RankedItem] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        cols_list = row.get("cols") or []
        if not cols_list:
            continue
        cols = {c.get("name", ""): (c.get("value") or "").strip() for c in cols_list}
        rank = int(row.get("id") or len(items) + 1)
        label = _pick_label(cols, label_hint, cols_list)
        if combine_user and label and cols.get("User"):
            label = f"{label} — {cols['User']}"
        value = _pick_value(cols_list, cols, value_hint).strip()
        pct = _pick_percent(cols)
        category = cols.get("Category", cols.get("Categories", cols.get("Categoria", "")))
        if label:
            items.append(
                RankedItem(rank=rank, label=label, value=value, percentage=pct, category=category)
            )
    return items


def _walk(node: Any, report: MensalGeralReport, *, title_hint: str = "") -> None:
    if isinstance(node, dict):
        if node.get("type") == "macro":
            _apply_macro(report, node)
        title = str(node.get("title") or node.get("name") or title_hint)
        rows = node.get("rows")
        if isinstance(rows, list) and rows:
            _assign_chart(report, title, rows)
        for value in node.values():
            _walk(value, report, title_hint=title)
    elif isinstance(node, list):
        for item in node:
            _walk(item, report, title_hint=title_hint)
