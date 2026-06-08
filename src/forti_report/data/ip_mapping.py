"""Mapeamento IP/subnet → antena para filtrar relatório WAN consolidado."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from forti_report.data.hierarchy import AntennaInfo, RegionalUnit, parse_device_name


@dataclass
class AntennaIpProfile:
    device_name: str
    prefixes: list[str] = field(default_factory=list)  # ex.: 10.29.64., 172.16.64.


def build_antenna_ip_profiles(devices: list[dict]) -> dict[str, AntennaIpProfile]:
    """Deriva prefixos a partir do IP de gerenciamento do FortiGate."""
    profiles: dict[str, AntennaIpProfile] = {}
    for dev in devices:
        name = dev.get("name") or ""
        ip = (dev.get("ip") or "").strip()
        if not name or not ip:
            continue
        prefixes: list[str] = []
        parts = ip.split(".")
        if len(parts) == 4:
            # IP interno típico 10.29.{octeto}.x espelha 172.16.{octeto}.x
            oct3 = parts[2]
            if parts[0] == "172" and parts[1] == "16":
                prefixes.append(f"10.29.{oct3}.")
                prefixes.append(f"172.16.{oct3}.")
            elif parts[0] == "10" and parts[1] == "26":
                prefixes.append(f"10.26.{oct3}.")
            elif parts[0] == "172" and parts[1] == "27":
                prefixes.append(f"172.27.{oct3}.")
                prefixes.append(f"10.29.{oct3}.")
            prefixes.append(".".join(parts[:3]) + ".")
        profiles[name] = AntennaIpProfile(device_name=name, prefixes=prefixes)
    return profiles


def label_matches_antenna(label: str, profile: AntennaIpProfile) -> bool:
    label = label.strip()
    if not label:
        return False
    for prefix in profile.prefixes:
        if label.startswith(prefix) or prefix.rstrip(".") in label:
            return True
    # match by device name token in hostname labels (rare)
    site = parse_device_name(profile.device_name)
    if site:
        _, site_slug, _ = site
        if site_slug.replace("-", "") in label.lower().replace("-", "").replace(".", ""):
            return True
    return False


def filter_ranked_for_antennas(items: list, profiles: list[AntennaIpProfile]) -> list:
    from forti_report.data.wan_models import RankedItem

    if not profiles:
        return items
    out: list[RankedItem] = []
    for item in items:
        if any(label_matches_antenna(item.label, p) for p in profiles):
            out.append(item)
    return out


def regional_unit_profiles(
    regional_unit: RegionalUnit,
    all_profiles: dict[str, AntennaIpProfile],
) -> list[AntennaIpProfile]:
    return [
        all_profiles[a.device_name]
        for a in regional_unit.antennas
        if a.device_name in all_profiles
    ]
