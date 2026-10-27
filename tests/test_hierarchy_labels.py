from forti_report.data.hierarchy import platform_model, region_display_name, site_display_name


def test_region_display_name_uses_code_when_unlabeled():
    assert region_display_name("norte") == "Unidade NORTE"


def test_site_display_name_from_slug():
    assert site_display_name("filial-norte") == "Filial Norte"


def test_platform_model():
    assert platform_model("FortiGate-50G") == "50G"
    assert platform_model("FortiGate-200G") == "200G"
    assert platform_model("FortiGate-40F") == "40F"
    assert platform_model(None) == "—"
