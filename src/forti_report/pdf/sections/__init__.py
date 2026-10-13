from forti_report.pdf.sections.base import PdfSection, SectionRegistry
from forti_report.pdf.sections.registry import build_default_registry
from forti_report.pdf.sections.faz_conteudo import build_faz_conteudo_flowables
from forti_report.pdf.sections.resumo_executivo import (
    build_global_resumo_executivo_flowables,
    build_resumo_executivo_flowables,
)
from forti_report.pdf.sections.seguranca import build_seguranca_flowables
from forti_report.pdf.sections.top_sites import TopSitesSection

__all__ = [
    "PdfSection",
    "SectionRegistry",
    "TopSitesSection",
    "build_default_registry",
    "build_resumo_executivo_flowables",
    "build_seguranca_flowables",
    "build_faz_conteudo_flowables",
]
