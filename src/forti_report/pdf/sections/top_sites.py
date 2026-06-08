from __future__ import annotations

import io

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, Spacer, Table, TableStyle

from forti_report.charts.plotly_charts import chart_to_png_bytes, top_sites_bar_chart
from forti_report.data.models import UnitReport
from forti_report.pdf.sections.base import PdfSection


class TopSitesSection(PdfSection):
    key = "top-sites"
    title = "Ranking de sites acessados"
    order = 20

    def build_flowables(self, unit: UnitReport) -> list[Flowable]:
        section = next((s for s in unit.sections if s.key == self.key), None)
        if not section or not section.site_ranking:
            return []

        styles = getSampleStyleSheet()
        body = ParagraphStyle(
            "Body",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
        )
        flowables: list = [Paragraph(section.title, styles["Heading2"]), Spacer(1, 0.3 * cm)]

        fig = top_sites_bar_chart(section.site_ranking)
        png = chart_to_png_bytes(fig, width=800)
        flowables.append(Image(io.BytesIO(png), width=16 * cm, height=9 * cm))
        flowables.append(Spacer(1, 0.4 * cm))

        table_data = [["#", "Site", "Acessos"]]
        for idx, item in enumerate(section.site_ranking[:20], start=1):
            table_data.append([str(idx), item.site, str(item.hits or "-")])

        table = Table(table_data, colWidths=[1.2 * cm, 10 * cm, 3 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#003366")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F0F4F8")]),
                ]
            )
        )
        flowables.append(table)
        flowables.append(Spacer(1, 0.5 * cm))
        return flowables
