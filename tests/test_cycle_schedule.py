from datetime import datetime
from zoneinfo import ZoneInfo

from forti_report.services.consolidated import HarvestItemRef, _series_summary, _text, select_for_cycle
from forti_report.services.consolidated import ChartTable
from forti_report.services.cycle_schedule import closed_through, completed_week, cycles_due

TZ = ZoneInfo("America/Sao_Paulo")


def _item(prefix: str, period: str, path: str, cycle: str = "") -> HarvestItemRef:
    return HarvestItemRef(
        cycle=cycle or ("diario" if prefix.startswith("RELAT") else ""),
        prefix=prefix,
        device="MLGOMES_FG4H0E",
        period_end=datetime.strptime(period, "%Y-%m-%d").date(),
        path=path,
        name=path,
    )


def test_segunda_dia_primeiro_gera_os_tres():
    when = datetime(2026, 6, 1, 6, 0, tzinfo=TZ)
    assert when.weekday() == 0
    assert cycles_due(when) == ("diario", "semanal", "mensal")


def test_terca_gera_so_o_diario():
    when = datetime(2026, 10, 13, 6, 0, tzinfo=TZ)
    assert cycles_due(when) == ("diario",)


def test_dia_primeiro_numa_quarta_gera_diario_e_mensal():
    when = datetime(2026, 7, 1, 6, 5, tzinfo=TZ)
    assert when.weekday() == 2
    assert cycles_due(when) == ("diario", "mensal")


def test_antes_das_seis_nao_dispara():
    when = datetime(2026, 10, 12, 5, 59, tzinfo=TZ)
    assert cycles_due(when) == ()


def test_diario_das_seis_usa_o_arquivo_do_dia_anterior():
    when = datetime(2026, 10, 14, 6, 0, tzinfo=TZ)
    assert closed_through(when).isoformat() == "2026-10-13"
    items = [
        _item("RELATÓRIO DIÁRIO DE CONFIGURAÇÕES", "2026-10-12", "antigo.json", "diario"),
        _item("RELATÓRIO DIÁRIO DE CONFIGURAÇÕES", "2026-10-13", "ontem.json", "diario"),
        _item("RELATÓRIO DIÁRIO DE CONFIGURAÇÕES", "2026-10-14", "hoje.json", "diario"),
    ]
    chosen, _dailies = select_for_cycle(items, "diario", when)
    assert chosen[0][1].path == "ontem.json"


def test_semana_encerra_no_domingo_anterior():
    monday = datetime(2026, 10, 12, 6, 0, tzinfo=TZ)
    assert completed_week(monday) == (
        datetime(2026, 10, 5).date(),
        datetime(2026, 10, 11).date(),
    )
    items = [
        _item("SEMANAL- RELATÓRIO TRÁFEGO WAN", "2026-10-08", "wan.json", "semanal"),
        _item("RELATÓRIO DIÁRIO DE CONFIGURAÇÕES", "2026-10-08", "d1.json", "diario"),
        _item("RELATÓRIO DIÁRIO DE CONFIGURAÇÕES", "2026-10-12", "fora.json", "diario"),
    ]
    chosen, dailies = select_for_cycle(items, "semanal", monday)
    wan = next(item for layout, item in chosen if "WAN" in layout.prefix)
    assert wan.path == "wan.json"
    assert [item.path for item in dailies] == ["d1.json"]


def test_pizza_e_linha_seguem_o_tipo_do_fortianalyzer():
    from forti_report.charts.faz_layout import figure_for_chart

    pie = figure_for_chart(
        ChartTable(
            title="Top usuários",
            kind="pie",
            headers=["Usuário", "Requisições", "% do total"],
            rows=[["ana", "10", "40"], ["bia", "15", "60"]],
            total_rows=2,
        )
    )
    line = figure_for_chart(
        ChartTable(
            title="CPU",
            kind="line",
            headers=["", "Equipamento"],
            rows=[["1790910000", "1"], ["1791000000", "9"], ["1791543600", "3"]],
            total_rows=3,
        )
    )
    assert pie is not None and pie.data[0].type == "pie"
    assert line is not None and line.data[0].type == "scatter"
    assert list(line.data[0].y) == [1.0, 9.0, 3.0]


def test_colunas_sem_nome_conservam_o_rotulo_da_fatia():
    from forti_report.charts.faz_layout import figure_for_chart
    from forti_report.services.consolidated import _rows_of

    headers, rows = _rows_of(
        [
            {
                "cols": [
                    {"value": "Unidentified"},
                    {"value": "128 "},
                    {"name": "% do Total", "value": "94.81 "},
                ]
            },
            {
                "cols": [
                    {"value": "Identified"},
                    {"value": "7 "},
                    {"name": "% do Total", "value": "5.19 "},
                ]
            },
        ]
    )
    assert headers[0] == ""
    assert rows[0][0] == "Unidentified"
    pie = figure_for_chart(ChartTable("Ativo por Identificação", "pie", headers, rows, len(rows)))
    assert list(pie.data[0].labels)[0].startswith("Unidentified")
    assert list(pie.data[0].labels)[1].startswith("Identified")


