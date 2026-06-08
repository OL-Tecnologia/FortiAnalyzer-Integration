from pathlib import Path

from forti_report.data.parsers.wan_pdf import parse_wan_traffic_pdf


def _reference_pdf() -> Path | None:
    for p in Path(__file__).resolve().parent.glob("SEMANAL*.pdf"):
        return p
    return None


def test_parse_wan_reference_pdf():
    pdf = _reference_pdf()
    if not pdf:
        return
    report = parse_wan_traffic_pdf(pdf)
    assert report.summary.allowed_requests
    assert len(report.top_users_allowed) >= 5
    assert len(report.top_sites_by_browsing) >= 10
    assert report.top_sites_by_browsing[0].label
