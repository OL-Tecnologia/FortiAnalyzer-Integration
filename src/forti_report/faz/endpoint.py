"""Normalização de host/URL do FortiAnalyzer."""

from __future__ import annotations


def parse_faz_endpoint(value: str) -> tuple[str, int | None, bool | None]:
    """
    Aceita IP/hostname ou URL completa.

    Retorna (host, porta_opcional, use_ssl_opcional).
    Exemplos:
      - "10.224.17.20" → ("10.224.17.20", None, None)
      - "https://10.224.17.20" → ("10.224.17.20", None, True)
      - "https://10.224.17.20:8090/" → ("10.224.17.20", 8090, True)
    """
    text = (value or "").strip()
    if not text:
        return "", None, None

    use_ssl: bool | None = None
    lower = text.lower()
    if lower.startswith("https://"):
        use_ssl = True
        text = text[8:]
    elif lower.startswith("http://"):
        use_ssl = False
        text = text[7:]

    text = text.split("/", 1)[0].strip()
    if not text:
        return "", None, use_ssl

    host = text
    port: int | None = None
    if text.count(":") == 1:
        host_part, port_part = text.rsplit(":", 1)
        if port_part.isdigit():
            host = host_part
            port = int(port_part)

    return host.strip(), port, use_ssl


def normalize_faz_host(value: str) -> str:
    host, _, _ = parse_faz_endpoint(value)
    return host
