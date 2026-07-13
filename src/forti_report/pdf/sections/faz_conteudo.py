"""Seção Referência FAZ — títulos de layout, widgets e prévia textual de gráficos."""

from __future__ import annotations

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer

from forti_report.data.mensal_models import FazChartRecord, MensalGeralReport
from forti_report.pdf.mensal_toc import section_anchor
from forti_report.pdf.table_utils import data_table

_SECTION_GAP = 0.12 * cm
_MAX_CHART_PREVIEWS = 18
_MAX_PREVIEW_ROWS = 5


def build_faz_conteudo_flowables(
    mensal: MensalGeralReport,
    *,
    width: float,
    styles,
    anchor_prefix: str = "",
) -> list:
    """Inventário do export FortiAnalyzer: seções ignoradas + texto de widgets/gráficos."""
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
            "Títulos de seção, widgets e prévia tabular dos gráficos exportados pelo FortiAnalyzer. "
            f"Fonte: <b>{source}</b>. Blocos marcados como «não renderizado» ainda não possuem "
            "seção dedicada no layout Cruz Azul (dados preservados aqui para tomada de decisão).",
            body,
        ),
    ]

    if titles:
        flow.append(Spacer(1, 0.12 * cm))
        flow.append(Paragraph("Títulos de seção identificados no export FAZ", styles["Heading3"]))
        title_rows = [["#", "Título da seção (FAZ)"]]
        for idx, title in enumerate(titles[:40], start=1):
            title_rows.append([str(idx), title])
        flow.append(
            data_table(
                title_rows,
                width,
                min_widths=[0.8 * cm, 12 * cm],
                font_size=7,
                header_font_size=8,
                nowrap_cols=frozenset({0}),
                stretch_col=1,
            )
        )

    macro_rows = [["Widget / macro", "Valor"]]
    for key, val in sorted(macros.items()):
        if key and val:
            macro_rows.append([key, val])
    for rec in charts:
        if rec.chart_type == "macro" and len(rec.preview_rows) == 1:
            row = rec.preview_rows[0]
            if len(row) >= 2 and [row[0], row[1]] not in macro_rows[1:]:
                macro_rows.append([row[0], row[1]])

    if len(macro_rows) > 1:
        flow.append(Spacer(1, 0.12 * cm))
        flow.append(Paragraph("Widgets e macros (texto numérico do FAZ)", styles["Heading3"]))
        flow.append(
            data_table(
                macro_rows,
                width,
                min_widths=[6.5 * cm, 4.5 * cm],
                font_size=7,
                header_font_size=8,
                nowrap_cols=frozenset(),
                stretch_col=0,
            )
        )

    chart_records = [c for c in charts if c.chart_type != "macro" or c.row_count > 0]
    unmapped = [c for c in chart_records if not c.rendered_in_pdf or c.mapped_field == "unmapped"]
    to_show = unmapped + [c for c in chart_records if c.rendered_in_pdf and c.mapped_field != "unmapped"]
    seen: set[str] = set()
    ordered: list[FazChartRecord] = []
    for rec in to_show:
        key = rec.title.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(rec)
        if len(ordered) >= _MAX_CHART_PREVIEWS:
            break

    if ordered:
        flow.append(Spacer(1, 0.12 * cm))
        flow.append(
            Paragraph("Conteúdo textual dos gráficos (prévia tabular)", styles["Heading3"]),
        )
        flow.append(
            Paragraph(
                "Substituto do texto embutido em gráficos/widgets do PDF FAZ quando não há "
                "renderização gráfica equivalente no relatório Cruz Azul.",
                body,
            )
        )

    for rec in ordered:
        status = "renderizado" if rec.rendered_in_pdf else "não renderizado"
        meta = f"{rec.row_count} linha(s) · campo: {rec.mapped_field or '—'} · {status}"
        flow.append(Spacer(1, 0.08 * cm))
        flow.append(Paragraph(f"<b>{rec.title}</b>", styles["Heading4"]))
        flow.append(Paragraph(meta, body))
        if rec.preview_rows:
            preview_table = [["Prévia (texto exportado)"]]
            for row in rec.preview_rows[:_MAX_PREVIEW_ROWS]:
                preview_table.append([" · ".join(cell for cell in row if cell)])
            flow.append(
                data_table(
                    preview_table,
                    width,
                    min_widths=[14 * cm],
                    font_size=6,
                    header_font_size=7,
                    nowrap_cols=frozenset(),
                    stretch_col=0,
                )
            )
        else:
            flow.append(Paragraph("<i>Sem linhas tabulares no export (gráfico puro / widget visual).</i>", body))

    return flow
