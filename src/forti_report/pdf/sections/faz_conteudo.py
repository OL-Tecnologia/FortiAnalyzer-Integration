"""Inventário FAZ — preferência por gráficos; tabelas só como fallback técnico."""

from __future__ import annotations

import re

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer

from forti_report.charts.plotly_charts import (
    chart_to_png_bytes,
    create_bar_chart,
    create_donut_chart,
)
from forti_report.data.mensal_models import FazChartRecord, MensalGeralReport
from forti_report.data.parsers.mensal_utils import pie_values_from_items
from forti_report.data.wan_models import RankedItem
from forti_report.pdf.chart_utils import (
    BAR_MAX_HEIGHT,
    DONUT_MAX_HEIGHT,
    append_chart_with_gap,
)
from forti_report.pdf.kpi_cards import kpi_cards_table
from forti_report.pdf.mensal_toc import section_anchor
from forti_report.pdf.table_utils import data_table

_SECTION_GAP = 0.12 * cm
_MAX_CHART_PREVIEWS = 18
_MAX_PREVIEW_ROWS = 10
_BLOCKED_COLOR = "#E63946"


def build_faz_conteudo_flowables(
    mensal: MensalGeralReport,
    *,
    width: float,
    styles,
    anchor_prefix: str = "",
    charts_enabled: bool = True,
    chart_scope: str | None = None,
) -> list:
    """
    Inventário do export FAZ com gráficos (barras/donuts) no lugar de planilhas.
    Por padrão o PDF do cliente NÃO inclui esta seção (unified_mensal_builder).
    """
    titles = mensal.faz_section_titles
    charts = mensal.faz_charts
    macros = mensal.macros

    if not titles and not charts and not macros:
        return []

    source = (mensal.content_source or "export").upper()
    body = ParagraphStyle(
        "FazBody",
        parent=styles["Normal"],
        fontSize=8,
        leading=11,
        spaceAfter=3,
    )

    flow: list = [
        *section_anchor(f"{anchor_prefix}faz-conteudo"),
        Spacer(1, _SECTION_GAP),
        Paragraph("Referência — Conteúdo FortiAnalyzer (FAZ)", styles["Heading2"]),
        Paragraph(
            "Widgets e rankings exportados pelo FortiAnalyzer, apresentados em gráficos "
            f"para leitura rápida. Fonte: <b>{source}</b>.",
            body,
        ),
    ]

    macro_items = [(k, v) for k, v in sorted(macros.items()) if k and v]
    for rec in charts:
        if rec.chart_type == "macro" and len(rec.preview_rows) == 1:
            row = rec.preview_rows[0]
            if len(row) >= 2 and (row[0], row[1]) not in macro_items:
                macro_items.append((row[0], row[1]))
    if macro_items:
        cards = kpi_cards_table(macro_items[:9], width, cols=3)
        if cards:
            flow.append(Spacer(1, 0.1 * cm))
            flow.append(Paragraph("Widgets / macros", styles["Heading3"]))
            flow.append(cards)

    chart_records = [c for c in charts if c.chart_type != "macro" or c.row_count > 0]
    unmapped = [c for c in chart_records if not c.rendered_in_pdf or c.mapped_field == "unmapped"]
    to_show = unmapped + [c for c in chart_records if c.rendered_in_pdf and c.mapped_field != "unmapped"]
    seen: set[str] = set()
    ordered: list[FazChartRecord] = []
    for rec in to_show:
        key = rec.title.strip().lower()
        if key in seen or rec.chart_type == "macro":
            continue
        seen.add(key)
        ordered.append(rec)
        if len(ordered) >= _MAX_CHART_PREVIEWS:
            break

    for idx, rec in enumerate(ordered):
        items = ranked_items_from_preview(rec.preview_rows)
        flow.append(Spacer(1, 0.12 * cm))
        flow.append(Paragraph(f"<b>{rec.title}</b>", styles["Heading3"]))

        charted = False
        if charts_enabled and len(items) >= 2:
            use_donut = _prefer_donut(rec.title)
            try:
                if use_donut:
                    labels, values = pie_values_from_items(items, max_items=8)
                    fig = create_donut_chart(labels, values, title=rec.title[:60])
                else:
                    color = _BLOCKED_COLOR if _is_blocked_title(rec.title) else None
                    fig = create_bar_chart(
                        items,
                        title=rec.title[:60],
                        value_label=_value_label(rec.title),
                        max_items=_MAX_PREVIEW_ROWS,
                        color=color,
                    )
                if fig:
                    png = chart_to_png_bytes(
                        fig,
                        cache_key=f"faz-preview:{anchor_prefix}:{idx}:{rec.title[:40]}",
                        cache_scope=chart_scope,
                    )
                    append_chart_with_gap(
                        flow,
                        png,
                        max_width=width,
                        max_height=DONUT_MAX_HEIGHT if use_donut else BAR_MAX_HEIGHT,
                    )
                    charted = True
            except Exception:
                charted = False

        if not charted and rec.preview_rows:
            # Fallback mínimo — só se não deu para plotar
            preview_table = [["#", "Item", "Valor"]]
            for i, item in enumerate(items[:_MAX_PREVIEW_ROWS], start=1):
                preview_table.append([str(i), item.label, item.value or "—"])
            if len(preview_table) == 1:
                for row in rec.preview_rows[:5]:
                    preview_table.append(["", " · ".join(cell for cell in row if cell), ""])
            flow.append(
                data_table(
                    preview_table,
                    width,
                    min_widths=[0.8 * cm, 8 * cm, 3 * cm],
                    font_size=7,
                    header_font_size=8,
                    nowrap_cols=frozenset({0, 2}),
                    stretch_col=1,
                )
            )

    return flow


