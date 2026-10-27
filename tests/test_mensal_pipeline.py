from forti_report.services.pipeline import _device_display_name


def test_device_display_name_uses_site_slug():
    name = _device_display_name({"title": "MENSAL- RELATÓRIO GERAL"}, "fw-norte-matriz")
    assert name == "Matriz"
