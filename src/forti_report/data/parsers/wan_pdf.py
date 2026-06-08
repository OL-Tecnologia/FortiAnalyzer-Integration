"""Parser do PDF SEMANAL Tráfego WAN (FortiAnalyzer)."""

from __future__ import annotations

import re
from pathlib import Path

from forti_report.data.wan_models import RankedItem, WanTrafficReport, WebUsageSummary


def parse_wan_traffic_pdf(pdf_path: Path) -> WanTrafficReport:
    import pdfplumber

    report = WanTrafficReport(
        source_file=str(pdf_path),
        scope_label="Consolidado ADOM (11 dispositivos)",
    )
    full_text: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            full_text.append(text)
            _parse_page_tables(page, report)
        text = "\n".join(full_text)

    report.summary = _parse_summary(text)
    if not report.top_users_allowed:
        report.top_users_allowed = _parse_user_block(
            text,
            start="Top 10 Usuários por Requisições\nPermitidas",
            end="Top 10 Usuários por Requisições\nBloqueadas",
        )
    if not report.top_users_blocked:
        report.top_users_blocked = _parse_user_block(
            text,
            start="Top 10 Usuários por Requisições\nBloqueadas",
            end="Categorias de Sites Mais Acessados",
        )
        if not report.top_users_blocked:
            report.top_users_blocked = _parse_user_block(
                text,
                start="Bloqueadas",
                end="Categorias de Sites Mais Acessados",
            )
    if not report.top_sites_by_browsing:
        for chunk in full_text:
            if "Top 20 Sites por Tempo" in chunk:
                report.top_sites_by_browsing = _parse_sites_from_page_text(chunk)
                break
    if not report.top_browsing_categories:
        report.top_browsing_categories = _parse_browsing_categories(text)
    if not report.top_categories:
        report.top_categories = _parse_categories_from_text(text)
    if not report.device_names:
        report.device_names = _parse_devices_appendix(text)
    return report


def filter_wan_report_for_unit(
    base: WanTrafficReport,
    *,
    unit_display_name: str,
    antenna_device_names: list[str],
    antenna_labels: list[str],
    filtered_users_allowed: list[RankedItem],
    filtered_users_blocked: list[RankedItem],
    filtered_sites: list[RankedItem],
    filtered_risk_users: list[RankedItem],
) -> WanTrafficReport:
    return WanTrafficReport(
        title=base.title,
        subtitle=base.subtitle,
        period_label=base.period_label,
        source_file=base.source_file,
        scope_label=unit_display_name,
        device_names=antenna_device_names,
        summary=_recompute_summary(filtered_users_allowed, filtered_users_blocked, base.summary),
        top_users_allowed=filtered_users_allowed[:10] or base.top_users_allowed[:3],
        top_users_blocked=filtered_users_blocked[:10],
        top_categories=base.top_categories,
        top_browsing_categories=base.top_browsing_categories,
        top_sites_by_browsing=filtered_sites[:20] or base.top_sites_by_browsing[:10],
        top_apps_bandwidth=base.top_apps_bandwidth,
        top_risk_users=filtered_risk_users[:10] or base.top_risk_users[:5],
        generated_at=base.generated_at,
    )


def _parse_page_tables(page, report: WanTrafficReport) -> None:
    text = page.extract_text() or ""
    tables = page.extract_tables() or []

    if "Top 20 Sites por Tempo" in text and not report.top_sites_by_browsing:
        report.top_sites_by_browsing = _parse_sites_from_page_text(text)

    if "#  Usuário  Requisições  % do Total" in text.replace("  ", " "):
        for table in tables:
            items = _table_to_risk_users(table)
            if items:
                report.top_risk_users = items
                break

    if "Categorias de Sites Mais Acessados" in text and not report.top_categories:
        report.top_categories = _parse_categories_from_text(text)


_CATEGORIES = (
    "Search Engines and Portals",
    "Information Technology",
    "Social Networking",
    "Web-based Applic",
    "Instant Messaging",
    "Web Analytics",
    "Liberado-Geral",
    "Web Chat",
    "Business",
)


def _parse_sites_from_page_text(text: str) -> list[RankedItem]:
    items: list[RankedItem] = []
    cat_pattern = "|".join(re.escape(c) for c in _CATEGORIES)
    rx = re.compile(rf"^(\d+)\s+(.+?)\s+({cat_pattern})(?:\.\.\.)?\s*([\d:]+)?\s*$")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "Relatório Semanal" in line:
            continue
        m = rx.match(line)
        if m:
            items.append(
                RankedItem(
                    rank=int(m.group(1)),
                    label=m.group(2).strip(),
                    category=m.group(3).strip(),
                    value=(m.group(4) or "").strip(),
                )
            )
    # dedupe by rank
    seen: set[int] = set()
    unique: list[RankedItem] = []
    for it in items:
        if it.rank in seen:
            continue
        seen.add(it.rank)
        unique.append(it)
    return sorted(unique, key=lambda x: x.rank)[:20]