def ranked_items_from_preview(preview_rows: list[list[str]]) -> list[RankedItem]:
    """Converte linhas 'User: x · Requests: y · % do Total: z' em RankedItem."""
    items: list[RankedItem] = []
    for idx, row in enumerate(preview_rows or [], start=1):
        if not row:
            continue
        if len(row) == 2 and not any(":" in c for c in row):
            items.append(RankedItem(rank=idx, label=row[0], value=row[1]))
            continue

        fields: dict[str, str] = {}
        for cell in row:
            for part in re.split(r"\s*·\s*", cell):
                if ":" in part:
                    key, _, val = part.partition(":")
                    fields[key.strip().lower()] = val.strip()

        label = (
            fields.get("user")
            or fields.get("usuário")
            or fields.get("usuario")
            or fields.get("site")
            or fields.get("sites")
            or fields.get("category")
            or fields.get("categoria")
            or fields.get("application")
            or fields.get("aplicação")
            or fields.get("aplicacao")
            or fields.get("policy")
            or fields.get("política")
            or fields.get("politica")
            or fields.get("name")
            or (row[0].split(":", 1)[-1].strip() if row else "")
        )
        value = (
            fields.get("requests")
            or fields.get("requisições")
            or fields.get("requisicoes")
            or fields.get("count")
            or fields.get("bytes")
            or fields.get("banda")
            or fields.get("bandwidth")
            or fields.get("sessions")
            or fields.get("sessões")
            or fields.get("time")
            or fields.get("tempo")
            or (row[1] if len(row) > 1 and ":" not in row[1] else "")
        )
        pct = fields.get("% do total") or fields.get("% do subtotal") or fields.get("%") or ""
        if pct and not pct.endswith("%"):
            pct = f"{pct}%"
        if label:
            items.append(
                RankedItem(rank=idx, label=label, value=value or pct or "0", percentage=pct)
            )
    return items


def _prefer_donut(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in ("distribui", "visibil", "aplicativ", "sd-wan", "categoria"))


def _is_blocked_title(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in ("bloque", "risco", "phishing", "malicio"))


def _value_label(title: str) -> str:
    t = title.lower()
    if "banda" in t or "byte" in t or "tráfego" in t or "trafego" in t:
        return "Banda"
    if "tempo" in t or "naveg" in t:
        return "Tempo"
    if "sess" in t:
        return "Sessões"
    return "Requisições"
