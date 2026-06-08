from forti_report.pdf.sections.base import PdfSection, SectionRegistry
from forti_report.pdf.sections.registry import build_default_registry
from forti_report.pdf.sections.top_sites import TopSitesSection

__all__ = [
    "PdfSection",
    "SectionRegistry",
    "TopSitesSection",
    "build_default_registry",
]
