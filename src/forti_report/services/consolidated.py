"""PDF consolidado de um ciclo a partir dos JSON já colhidos no FortiAnalyzer."""

from __future__ import annotations

import base64
import json
import re
from io import BytesIO
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Flowable,
    Frame,
    Image,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from forti_report.config import Settings
from forti_report.data.harvest_catalog import HarvestLayout, layouts_for
from forti_report.pdf.cover_page import build_mensal_cover_flowables
from forti_report.pdf.internal_page import (
    draw_internal_page_footer,
    draw_internal_page_header,
    internal_footer_height,
    internal_header_height,
    prewarm_header_logo,
)
from forti_report.pdf.page_layout import LATERAL_MARGIN
from forti_report.services.cycle_schedule import (
    CYCLE_TITLES,
    closed_through,
    completed_week,
    previous_month,
)
_SERIES_KINDS = {"line", "area"}
_CONTENT_WIDTH = A4[0] - 2 * LATERAL_MARGIN
_FOOTER_LABEL = {
    "diario": "RELATORIO DIARIO",
    "semanal": "RELATORIO SEMANAL",
    "mensal": "RELATORIO MENSAL",
}
_MONTHS_PT = (
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
)
_FULL_TABLE_ROWS = 150
_DATE_IN_TEXT = re.compile(r"(\d{4})[/-](\d{2})[/-](\d{2})")
_HEADER_PT = {
    "user": "Usuário",
    "device": "Equipamento",
    "device name": "Equipamento",
    "nome do dispositivo": "Equipamento",
    "date/time": "Data",
    "time": "Hora",
    "user interface": "Origem",
    "action performed": "Ação",
    "requests": "Requisições",
    "categories": "Categoria",
    "category": "Categoria",
    "sites": "Site",
    "application": "Aplicação",
    "application name": "Aplicação",
    "browsing time": "Tempo de navegação",
    "browsing time (hh:mm:ss)": "Tempo de navegação",
    "% do total": "% do total",
    "% do subtotal": "% do subtotal",
}
_KPI_PT = {
    "web usage request count": "Requisições web",
    "web usage application count": "Aplicações",
    "web usage category count": "Categorias",
    "web usage user count": "Usuários",
    "web usage total malicious websites count": "Sites maliciosos",
}


@dataclass(frozen=True)
class HarvestItemRef:
    cycle: str
    prefix: str
    device: str
    period_end: date | None
    path: str
    name: str


@dataclass
class ChartTable:
    title: str
    kind: str
    headers: list[str]
    rows: list[list[str]]
    total_rows: int


def harvest_root(settings: Settings) -> Path:
    return settings.output_dir / "colheita"


def load_harvest_items(settings: Settings) -> list[HarvestItemRef]:
    index_path = harvest_root(settings) / "index.json"
    if not index_path.is_file():
        return []
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    items: list[HarvestItemRef] = []
    for raw in payload.get("items") or []:
        if not isinstance(raw, dict):
            continue
        items.append(
            HarvestItemRef(
                cycle=str(raw.get("cycle") or ""),
                prefix=str(raw.get("prefix") or ""),
                device=str(raw.get("device") or ""),
                period_end=_parse_date(str(raw.get("period_end") or raw.get("name") or "")),
                path=str(raw.get("path") or ""),
                name=str(raw.get("name") or ""),
            )
        )
    return items


def select_for_cycle(
    items: list[HarvestItemRef],
    cycle: str,
    when: datetime,
) -> tuple[list[tuple[HarvestLayout, HarvestItemRef | None]], list[HarvestItemRef]]:
    """Um arquivo por layout do ciclo, mais os diários da semana quando o ciclo é semanal."""
    limit = _content_limit(cycle, when)
    chosen: list[tuple[HarvestLayout, HarvestItemRef | None]] = []
    for layout in layouts_for(cycle):
        pool = [
            item
            for item in items
            if item.prefix == layout.prefix and item.period_end is not None and item.period_end <= limit
        ]
        pool.sort(key=lambda item: item.period_end or date.min, reverse=True)
        chosen.append((layout, pool[0] if pool else None))
    dailies: list[HarvestItemRef] = []
    if cycle == "semanal":
        start, end = completed_week(when)
        dailies = [
            item
            for item in items
            if item.cycle == "diario"
            and item.period_end is not None
            and start <= item.period_end <= end
        ]
        dailies.sort(key=lambda item: item.period_end or date.min)
    return chosen, dailies