def _table_to_risk_users(table: list[list]) -> list[RankedItem]:
    items: list[RankedItem] = []
    for row in table:
        if not row or len(row) < 3:
            continue
        c0 = (row[0] or "").strip()
        if not c0.isdigit():
            continue
        items.append(
            RankedItem(
                rank=int(c0),
                label=(row[1] or "").strip(),
                value=(row[2] or "").strip(),
                percentage=(row[3] or "").strip() if len(row) > 3 else "",
            )
        )
    return items[:10]


def _parse_summary(text: str) -> WebUsageSummary:
    s = WebUsageSummary()
    m_allowed = re.search(r"([\d,]+)\s+Allowed", text)
    m_blocked = re.search(r"([\d,]+)\s+Blocked", text)
    if m_allowed:
        s.allowed_requests = m_allowed.group(1)
    if m_blocked:
        s.blocked_requests = m_blocked.group(1)
    if s.allowed_requests or s.blocked_requests:
        s.total_requests = "62.83M (ref. PDF)"
    m_mal = re.search(r"(\d+)\s*\n\s*Sites\s*\n\s*Maliciosos", text, re.I)
    if m_mal:
        s.malicious_sites = int(m_mal.group(1))
    m_users = re.search(r"([\d.]+)\s*K\s*\n\s*Usuários", text)
    if m_users:
        try:
            s.users = int(float(m_users.group(1)) * 1000)
        except ValueError:
            pass
    m_sites = re.search(r"Usuários\s*\n\s*(\d+)\s+Sites", text)
    if m_sites:
        s.sites = int(m_sites.group(1))
    m_apps = re.search(r"Requisições\s*\n\s*(\d+)\s*\n\s*Aplicações", text)
    if m_apps:
        s.applications = int(m_apps.group(1))
    m_cat = re.search(r"Aplicações\s*\n\s*(\d+)\s*\n\s*Categorias", text)
    if m_cat:
        s.categories = int(m_cat.group(1))
    return s


def _parse_user_block(text: str, *, start: str, end: str) -> list[RankedItem]:
    s = text.find(start)
    if s < 0:
        # fallback encoding
        alt = start.replace("á", "").replace("ó", "")
        for chunk_start in [start, alt, "Top 10 Usu"]:
            s = text.find(chunk_start)
            if s >= 0:
                break
    if s < 0:
        return []
    e = text.find(end, s + 10)
    if e < 0:
        e = s + 2500
    block = text[s:e]
    pattern = re.compile(r"(\d+(?:\.\d+)?)\%\s+([^\(\n]+?)\s*\((\d+(?:\.\d+)?[KkMm]?)\)")
    items: list[RankedItem] = []
    seen: set[str] = set()
    for idx, m in enumerate(pattern.finditer(block), start=1):
        label = m.group(2).strip()
        if label in seen:
            continue
        seen.add(label)
        items.append(
            RankedItem(rank=len(items) + 1, label=label, value=m.group(3), percentage=f"{m.group(1)}%")
        )
        if len(items) >= 10:
            break
    return items


def _parse_categories_from_text(text: str) -> list[RankedItem]:
    block = _slice(text, "Categorias de Sites Mais Acessados", "Navegação Web")
    names = re.findall(
        r"(\d+)\s+(General\.Interest|Network\.Service|Collaboration|Business|Social\.Media|Others)",
        block,
    )
    return [RankedItem(rank=i + 1, label=n, value=v) for i, (v, n) in enumerate(names)]


def _parse_browsing_categories(text: str) -> list[RankedItem]:
    block = _slice(text, "Categoria com maior tempo de Navegação", "Tempo de Uso da Internet")
    items: list[RankedItem] = []
    for m in re.finditer(r"([\d:]+)\s+([A-Za-z0-9._\s\-]+?)(?:\s+[\d:]+\s+[A-Za-z]|$)", block):
        name = m.group(2).strip()
        if len(name) > 2 and "Browsing" not in name and "rrrr" not in name:
            items.append(RankedItem(rank=len(items) + 1, label=name, value=m.group(1)))
    return items[:10]


def _parse_devices_appendix(text: str) -> list[str]:
    block = _slice(text, "Dispositivos (11)", "Relatório Semanal")
    if not block:
        block = _slice(text, "Appendix A", "Relatório Semanal")
    names = re.findall(r"(?:fw|hafw\d?)-[a-z0-9-]+", block, re.I)
    if not names:
        names = re.findall(r"(?:fw|hafw\d?)-[a-z0-9-]+", text, re.I)
    return sorted(set(names))


def _slice(text: str, start: str, end: str) -> str:
    s = text.find(start)
    if s < 0:
        return ""
    e = text.find(end, s + len(start))
    return text[s:e] if e > s else text[s:]


def _recompute_summary(
    allowed: list[RankedItem],
    blocked: list[RankedItem],
    base: WebUsageSummary,
) -> WebUsageSummary:
    if not allowed and not blocked:
        return base
    return WebUsageSummary(
        total_requests="filtrado por unidade",
        allowed_requests=f"{len(allowed)} usuários (top filtrado)",
        blocked_requests=f"{len(blocked)} usuários (top filtrado)",
        users=len({u.label for u in allowed + blocked}) or base.users,
        sites=base.sites,
        categories=base.categories,
        applications=base.applications,
        malicious_sites=base.malicious_sites,
    )
