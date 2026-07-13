from forti_report.pdf.sections.base import SectionRegistry
from forti_report.pdf.sections.top_sites import TopSitesSection


def build_default_registry() -> SectionRegistry:
    return SectionRegistry(
        sections=[
            TopSitesSection(),
            # Resumo executivo e segurança ampliada: PDF unificado
            # (resumo_executivo.py / seguranca.py).
        ]
    )
