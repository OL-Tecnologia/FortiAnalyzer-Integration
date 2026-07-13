from forti_report.data.parsers.mensal_json import _rows_to_ranked
from forti_report.data.parsers.mensal_utils import (
    block_rate_percent,
    filter_ranked,
    format_bandwidth,
    parse_numeric_value,
    pie_values_from_items,
)
from forti_report.data.wan_models import RankedItem


def test_rows_to_ranked_category_not_user_ip():
    rows = [
        {
            "id": "1",
            "cols": [
                {"name": "Category", "value": "Information Technology"},
                {"name": "User", "value": "172.16.24.107"},
                {"value": "76120960", "attr": {"name": "Count"}},
                {"name": "% do Subtotal", "value": "18.13%"},
            ],
        }
    ]
    items = _rows_to_ranked(rows, label_hint="category", value_hint="requests")
    assert len(items) == 1
    assert items[0].label == "Information Technology"
    assert items[0].value == "76120960"
    assert items[0].percentage == "18.13%"


def test_rows_to_ranked_sites_use_browsing_time():
    rows = [
        {
            "id": "1",
            "cols": [
                {"name": "Sites", "value": "us.nimbus.bitdefender.net"},
                {"name": "Categories", "value": "Information Technology"},
                {"name": "Browsing Time (hh:mm:ss)", "value": "60:22:09"},
            ],
        }
    ]
    items = _rows_to_ranked(rows, label_hint="sites", value_hint="time")
    assert items[0].label == "us.nimbus.bitdefender.net"
    assert items[0].value == "60:22:09"
    assert items[0].category == "Information Technology"


def test_parse_duration_and_pie():
    items = [
        RankedItem(rank=1, label="IT", value="60:22:09", percentage="18.13%"),
        RankedItem(rank=2, label="Social", value="", percentage="12%"),
    ]
    assert parse_numeric_value("60:22:09") == 60 * 3600 + 22 * 60 + 9
    labels, values = pie_values_from_items(items)
    assert "IT" in labels
    assert all(v > 0 for v in values)


def test_rows_to_ranked_app_visibility():
    rows = [
        {
            "id": "1",
            "cols": [
                {"value": "General.Interest"},
                {"name": "Apps", "value": "22 ", "attr": {"name": "Count"}},
                {"name": "% do Total", "value": "22.68 "},
            ],
        }
    ]
    items = _rows_to_ranked(rows, label_hint="application", value_hint="requests")
    assert items[0].label == "General.Interest"
    assert items[0].value == "22"
    assert items[0].percentage == "22.68%"


def test_format_bandwidth():
    assert format_bandwidth("34410334018") == "32.05 GB"
    assert format_bandwidth("225.17 GB") == "225.17 GB"
    assert format_bandwidth("1430403") == "1.36 MB"


def test_filter_ranked_drops_empty():
    items = [
        RankedItem(rank=1, label="A", value="100"),
        RankedItem(rank=2, label="", value="50"),
        RankedItem(rank=3, label="C", value=""),
    ]
    assert len(filter_ranked(items)) == 1


def test_block_rate_percent():
    assert block_rate_percent("9000", "1000") == "10.0%"
    assert block_rate_percent("", "") == ""
    assert block_rate_percent("0", "0") == ""