def generate_consolidated(
    settings: Settings,
    cycle: str,
    *,
    when: datetime,
    refresh: bool = False,
) -> Path:
    """Monta o PDF do ciclo. `refresh` baixa de novo os 10 layouts antes de ler o índice."""
    if cycle not in CYCLE_TITLES:
        raise ValueError(f"ciclo desconhecido: {cycle}")
    if refresh:
        _refresh_harvest(settings)
    items = load_harvest_items(settings)
    layouts, dailies = select_for_cycle(items, cycle, when)
    path = _output_path(settings, cycle, when)
    _write_pdf(path, settings, cycle, when, layouts, dailies)
    return path


def read_chart_tables(path: Path) -> list[ChartTable]:
    """Gráficos com todas as linhas. A série temporal vira resumo na montagem do PDF."""
    _kpis, tables = read_report(path)
    return tables


def read_report(path: Path) -> tuple[list[tuple[str, str]], list[ChartTable]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    root = payload.get("fortianalyzer-report") if isinstance(payload, dict) else None
    charts = root.get("charts") if isinstance(root, dict) else None
    if not isinstance(charts, list):
        return [], []
    kpis: list[tuple[str, str]] = []
    tables: list[ChartTable] = []
    for chart in charts:
        if not isinstance(chart, dict):
            continue
        kind = str(chart.get("type") or "table")
        raw_title = _text(chart.get("name") or chart.get("title") or "")
        title = _label(raw_title)
        if kind == "macro":
            value = _text(chart.get("value")).strip()
            if raw_title and value:
                kpis.append((_kpi_name(raw_title), value))
            continue
        headers, rows = _rows_of(chart.get("rows") or [])
        headers, rows = _dedupe_columns(headers, rows)
        tables.append(
            ChartTable(
                title=title or "Gráfico",
                kind=kind,
                headers=headers,
                rows=rows,
                total_rows=len(rows),
            )
        )
    return kpis, tables


def _content_limit(cycle: str, when: datetime) -> date:
    if cycle == "diario":
        return closed_through(when)
    if cycle == "semanal":
        return completed_week(when)[1]
    return previous_month(when)[1] if when.day == 1 else closed_through(when)


def _refresh_harvest(settings: Settings) -> None:
    from forti_report.services.harvest import harvest_reports

    harvest_reports(settings, days=90)


def _output_path(settings: Settings, cycle: str, when: datetime) -> Path:
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    if cycle == "semanal":
        start, _end = completed_week(when)
        stamp = start.isoformat()
    elif cycle == "mensal":
        stamp = when.strftime("%Y-%m")
    else:
        stamp = closed_through(when).isoformat()
    return settings.output_dir / f"{cycle.upper()}_UNIFICADO_{stamp}.pdf"


def _write_pdf(
    path: Path,
    settings: Settings,
    cycle: str,
    when: datetime,
    layouts: list[tuple[HarvestLayout, HarvestItemRef | None]],
    dailies: list[HarvestItemRef],
) -> None:
    styles = _styles()
    root = harvest_root(settings)
    bounds = _analysis_bounds(root, layouts)
    period = _period_label(cycle, when, bounds)
    entries: list[_Outline] = []
    content: list[Any] = []
    present, missing = _split_layouts(root, layouts)
    if missing:
        _mark(entries, content, "Layouts ainda não gerados pelo FortiAnalyzer", 0)
        content.append(Paragraph("Layouts ainda não gerados pelo FortiAnalyzer", styles["section"]))
        for layout in missing:
            _mark(entries, content, layout.prefix, 1)
            content.append(Paragraph(_escape(layout.prefix), styles["chart"]))
            content.append(Paragraph("O FortiAnalyzer ainda não gerou este layout.", styles["note"]))
        if present or (cycle == "semanal" and dailies):
            content.append(PageBreak())
    for index, (layout, item) in enumerate(present):
        if index:
            content.append(PageBreak())
        _mark(entries, content, layout.prefix, 0)
        content.append(Paragraph(layout.prefix, styles["section"]))
        content.append(Paragraph(_file_caption(item), styles["meta"]))
        kpis, tables = read_report(root / item.path)
        content.extend(
            _chart_flow(
                kpis,
                tables,
                styles,
                entries,
                skip_config=cycle == "semanal",
            )
        )
    if cycle == "semanal":
        content.append(PageBreak())
        content.extend(_daily_summary(root, dailies, bounds, styles, entries))
    doc = _ConsolidatedDoc(str(path), settings=settings, cycle=cycle)
    story: list[Any] = [
        _PageTotal(doc),
        *build_mensal_cover_flowables(
            settings,
            adom=settings.faz_adom,
            regional_units=0,
            antennas=0,
            when=when,
            title=CYCLE_TITLES[cycle],
            detail=_device_line(layouts),
            period_label=period,
        ),
        NextPageTemplate("internal"),
        PageBreak(),
        Paragraph("Sumário", styles["section"]),
        Paragraph(_subtitle(settings, period), styles["meta"]),
        Spacer(1, 0.2 * cm),
        *[_TocLine(entry) for entry in entries],
        PageBreak(),
        *content,
    ]
    doc.multiBuild(story)


@dataclass
class _Outline:
    title: str
    level: int
    page: int = 0


class _TocMark(Flowable):
    def __init__(self, entry: _Outline):
        super().__init__()
        self.entry = entry

    def wrap(self, availWidth, availHeight):  # noqa: N803
        return 0, 0

    def draw(self) -> None:
        self.entry.page = int(self.canv.getPageNumber())


class _TocLine(Flowable):
    def __init__(self, entry: _Outline):
        super().__init__()
        self.entry = entry

    def wrap(self, availWidth, availHeight):  # noqa: N803
        self.width = availWidth
        return availWidth, 12

    def draw(self) -> None:
        indent = 14 * self.entry.level
        font = "Helvetica-Bold" if self.entry.level == 0 else "Helvetica"
        self.canv.setFont(font, 8)
        self.canv.setFillColor(colors.HexColor("#1f4e79" if self.entry.level == 0 else "#333333"))
        title = self.entry.title if len(self.entry.title) <= 78 else self.entry.title[:75] + "..."
        self.canv.drawString(indent, 2, title)
        page = str(self.entry.page) if self.entry.page else "—"
        self.canv.drawRightString(self.width, 2, page)


def _mark(entries: list[_Outline], content: list[Any], title: str, level: int) -> None:
    entry = _Outline(title, level, 0)
    entries.append(entry)
    content.append(_TocMark(entry))


class _PageTotal(Flowable):
    """Faz o ReportLab dar uma segunda passada para o rodapé saber o total."""

    def __init__(self, doc: _ConsolidatedDoc):
        super().__init__()
        self._doc = doc
        self._passes = 0

    def isIndexing(self) -> int:
        return 1

    def isSatisfied(self) -> bool:
        return self._passes >= 2

    def beforeBuild(self) -> None:
        return None

    def afterBuild(self) -> None:
        self._passes += 1

    def wrap(self, availWidth, availHeight):  # noqa: N803
        return 0, 0

    def draw(self) -> None:
        return None


class _ConsolidatedDoc(BaseDocTemplate):
    def __init__(self, filename: str, *, settings: Settings, cycle: str):
        page_w, page_h = A4
        super().__init__(filename, pagesize=A4, title=CYCLE_TITLES[cycle])
        self.settings = settings
        self.cycle = cycle
        self._header_h = internal_header_height(settings, page_w)
        self._footer_h = internal_footer_height()
        self._total_pages = 0
        prewarm_header_logo(settings, header_h=self._header_h)
        cover = Frame(
            0,
            0,
            page_w,
            page_h,
            id="cover",
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        )
        body = Frame(
            LATERAL_MARGIN,
            self._footer_h + 0.35 * cm,
            _CONTENT_WIDTH,
            page_h - self._header_h - self._footer_h - 0.7 * cm,
            id="body",
        )
        self.addPageTemplates(
            [
                PageTemplate(id="cover", frames=[cover]),
                PageTemplate(id="internal", frames=[body], onPage=self._on_page),
            ]
        )

    def afterPage(self) -> None:
        self._total_pages = max(self._total_pages, self.page)

    def _on_page(self, canvas, doc) -> None:
        canvas.saveState()
        draw_internal_page_header(canvas, self.settings, header_h=self._header_h)
        draw_internal_page_footer(
            canvas,
            adom=self.settings.faz_adom,
            page_num=doc.page,
            total_pages=self._total_pages or doc.page,
            footer_h=self._footer_h,
            display_name=(self.settings.client_display_name or "").strip(),
            report_label=_FOOTER_LABEL[self.cycle],
        )
        canvas.restoreState()


def _device_line(layouts: list[tuple[HarvestLayout, HarvestItemRef | None]]) -> str:
    devices = {item.device for _layout, item in layouts if item and item.device}
    count = len(devices)
    if count == 0:
        return "Nenhum dispositivo neste período"
    if count == 1:
        return "1 dispositivo"
    return f"{count} dispositivos"


def _split_layouts(
    root: Path,
    layouts: list[tuple[HarvestLayout, HarvestItemRef | None]],
) -> tuple[list[tuple[HarvestLayout, HarvestItemRef]], list[HarvestLayout]]:
    present: list[tuple[HarvestLayout, HarvestItemRef]] = []
    missing: list[HarvestLayout] = []
    for layout, item in layouts:
        if item is not None and (root / item.path).is_file():
            present.append((layout, item))
        else:
            missing.append(layout)
    return present, missing


def _analysis_bounds(
    root: Path,
    layouts: list[tuple[HarvestLayout, HarvestItemRef | None]],
) -> tuple[date | None, date | None]:
    starts: list[date] = []
    ends: list[date] = []
    zone = ZoneInfo("America/Sao_Paulo")
    for _layout, item in layouts:
        if item is None or not (root / item.path).is_file():
            continue
        if item.period_end is not None:
            ends.append(item.period_end)
        _kpis, tables = read_report(root / item.path)
        for table in tables:
            if table.kind not in _SERIES_KINDS:
                continue
            stamps = [int(row[0]) for row in table.rows if row and re.fullmatch(r"\d{10}", row[0].strip())]
            if len(stamps) < 2:
                continue
            starts.append(datetime.fromtimestamp(min(stamps), zone).date())
            ends.append(datetime.fromtimestamp(max(stamps), zone).date())
    if not starts and not ends:
        return None, None
    start = min(starts) if starts else min(ends)
    return start, max(ends)


def _period_label(cycle: str, when: datetime, bounds: tuple[date | None, date | None]) -> str:
    start, end = bounds
    if start and end:
        if start == end:
            return start.strftime("%d/%m/%Y")
        return f"{start.strftime('%d/%m/%Y')} a {end.strftime('%d/%m/%Y')}"
    if cycle == "diario":
        return closed_through(when).strftime("%d/%m/%Y")
    if cycle == "semanal":
        week_start, week_end = completed_week(when)
        return f"{week_start.strftime('%d/%m/%Y')} a {week_end.strftime('%d/%m/%Y')}"
    month_start = previous_month(when)[0] if when.day == 1 else when.date().replace(day=1)
    return f"{_MONTHS_PT[month_start.month - 1]}/{month_start.year}"


def _daily_summary(
    root: Path,
    dailies: list[HarvestItemRef],
    bounds: tuple[date | None, date | None],
    styles: dict,
    entries: list[_Outline],
) -> list[Any]:
    start, end = bounds
    chosen = _one_daily_per_day(dailies, root)
    if start and end:
        chosen = [item for item in chosen if item.period_end and start <= item.period_end <= end]
    window = _period_label("semanal", datetime.now(ZoneInfo("America/Sao_Paulo")), bounds)
    flow: list[Any] = []
    _mark(entries, flow, "Alterações do diário no período", 0)
    flow.append(Paragraph("Alterações do diário no período", styles["section"]))
    flow.append(Paragraph(window, styles["meta"]))
    if not chosen:
        flow.append(Paragraph("Nenhum diário desta semana foi colhido.", styles["note"]))
        return flow
    for item in chosen:
        day = item.period_end.strftime("%d/%m/%Y") if item.period_end else "sem data"
        _mark(entries, flow, day, 1)
        flow.append(Paragraph(day, styles["chart"]))
        file_path = root / item.path
        if not file_path.is_file():
            flow.append(Paragraph("Arquivo não encontrado.", styles["note"]))
            continue
        _kpis, tables = read_report(file_path)
        filled = [table for table in tables if table.rows]
        if not filled:
            flow.append(Paragraph("Sem alterações neste dia.", styles["note"]))
            continue
        for table in filled:
            flow.extend(_grid(table.headers, table.rows, styles))
    return flow


def _one_daily_per_day(dailies: list[HarvestItemRef], root: Path) -> list[HarvestItemRef]:
    best: dict[date, HarvestItemRef] = {}
    for item in dailies:
        if item.period_end is None:
            continue
        current = best.get(item.period_end)
        if current is None or _row_count(root / item.path) > _row_count(root / current.path):
            best[item.period_end] = item
    return [best[day] for day in sorted(best)]


def _row_count(path: Path) -> int:
    if not path.is_file():
        return 0
    return sum(table.total_rows for table in read_chart_tables(path))


def _chart_flow(
    kpis: list[tuple[str, str]],
    tables: list[ChartTable],
    styles: dict,
    entries: list[_Outline],
    *,
    skip_config: bool = False,
) -> list[Any]:
    flow: list[Any] = []
    table_titles = {table.title for table in tables if table.kind == "table" and table.rows}
    if kpis:
        _mark(entries, flow, "Indicadores", 1)
        flow.append(Paragraph("Indicadores", styles["chart"]))
        flow.extend(_grid(["Indicador", "Valor"], [[name, value] for name, value in kpis], styles))
    empties: list[str] = []
    shown = False
    for table in tables:
        if not table.rows:
            if table.title:
                empties.append(table.title)
            continue
        if skip_config and _is_config_change(table.title):
            continue
        if table.kind == "bubble" and table.title in table_titles:
            continue
        shown = True
        title = Paragraph(_escape(table.title), styles["chart"])
        image = _chart_image(table)
        if image is not None:
            flow.append(CondPageBreak(7 * cm))
            _mark(entries, flow, table.title, 1)
            flow.append(KeepTogether([title, image, Spacer(1, 0.3 * cm)]))
            continue
        flow.append(CondPageBreak(4 * cm))
        _mark(entries, flow, table.title, 1)
        flow.append(title)
        if _is_series(table):
            start, end = _series_span(table)
            if start and end:
                flow.append(Paragraph(f"Série de {start} a {end}.", styles["meta"]))
            summary = _series_summary(table)
            flow.extend(_grid(["Série", "Mínimo", "Máximo", "Último"], summary, styles))
            continue
        rows = table.rows
        if len(rows) > _FULL_TABLE_ROWS:
            rows = rows[:_FULL_TABLE_ROWS]
        flow.extend(_grid(table.headers, rows, styles))
        if len(table.rows) > len(rows):
            flow.append(Paragraph(f"{len(rows)} de {len(table.rows)} linhas.", styles["note"]))
    if empties and not shown and any("CONFIGURA" in item.upper() for item in empties):
        flow.append(Paragraph("Sem alterações neste dia.", styles["note"]))
    elif empties:
        flow.append(Paragraph("Sem registros: " + _escape("; ".join(empties)) + ".", styles["note"]))
    if not kpis and not shown and not empties:
        flow.append(Paragraph("O arquivo não trouxe gráficos.", styles["note"]))
    return flow


def _chart_image(table: ChartTable) -> Image | None:
    from forti_report.charts.faz_layout import render_faz_chart

    try:
        rendered = render_faz_chart(table)
    except Exception:
        return None
    if not rendered:
        return None
    png, width, height = rendered
    display_w = _CONTENT_WIDTH * (0.72 if table.kind in {"pie", "bubble-ring"} else 1)
    display_h = display_w * (height / width)
    image = Image(BytesIO(png), width=display_w, height=display_h)
    image.hAlign = "CENTER"
    return image


def _is_series(table: ChartTable) -> bool:
    return table.kind in _SERIES_KINDS and table.total_rows > 12


def _series_span(table: ChartTable) -> tuple[str, str]:
    stamps = [_as_timestamp(row[0]) for row in table.rows if row]
    stamps = [item for item in stamps if item]
    if len(stamps) < 2:
        return "", ""
    return _fmt_ts(stamps[0]), _fmt_ts(stamps[-1])


def _series_summary(table: ChartTable) -> list[list[str]]:
    headers = table.headers[1:] or table.headers
    summary: list[tuple[float, list[str]]] = []
    for index, name in enumerate(headers):
        column = index + 1 if table.headers[1:] else index
        numbers: list[float] = []
        last = ""
        for row in table.rows:
            if column >= len(row):
                continue
            last = row[column]
            number = _as_number(last)
            if number is not None:
                numbers.append(number)
        label = name or f"Série {index + 1}"
        if numbers:
            last_number = _as_number(last)
            summary.append(
                (
                    max(numbers),
                    [
                        label,
                        _fmt_number(min(numbers)),
                        _fmt_number(max(numbers)),
                        _fmt_number(last_number if last_number is not None else numbers[-1]),
                    ],
                )
            )
        elif last:
            summary.append((0, [label, "—", "—", last]))
    summary.sort(key=lambda item: item[0], reverse=True)
    return [row for _score, row in summary]


def _is_config_change(title: str) -> bool:
    return "CONFIGURA" in title.upper()


def _display_cell(header: str, value: str) -> str:
    if "byte" not in header.lower():
        return value
    number = _as_number(value.replace(" ", ""))
    if number is None or number < 1_000_000 or any(suffix in value.upper() for suffix in ("KB", "MB", "GB", "TB")):
        return value
    return f"{number / 1_000_000_000:.2f} GB"


def _column_widths(headers: list[str], rows: list[list[str]]) -> list[float]:
    count = max(len(headers), 1)
    weights: list[int] = []
    for index, name in enumerate(headers):
        lengths = [len(name)]
        for row in rows[:40]:
            if index < len(row):
                lengths.append(min(len(row[index]), 36))
        weights.append(max(max(lengths), 4))
    total = sum(weights) or 1
    raw = [_CONTENT_WIDTH * weight / total for weight in weights]
    low = _CONTENT_WIDTH / count * 0.62
    high = _CONTENT_WIDTH / count * 2.1
    clamped = [min(high, max(low, width)) for width in raw]
    scale = _CONTENT_WIDTH / sum(clamped)
    return [width * scale for width in clamped]


def _grid(headers: list[str], rows: list[list[str]], styles: dict) -> list[Any]:
    if not headers or not rows:
        return []
    shown = []
    for row in rows:
        shown.append(
            [
                _display_cell(headers[index], row[index] if index < len(row) else "")
                for index in range(len(headers))
            ]
        )
    head = [Paragraph(_escape(name or "—"), styles["head"]) for name in headers]
    body = [[Paragraph(_escape(cell), styles["cell"]) for cell in row] for row in shown]
    grid = Table([head, *body], colWidths=_column_widths(headers, shown), repeatRows=1)
    grid.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d0d7de")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return [grid, Spacer(1, 0.25 * cm)]


def _styles() -> dict[str, ParagraphStyle]:
    return {
        "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=16, textColor=colors.HexColor("#1f4e79"), spaceAfter=6),
        "section": ParagraphStyle("section", fontName="Helvetica-Bold", fontSize=12, textColor=colors.HexColor("#1f4e79"), spaceBefore=12, spaceAfter=4),
        "chart": ParagraphStyle("chart", fontName="Helvetica-Bold", fontSize=9, spaceBefore=8, spaceAfter=3),
        "meta": ParagraphStyle("meta", fontName="Helvetica", fontSize=9, textColor=colors.HexColor("#444444"), spaceAfter=2),
        "body": ParagraphStyle("body", fontName="Helvetica", fontSize=9, spaceAfter=2),
        "note": ParagraphStyle("note", fontName="Helvetica-Oblique", fontSize=9, textColor=colors.HexColor("#666666"), spaceAfter=4),
        "head": ParagraphStyle("head", fontName="Helvetica-Bold", fontSize=7, leading=9, textColor=colors.white),
        "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=7, leading=9, textColor=colors.HexColor("#222222")),
    }


def _subtitle(settings: Settings, period: str) -> str:
    client = settings.client_display_name or settings.client_slug or "cliente"
    return _escape(f"{client} · ADOM {settings.faz_adom or '-'} · {period}")


def _file_caption(item: HarvestItemRef) -> str:
    period = item.period_end.strftime("%d/%m/%Y") if item.period_end else "sem data"
    return _escape(f"{item.device} · período até {period}")


def _rows_of(raw_rows: list[Any]) -> tuple[list[str], list[list[str]]]:
    parsed: list[list[tuple[str, str]]] = []
    for raw in raw_rows:
        if not isinstance(raw, dict):
            continue
        pairs = [_cell(col) for col in raw.get("cols") or [] if isinstance(col, dict)]
        pairs = _collapse_repeated_names(pairs)
        if pairs:
            parsed.append(pairs)
    if not parsed:
        return [], []
    if any(not name for pairs in parsed for name, _value in pairs):
        width = max(len(pairs) for pairs in parsed)
        headers = [""] * width
        for pairs in parsed:
            for index, (name, _value) in enumerate(pairs):
                if name and not headers[index]:
                    headers[index] = name
        rows = [([value for _name, value in pairs] + [""] * width)[:width] for pairs in parsed]
        return headers, rows
    headers: list[str] = []
    for pairs in parsed:
        for name, _value in pairs:
            if name not in headers:
                headers.append(name)
    rows = []
    for pairs in parsed:
        by_name: dict[str, str] = {}
        for name, value in pairs:
            if value or name not in by_name:
                by_name[name] = value
        rows.append([by_name.get(name, "") for name in headers])
    return headers, rows


def _cell(col: dict) -> tuple[str, str]:
    value = _text(col.get("value")).strip()
    if not value:
        value = _merged_display(col.get("merged-cols"))
    return _label(_text(col.get("name"))), value


def _merged_display(merged: object) -> str:
    if not isinstance(merged, list):
        return ""
    texts = [_text(item.get("value")).strip() for item in merged if isinstance(item, dict)]
    texts = [item for item in texts if item]
    for item in texts:
        if ":" in item:
            return item
    return texts[0] if texts else ""


def _collapse_repeated_names(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    folded: list[tuple[str, str]] = []
    for name, value in pairs:
        if name and folded and folded[-1][0] == name:
            if value:
                folded[-1] = (name, value)
            continue
        folded.append((name, value))
    return folded


def _text(value: object) -> str:
    if value is None:
        return ""
    raw = str(value).strip()
    if re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", raw) and ("=" in raw or len(raw) > 16):
        try:
            decoded = base64.b64decode(raw).decode("utf-8").strip()
        except Exception:
            decoded = ""
        if decoded and sum(ch.isprintable() for ch in decoded) / len(decoded) > 0.85:
            return decoded
    return raw


def _label(value: str) -> str:
    key = re.sub(r"\s+", " ", value).strip().lower()
    return _HEADER_PT.get(key, value.strip())


def _kpi_name(value: str) -> str:
    key = re.sub(r"\s+", " ", value).strip().lower()
    return _KPI_PT.get(key, value.strip())


def _dedupe_columns(
    headers: list[str], rows: list[list[str]]
) -> tuple[list[str], list[list[str]]]:
    keep: list[int] = []
    seen: set[str] = set()
    for index, name in enumerate(headers):
        key = name.strip().lower()
        if index == 0:
            keep.append(index)
            if key:
                seen.add(key)
            continue
        if not key or key in seen:
            continue
        seen.add(key)
        keep.append(index)
    if len(keep) == len(headers):
        return headers, rows
    return (
        [headers[index] for index in keep],
        [[row[index] if index < len(row) else "" for index in keep] for row in rows],
    )


def _as_timestamp(value: str) -> str:
    return value if re.fullmatch(r"\d{10}", value.strip()) else ""


def _fmt_ts(value: str) -> str:
    moment = datetime.fromtimestamp(int(value), ZoneInfo("America/Sao_Paulo"))
    return moment.strftime("%d/%m %H:%M")


def _as_number(value: str) -> float | None:
    text = value.strip().replace("%", "").replace(",", "").replace(" ", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _fmt_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.1f}"


def _parse_date(value: str) -> date | None:
    match = _DATE_IN_TEXT.search(value)
    if not match:
        return None
    return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))


def _escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

