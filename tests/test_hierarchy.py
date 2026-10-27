from forti_report.data.hierarchy import (
    build_regional_hierarchy,
    parse_device_name,
    region_display_name,
    site_display_name,
)


def test_parse_device_name():
    assert parse_device_name("fw-norte-matriz") == ("norte", "matriz", "fw")
    assert parse_device_name("hafw1-norte-matriz") == ("norte", "matriz", "hafw")
    assert parse_device_name("fw-leste-filial-01") == ("leste", "filial-01", "fw")


def test_build_regional_hierarchy():
    devices = [
        {"name": "fw-norte-matriz", "ip": "1.1.1.1", "dev_status": 1, "platform_str": "FG-50G"},
        {"name": "fw-norte-anexo", "ip": "2.2.2.2", "dev_status": 1, "platform_str": "FG-50G"},
        {"name": "fw-sul-filial", "ip": "3.3.3.3", "dev_status": 0, "platform_str": "FG-50G"},
    ]
    units = build_regional_hierarchy(devices)
    assert len(units) == 2
    norte = next(u for u in units if u.code == "norte")
    assert norte.antenna_count == 2
    assert norte.display_name == region_display_name("norte")
    assert norte.antennas[0].display_name == site_display_name("anexo")


def test_hostname_fora_do_padrao_entra_na_hierarquia():
    devices = [
        {"name": "FW_MATRIZ_01", "ip": "10.0.0.1", "dev_status": 1, "platform_str": "FG-4H"},
        {"name": "fw-norte-matriz", "ip": "1.1.1.1", "dev_status": 1, "platform_str": "FG-50G"},
    ]
    units = build_regional_hierarchy(devices)
    names = {ant.device_name for unit in units for ant in unit.antennas}
    assert names == {"FW_MATRIZ_01", "fw-norte-matriz"}
    literal = next(unit for unit in units if unit.code == "fw_matriz_01")
    assert literal.display_name == "FW_MATRIZ_01"
