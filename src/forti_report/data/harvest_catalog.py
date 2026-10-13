"""Layouts que a colheita baixa do FortiAnalyzer e guarda para o PDF."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HarvestLayout:
    cycle: str
    prefix: str

    @property
    def folder(self) -> str:
        return self.prefix.replace(" ", "_").replace("-", "_")


# Só estes 10 layouts entram na colheita. A ordem é a da lista do FortiAnalyzer.
HARVEST_LAYOUTS: tuple[HarvestLayout, ...] = (
    HarvestLayout("diario", "RELATÓRIO DIÁRIO DE CONFIGURAÇÕES"),
    HarvestLayout("semanal", "SEMANAL- RELATÓRIO TRÁFEGO WAN"),
    HarvestLayout("semanal", "SEMANAL-RELATÓRIO CONSUMO DE BANDA"),
    HarvestLayout("semanal", "SEMANAL-RELATÓRIO DE ENDPOINT"),
    HarvestLayout("semanal", "SEMANAL-RELATÓRIO SISTEMA"),
    HarvestLayout("mensal", "MENSAL- RELATÓRIO TRÁFEGO WAN"),
    HarvestLayout("mensal", "MENSAL-RELATÓRIO CONSUMO DE BANDA"),
    HarvestLayout("mensal", "MENSAL-RELATÓRIO DE ENDPOINT"),
    HarvestLayout("mensal", "MENSAL-RELATÓRIO MENSAL DE CONFIGURAÇÕES"),
    HarvestLayout("mensal", "MENSAL-RELATÓRIO SISTEMA"),
)


def layouts_for(cycle: str) -> tuple[HarvestLayout, ...]:
    return tuple(layout for layout in HARVEST_LAYOUTS if layout.cycle == cycle)
