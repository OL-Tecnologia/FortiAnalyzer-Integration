from forti_report.data.hierarchy import platform_model, region_display_name, site_display_name


def test_region_display_name_cas():
    assert region_display_name("cas") == "CAS - Campinas"


def test_site_display_name_accents():
    assert site_display_name("ambulatorio") == "Ambulatório"
    assert site_display_name("colegio") == "Colégio"
    assert site_display_name("stamaro") == "Santo Amaro"


def test_platform_model():
    assert platform_model("FortiGate-50G") == "50G"
    assert platform_model("FortiGate-200G") == "200G"
    assert platform_model("FortiGate-40F") == "40F"
    assert platform_model(None) == "—"
