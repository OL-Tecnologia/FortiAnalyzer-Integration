from forti_report.data.units import (
    extract_device_from_report_name,
    report_device_text,
    report_has_schedule,
    report_matches_device,
)


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


def test_extract_device_ignores_hostname_shape():
    cruz = (
        "MENSAL-RELATÓRIO DE ENDPOINT-fw-cas-cruz-azul-colegio[root]-2026-10-09-0804-0300_1976"
    )
    gomes = "MENSAL-RELATÓRIO DE ENDPOINT-MLGOMES_FG4H0E[root]-2026-10-09-0803-0300_6169"
    assert extract_device_from_report_name(cruz) == "fw-cas-cruz-azul-colegio"
    assert extract_device_from_report_name(gomes) == "MLGOMES_FG4H0E"


def test_schedule_uses_endpoint_prefix_not_daily_report():
    endpoint = {
        "name": "MENSAL-RELATÓRIO DE ENDPOINT-MLGOMES_FG4H0E[root]-2026-10-09-0803-0300_6169",
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
