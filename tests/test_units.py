from forti_report.data.units import report_device_text, report_matches_device


def test_report_device_text_from_dict():
    report = {"device": {"count": 1, "data": "fw-spo-cruz-azul-centro[root]"}}
    assert report_device_text(report) == "fw-spo-cruz-azul-centro[root]"


def test_report_matches_device():
    report = {
        "name": "MENSAL- RELATÓRIO GERAL-fw-spo-cruz-azul-centro[root]-2026-05-29",
        "title": "MENSAL- RELATÓRIO GERAL",
        "device": {"data": "fw-spo-cruz-azul-centro[root]"},
    }
    assert report_matches_device(report, "fw-spo-cruz-azul-centro")
    assert not report_matches_device(report, "fw-other")
