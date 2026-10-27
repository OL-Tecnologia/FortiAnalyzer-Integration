from forti_report.config import Settings
from forti_report.clients.models import FazClientConfig
from forti_report.faz.endpoint import normalize_faz_host, parse_faz_endpoint


def test_parse_plain_ip():
    assert parse_faz_endpoint("192.0.2.10") == ("192.0.2.10", None, None)


def test_parse_https_url_strips_scheme():
    assert parse_faz_endpoint("https://192.0.2.10") == ("192.0.2.10", None, True)


def test_parse_https_url_with_port_and_slash():
    assert parse_faz_endpoint("https://192.0.2.10:8090/") == ("192.0.2.10", 8090, True)


def test_faz_client_config_normalizes_url_host():
    faz = FazClientConfig(host="https://192.0.2.10", port=8090, use_ssl=True)
    assert faz.host == "192.0.2.10"
    assert faz.port == 8090
    assert faz.use_ssl is True


def test_jsonrpc_url_never_doubles_scheme():
    settings = Settings(
        faz_host="https://192.0.2.10",
        faz_port=8090,
        faz_use_ssl=True,
    )
    assert settings.jsonrpc_url == "https://192.0.2.10:8090/jsonrpc"
    assert "https://https://" not in settings.jsonrpc_url
    assert normalize_faz_host("https://192.0.2.10") == "192.0.2.10"
