"""Profile MENSAL PDF generation (run from repo root)."""
import time

from forti_report.config import get_settings
from forti_report.pdf.internal_page import _logo_png_for_width
from forti_report.pdf.unified_mensal_builder import UnifiedMensalPdfBuilder
from forti_report.services.mensal_pipeline import MensalReportPipeline


def _count_cache(settings) -> tuple[int, int]:
    json_n = 0
    if settings.faz_mensal_cache_dir.is_dir():
        json_n = len(list(settings.faz_mensal_cache_dir.glob("*.json")))
    chart_n = 0
    if settings.pdf_chart_cache_dir.is_dir():
        chart_n = len(list(settings.pdf_chart_cache_dir.glob("*.png")))
    return json_n, chart_n


def main() -> None:
    settings = get_settings()
    json_n, chart_n = _count_cache(settings)
    print(f"estado inicial: json_cache={json_n}, chart_cache={chart_n}")

    t0 = time.perf_counter()
    h = MensalReportPipeline(settings).fetch_hierarchy(days=60, download=False)
    antennas = sum(u.antenna_count for u in h.regional_units)
    with_data = sum(
        1
        for u in h.regional_units
        for a in u.antennas
        if a.report and a.report.mensal and a.report.mensal.has_content
    )
    print(
        f"fetch_hierarchy (metadata-only): {time.perf_counter() - t0:.2f}s "
        f"| unidades={len(h.regional_units)} antenas={antennas} com_dados={with_data}"
    )

    _logo_png_for_width.cache_clear()
    runs = [
        ("1-cold-charts", True),
        ("2-warm-charts", False),
        ("3-no-charts", False),
    ]
    for i, (label, charts) in enumerate(runs):
        s = settings.model_copy(update={"pdf_mensal_charts": charts})
        if i == 2:
            _logo_png_for_width.cache_clear()
        t1 = time.perf_counter()
        out = settings.output_dir / f"_profile_{label}.pdf"
        UnifiedMensalPdfBuilder(s).build(
            h.regional_units, out, adom=settings.faz_adom
        )
        json_n, chart_n = _count_cache(settings)
        print(
            f"build ({label}): {time.perf_counter() - t1:.2f}s, "
            f"{out.stat().st_size / 1024:.0f} KB | chart_cache={chart_n}"
        )


if __name__ == "__main__":
    main()
