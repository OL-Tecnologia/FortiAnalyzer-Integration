import json
from pathlib import Path

from forti_report.data.parsers.mensal_json import parse_mensal_json

SAMPLE = Path(__file__).resolve().parents[1] / "output" / "samples" / "mensal_centro.json"


def test_parse_mensal_json_centro_sample():
    if not SAMPLE.is_file():
        return
    raw = SAMPLE.read_bytes()
    report = parse_mensal_json(raw, device_name="fw-norte-matriz")
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


def test_parse_phishing_user_and_site():
    payload = {
        "fortianalyzer-report": {
            "charts": [
                {
                    "name": "Vítimas de Sites de Phishing",
                    "rows": [
                        {
                            "id": "1",
                            "cols": [
                                {"name": "User", "value": "172.16.81.13"},
                                {"name": "Site Phishing", "value": "https://evil.example/"},
                                {"name": "Requests", "value": "2"},
                                {"name": "% do Subtotal", "value": "100%"},
                            ],
                        }
                    ],
                }
            ]
        }
    }
    report = parse_mensal_json(json.dumps(payload).encode(), device_name="fw-test")
    assert len(report.phishing_victims) == 1
    item = report.phishing_victims[0]
    assert item.label == "172.16.81.13"
    assert item.category == "https://evil.example/"
    assert item.value == "2"
