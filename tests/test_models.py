from forti_report.data.models import SectionData, SiteRankingItem, UnitReport
from forti_report.charts.plotly_charts import top_sites_bar_chart, chart_to_png_bytes


def test_top_sites_chart_exports_png():
    items = [
        SiteRankingItem("example.com", hits=100),
        SiteRankingItem("test.org", hits=50),
    ]
    fig = top_sites_bar_chart(items)
    png = chart_to_png_bytes(fig, width=400, height=200)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_unit_report_sections():
    items = [SiteRankingItem("a.com", hits=1)]
    unit = UnitReport(
        device_name="fw-test",
        display_name="Test",
        sections=[SectionData(key="top-sites", title="Top sites", site_ranking=items)],
    )
    assert unit.sections[0].key == "top-sites"