def test_tempo_de_navegacao_nao_some_e_coluna_faltando_nao_desloca():
    from forti_report.services.consolidated import _rows_of

    headers, rows = _rows_of(
        [
            {
                "cols": [
                    {"name": "Sites", "value": "outlook.office.com"},
                    {"name": "Category", "value": "Information Technology"},
                    {
                        "name": "Browsing Time (hh:mm:ss)",
                        "merged-cols": [
                            {"name": "Browsing Time (hh:mm:ss)", "value": "59:06:06"},
                            {"name": "Browsing Time (hh:mm:ss)", "value": "212766.000000"},
                        ],
                    },
                    {"name": "Browsing Time (hh:mm:ss)", "value": "59:06:06"},
                ]
            }
        ]
    )
    assert rows[0] == ["outlook.office.com", "Information Technology", "59:06:06"]
    assert headers == ["Site", "Categoria", "Tempo de navegação"]
    headers2, rows2 = _rows_of(
        [
            {
                "cols": [
                    {"name": "Usuário", "value": "ana"},
                    {"name": "Site Phishing", "value": "https://a"},
                    {"name": "Total", "value": "28"},
                ]
            },
            {
                "cols": [
                    {"name": "Site Phishing", "value": "https://b"},
                    {"name": "Total", "value": "9"},
                ]
            },
        ]
    )
    assert rows2[1] == ["", "https://b", "9"]
    assert headers2[0] == "Usuário"


def test_anel_agrupa_categoria_e_gigabyte_entra_na_medida():
    from forti_report.charts.faz_layout import _measure, figure_for_chart

    assert _measure("52.14 GB") == 52.14 * 1_000_000_000
    assert _measure("1,438,861") == 1438861
    ring = figure_for_chart(
        ChartTable(
            title="Categorias",
            kind="bubble-ring",
            headers=["Categoria", "Usuário", "% do subtotal"],
            rows=[
                ["ALLOW_ALL", "ana", "0.35%"],
                ["ALLOW_ALL", "bia", "0.26%"],
                ["Business", "ana", "0.10%"],
            ],
            total_rows=3,
        )
    )
    assert ring.data[0].labels[0].startswith("ALLOW_ALL — ana")
    assert any(label.startswith("Business") for label in ring.data[0].labels)


def test_cabecalho_curto_em_base64_vira_usuario():
    assert _text("VXN1w6FyaW8=") == "Usuário"


def test_serie_longa_resume_minimo_maximo_e_ultimo():
    table = ChartTable(
        title="CPU",
        kind="line",
        headers=["", "MLGOMES"],
        rows=[["1790910000", "1"], ["1791000000", "9"], ["1791543600", "3"]],
        total_rows=3,
    )
    summary = _series_summary(table)
    assert summary == [["MLGOMES", "1", "9", "3"]]


def test_pdf_consolidado_abre_com_capa_e_fecha_com_rodape(tmp_path):
    import pypdfium2 as pdfium

    from forti_report.config import get_settings
    from forti_report.data.harvest_catalog import layouts_for
    from forti_report.services.consolidated import _write_pdf

    settings = get_settings().model_copy(
        update={
            "output_dir": tmp_path,
            "client_display_name": "Ol-Gomes",
            "faz_adom": "root",
        }
    )
    path = tmp_path / "diario.pdf"
    when = datetime(2026, 10, 13, 16, 30, tzinfo=TZ)
    _write_pdf(path, settings, "semanal", when, [(layout, None) for layout in layouts_for("semanal")], [])
    doc = pdfium.PdfDocument(str(path))
    cover = doc[0].get_textpage().get_text_bounded()
    body = doc[1].get_textpage().get_text_bounded()
    assert "RELATÓRIO SEMANAL" in cover
    assert "Ol-Gomes" in cover
    assert "05/10/2026 a 11/10/2026" in cover
    assert "Sumário" in body
    assert "RELATORIO SEMANAL" in body
    assert "SEMANAL-RELATÓRIO DE ENDPOINT" in body
    assert f"Página 2 de {len(doc)}" in body
    assert len(doc) > 2


def test_capa_usa_o_intervalo_real_dos_arquivos():
    from datetime import date

    from forti_report.services.consolidated import _period_label

    when = datetime(2026, 10, 13, 16, 30, tzinfo=TZ)
    assert _period_label("semanal", when, (date(2026, 10, 2), date(2026, 10, 9))) == "02/10/2026 a 09/10/2026"
    assert _period_label("diario", when, (date(2026, 10, 13), date(2026, 10, 13))) == "13/10/2026"


def test_linha_corta_dias_zerados_e_pizza_guarda_dez_fatias():
    from forti_report.charts.faz_layout import _top_slices, figure_for_chart

    labels, values = _top_slices([f"n{i}" for i in range(12)], [float(i + 1) for i in range(12)])
    assert labels[-1] == "Outros"
    assert len(labels) == 11
    line = figure_for_chart(
        ChartTable(
            title="Banda",
            kind="line",
            headers=["", "Bytes"],
            rows=[
                ["1790910000", "0"],
                ["1791000000", "0"],
                ["1791100000", "2000000000"],
                ["1791200000", "4000000000"],
            ],
            total_rows=4,
        )
    )
    assert list(line.data[0].y) == [2.0, 4.0]
    assert line.layout.yaxis.title.text == "GB"

