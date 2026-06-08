from forti_report.data.hierarchy import (
    build_regional_hierarchy,
    parse_device_name,
    region_display_name,
    site_display_name,
)


def test_parse_device_name():
    assert parse_device_name("fw-spo-cruz-azul-centro") == ("spo", "centro", "fw")
    assert parse_device_name("hafw1-spo-cruz-azul-matriz") == ("spo", "matriz", "hafw")
    assert parse_device_name("fw-sne-cruz-azul-santo-andre") == ("sne", "santo-andre", "fw")


def test_build_regional_hierarchy():
    devices = [
        {"name": "fw-spo-cruz-azul-centro", "ip": "1.1.1.1", "dev_status": 1, "platform_str": "FG-50G"},
        {"name": "fw-spo-cruz-azul-penha", "ip": "2.2.2.2", "dev_status": 1, "platform_str": "FG-50G"},
        {"name": "fw-cas-cruz-azul-colegio", "ip": "3.3.3.3", "dev_status": 0, "platform_str": "FG-50G"},
    ]
    units = build_regional_hierarchy(devices)
    assert len(units) == 2
    spo = next(u for u in units if u.code == "spo")
    assert spo.antenna_count == 2
    assert spo.display_name == region_display_name("spo")
    assert spo.antennas[0].display_name == site_display_name("centro")
