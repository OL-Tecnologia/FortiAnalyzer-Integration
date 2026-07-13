"""Testes do inventário FAZ (títulos, widgets, prévia de gráficos)."""

import json

from forti_report.data.parsers.faz_inventory import (
    build_inventory_from_json_charts,
    chart_target_field,
    decode_chart_title,
    extract_pdf_section_headings,
)
from forti_report.data.parsers.mensal_json import parse_mensal_json
from reportlab.lib.styles import getSampleStyleSheet

from forti_report.pdf.sections.faz_conteudo import build_faz_conteudo_flowables


def test_decode_base64_chart_title():
    import base64

    title = "Top 20 Sites por Tempo de Navegação"
    encoded = base64.b64encode(title.encode()).decode()
    decoded = decode_chart_title({"name": encoded})
    assert "Sites" in decoded


def test_build_inventory_from_json():
    payload = {
        "fortianalyzer-report": {
            "charts": [
                {"type": "macro", "name": "Web Usage User Count", "value": "42"},
                {
                    "name": "VG90YWwgZGUgUmVxdWlzacOnw7Vlcw==",
                    "rows": [
                        {
                            "id": "1",
                            "cols": [
                                {"name": "Type", "value": "Allowed"},
                                {"name": "Requests", "value": "100"},
                            ],
                        }
                    ],
                },
                {
                    "name": "Unmapped Custom Chart XYZ",
                    "rows": [
                        {"id": "1", "cols": [{"name": "Foo", "value": "Bar"}]},
                    ],
                },
            ]
        }
    }
    charts = payload["fortianalyzer-report"]["charts"]
    titles, records = build_inventory_from_json_charts(charts)
    assert "Web Usage User Count" in titles
    assert len(records) >= 2
    unmapped = [r for r in records if r.mapped_field == "unmapped"]
    assert unmapped
    assert unmapped[0].preview_rows


def test_parse_mensal_json_populates_faz_inventory():
    payload = {
        "fortianalyzer-report": {
            "charts": [
                {"type": "macro", "name": "SD-WAN Total Bandwidth", "value": "10 GB"},
                {
                    "name": "Total de Requisições",
                    "rows": [
                        {
                            "id": "1",
                            "cols": [
                                {"name": "Type", "value": "Allowed"},
                                {"name": "Requests", "value": "50"},
                            ],
                        }
                    ],
                },
            ]
        }
    }
    report = parse_mensal_json(json.dumps(payload).encode(), device_name="fw-test")
    assert report.content_source == "json"
    assert report.faz_section_titles
    assert report.faz_charts
    assert report.macros.get("SD-WAN Total Bandwidth") == "10 GB"


def test_extract_pdf_section_headings():
    text = """
    Sumário
    Análise Abrangente da Navegação Web da Rede
    RESUMO DE UTILIZAÇÃO WEB
    Top 10 Usuários por Requisições Permitidas
    Aplicações SD-WAN e Consumo de Banda
    """
    headings = extract_pdf_section_headings(text)
    assert any("RESUMO" in h for h in headings)
    assert any("SD-WAN" in h for h in headings)


def test_faz_conteudo_flowables():
    report = parse_mensal_json(
        json.dumps(
            {
                "fortianalyzer-report": {
                    "charts": [
                        {"type": "macro", "name": "Web Usage User Count", "value": "10"},
                        {
                            "name": "Custom Unmapped Section",
                            "rows": [{"id": "1", "cols": [{"name": "A", "value": "1"}]}],
                        },
                    ]
                }
            }
        ).encode(),
        device_name="fw-test",
    )
    styles = getSampleStyleSheet()
    flow = build_faz_conteudo_flowables(report, width=400, styles=styles, anchor_prefix="t-")
    assert len(flow) >= 5
    texts = [getattr(f, "text", "") for f in flow if hasattr(f, "text")]
    assert any("Referência — Conteúdo FortiAnalyzer" in t for t in texts)
    assert any("Custom Unmapped" in t for t in texts)


def test_chart_target_field_mapping():
    assert chart_target_field("Top 20 Sites por Tempo de Navegação") == "top_sites_by_browsing"
    assert chart_target_field("Seção Desconhecida XYZ") == "unmapped"
