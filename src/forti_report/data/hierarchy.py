"""Hierarquia: unidade regional → dispositivos (FortiGates por site)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from forti_report.data.models import UnitReport

_DEVICE_PATTERN = re.compile(
    r"^(?:(?P<prefix>hafw\d+)|fw)-(?P<region>[a-z]+)-cruz-azul-(?P<site>.+)$",
    re.IGNORECASE,
)

# Códigos regionais extraídos do naming convention fw-{code}-cruz-azul-{site}
REGION_LABELS: dict[str, str] = {
    "cas": "CAS - Campinas",
    "grs": "Unidade Guarulhos (GRS)",
    "oco": "Unidade Osasco (OCO)",
    "sne": "Unidade Santo André (SNE)",
    "spo": "Unidade São Paulo (SPO)",
    "sve": "Unidade São Vicente (SVE)",
}


@dataclass
class AntennaInfo:
    """Dispositivo FortiGate vinculado a uma unidade (site)."""

    device_name: str
    site_slug: str
    display_name: str
    device_type: str  # fw | hafw
    ip: str | None = None
    platform: str | None = None
    online: bool | None = None
    report: UnitReport | None = None


@dataclass
class RegionalUnit:
    """Unidade regional agrupando dispositivos de várias unidades (sites)."""

    code: str
    display_name: str
    antennas: list[AntennaInfo] = field(default_factory=list)

    @property
    def antenna_count(self) -> int:
        return len(self.antennas)

    @property
    def reports_linked(self) -> int:
        return sum(1 for a in self.antennas if a.report and a.report.faz_tid)


def parse_device_name(
    device_name: str,
    pattern: str | re.Pattern[str] | None = None,
) -> tuple[str, str, str] | None:
    """
    Retorna (region_code, site_slug, device_type) ou None se não reconhecer.
    Ex.: fw-spo-cruz-azul-centro → ('spo', 'centro', 'fw')
    """
    compiled = _DEVICE_PATTERN
    if pattern:
        compiled = re.compile(pattern, re.IGNORECASE) if isinstance(pattern, str) else pattern
    match = compiled.match(device_name.strip())
    if not match:
        return None
    groups = match.groupdict()
    prefix = groups.get("prefix")
    region = groups.get("region")
    site = groups.get("site")
    if not region or not site:
        return None
    device_type = "hafw" if prefix else "fw"
    return region.lower(), site.lower(), device_type


SITE_LABELS: dict[str, str] = {
    "ambulatorio": "Ambulatório",
    "colegio": "Colégio",
    "guarulhos": "Guarulhos",
    "osasco": "Osasco",
    "santo-andre": "Santo André",
    "centro": "Centro",
    "itaquera": "Itaquera",
    "matriz": "Matriz",
    "penha": "Penha",
    "stamaro": "Santo Amaro",
    "sao-vicente": "São Vicente",
}


def site_display_name(site_slug: str) -> str:
    """Converte slug em nome legível: santo-andre → Santo André."""
    key = site_slug.strip().lower()
    if key in SITE_LABELS:
        return SITE_LABELS[key]
    return site_slug.replace("-", " ").strip().title()


def region_display_name(code: str, labels: dict[str, str] | None = None) -> str:
    mapping = labels if labels is not None else REGION_LABELS
    return mapping.get(code.lower(), f"Unidade {code.upper()}")


def regional_sites_label(unit: RegionalUnit) -> str:
    """Lista legível das unidades (sites) da regional: (Ambulatório, Colégio, ...)."""
    names = [a.display_name for a in sorted(unit.antennas, key=lambda a: a.display_name.lower())]
    return f"({', '.join(names)})" if names else "—"


def platform_model(platform: str | None) -> str:
    """Extrai modelo curto: FortiGate-50G → 50G, FortiGate-200G → 200G."""
    if not platform:
        return "—"
    match = re.search(r"FortiGate[-\s]?(\d+[A-Za-z]*)", platform, re.IGNORECASE)
    if match:
        return match.group(1).upper() if match.group(1)[-1].isalpha() else match.group(1)
    match = re.search(r"(\d+[FfGg])", platform)
    if match:
        return match.group(1).upper()
    return platform.replace("FortiGate-", "").strip() or "—"


def build_regional_hierarchy(
    devices: list[dict],
    reports_by_device: dict[str, UnitReport] | None = None,
    *,
    device_pattern: str | None = None,
    region_labels: dict[str, str] | None = None,
) -> list[RegionalUnit]:
    """Monta árvore unidade regional → dispositivos a partir da lista de devices do FAZ."""
    reports_by_device = reports_by_device or {}
    buckets: dict[str, list[AntennaInfo]] = {}

    for dev in devices:
        name = dev.get("name") or ""
        parsed = parse_device_name(name, device_pattern)
        if not parsed:
            continue
        region, site, dtype = parsed
        antenna = AntennaInfo(
            device_name=name,
            site_slug=site,
            display_name=site_display_name(site),
            device_type=dtype,
            ip=dev.get("ip"),
            platform=dev.get("platform_str"),
            online=dev.get("dev_status") == 1,
            report=reports_by_device.get(name),
        )
        buckets.setdefault(region, []).append(antenna)

    units: list[RegionalUnit] = []
    for code in sorted(buckets.keys()):
        antennas = sorted(buckets[code], key=lambda a: a.display_name)
        units.append(
            RegionalUnit(
                code=code,
                display_name=region_display_name(code, region_labels),
                antennas=antennas,
            )
        )
    return units
