import json
from pathlib import Path

from forti_report.data.parsers.mensal_json import parse_mensal_json

SAMPLE = Path(__file__).resolve().parents[1] / "output" / "samples" / "mensal_centro.json"


def test_parse_mensal_json_centro_sample():
    if not SAMPLE.is_file():
        return
    raw = SAMPLE.read_bytes()
    report = parse_mensal_json(raw, device_name="fw-spo-cruz-azul-centro")
    assert report.has_content
    assert report.summary.allowed_requests
    assert len(report.top_users_allowed) == 10
    assert len(report.top_sites_by_browsing) == 20


def test_parse_mensal_json_minimal_structure():
    payload = {
        "fortianalyzer-report": {
            "charts": [
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
                }
            ]
        }
    }
    report = parse_mensal_json(json.dumps(payload).encode(), device_name="fw-test")
    assert report.summary.allowed_requests == "100"
