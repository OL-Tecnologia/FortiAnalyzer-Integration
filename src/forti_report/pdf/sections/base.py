"""Contrato das seções do PDF."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from reportlab.platypus import Flowable

from forti_report.data.models import UnitReport


class PdfSection(ABC):
    key: str
    title: str
    order: int = 0

    @abstractmethod
    def build_flowables(self, unit: UnitReport) -> list[Flowable]:
        """Gera conteúdo ReportLab para a seção."""


@dataclass
class SectionRegistry:
    sections: list[PdfSection] = field(default_factory=list)

    def sorted(self) -> list[PdfSection]:
        return sorted(self.sections, key=lambda s: s.order)

    def for_unit(self, unit: UnitReport) -> list[PdfSection]:
        """Seções que possuem dados para a unidade."""
        available_keys = {s.key for s in unit.sections}
        return [s for s in self.sorted() if s.key in available_keys]
