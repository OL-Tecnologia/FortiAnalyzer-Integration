from forti_report.pdf.sections.base import SectionRegistry
from forti_report.pdf.sections.top_sites import TopSitesSection


def build_default_registry() -> SectionRegistry:
    return SectionRegistry(
        sections=[
            TopSitesSection(),
            # Adicionar novas seções aqui (ex.: resumo, segurança, bandwidth)
        ]
    )
