"""Testes dos cards KPI e helpers de gráficos executivos."""

from forti_report.charts.plotly_charts import (
    allowed_blocked_donut,
    create_bar_chart,
    create_donut_chart,
    create_gauge,
    parse_availability_percent,
    status_donut_chart,
)
from forti_report.data.wan_models import RankedItem
from forti_report.pdf.kpi_cards import kpi_cards_table


def test_kpi_cards_table_builds():
    table = kpi_cards_table(
        [
            ("Permitidas", "100"),
            ("Bloqueadas", "10"),
            ("Usuários", "5"),
        ],
        width=400,
        cols=3,
    )
    assert table is not None


def test_kpi_cards_empty():
    assert kpi_cards_table([], width=400) is None

def test_status_donut_chart():
    fig = status_donut_chart(online=8, offline=3)
    assert fig is not None


def test_allowed_blocked_donut():
    fig = allowed_blocked_donut(9000, 1000)
    assert fig is not None
    assert allowed_blocked_donut(0, 0) is None


def test_create_gauge_and_parse_availability():
    assert parse_availability_percent("100%") == 100.0
    assert parse_availability_percent("99,5 %") == 99.5
    assert parse_availability_percent("—") is None
    fig = create_gauge(100.0, title="Disponibilidade")
    assert fig is not None


def test_create_bar_and_donut():
    items = [
        RankedItem(rank=1, label="A", value="100"),
        RankedItem(rank=2, label="B", value="50"),
        RankedItem(rank=3, label="C", value="25"),
    ]
    assert create_bar_chart(items, title="Teste", max_items=3) is not None
    assert create_donut_chart(["A", "B"], [10.0, 5.0], title="Donut") is not None
