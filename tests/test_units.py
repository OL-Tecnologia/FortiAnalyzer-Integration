from forti_report.data.units import (
    extract_device_from_report_name,
    report_device_text,
    report_has_schedule,
    report_matches_device,
)


def test_report_device_text_from_dict():
    report = {"device": {"count": 1, "data": "fw-norte-matriz[root]"}}
    assert report_device_text(report) == "fw-norte-matriz[root]"


def test_report_matches_device():
    report = {
        "name": "MENSAL- RELATÓRIO GERAL-fw-norte-matriz[root]-2026-05-29",
        "title": "MENSAL- RELATÓRIO GERAL",
        "device": {"data": "fw-norte-matriz[root]"},
    }
    assert report_matches_device(report, "fw-norte-matriz")
    assert not report_matches_device(report, "fw-other")


def test_extract_device_ignores_hostname_shape():
    cruz = (
        "MENSAL-RELATÓRIO DE ENDPOINT-fw-sul-anexo[root]-2026-10-09-0804-0300_1976"
    )
    gomes = "MENSAL-RELATÓRIO DE ENDPOINT-FW_MATRIZ_01[root]-2026-10-09-0803-0300_6169"
    assert extract_device_from_report_name(cruz) == "fw-sul-anexo"
    assert extract_device_from_report_name(gomes) == "FW_MATRIZ_01"


def test_schedule_uses_endpoint_prefix_not_daily_report():
    endpoint = {
        "name": "MENSAL-RELATÓRIO DE ENDPOINT-FW_MATRIZ_01[root]-2026-10-09-0803-0300_6169",
        "title": "MENSAL-RELATÓRIO DE ENDPOINT",
    }
    daily = {
        "name": "REPORT MONITORAMENTO SYS ADMIN-2026-10-13-0800-0300_6267",
        "title": "REPORT MONITORAMENTO SYS ADMIN",
    }
    assert report_has_schedule(endpoint, "MENSAL- RELATÓRIO GERAL")
    assert report_has_schedule(endpoint, "MENSAL-RELATÓRIO DE ENDPOINT")
    assert not report_has_schedule(daily, "MENSAL-RELATÓRIO DE ENDPOINT")
    assert not report_has_schedule(daily, "")
