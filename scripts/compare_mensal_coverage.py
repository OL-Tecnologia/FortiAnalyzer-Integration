"""Compara cobertura: JSON FAZ vs parser vs PDF unificado vs PDF FAZ original."""

from __future__ import annotations

import base64
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from forti_report.data.parsers.mensal_json import parse_mensal_json
from forti_report.pdf.unified_mensal_builder import _UnifiedMensalDoc

CACHE = ROOT / "output" / "faz_mensal"
UNIFIED = ROOT / "output" / "MENSAL_UNIFICADO_ADOM_EXEMPLO_20260603.pdf"

# Seções do layout MENSAL GERAL (layout-id 12) — referência FAZ
LAYOUT_SECTIONS = [
    "Sumário",
    "Análise Abrangente da Navegação Web",
    "RESUMO DE UTILIZAÇÃO WEB",
    "Categorias de Sites Mais Acessados",
    "Navegação Web",
    "Relatório Mensal de Consumo de Banda",
    "Aplicações SD-WAN",
    "RESUMO DE UTILIZAÇÃO DA WEB",
    "Atividade WEB",
    "USO DA LARGURA DE BANDA DA INTERNET",
]

# Campos que o PDF unificado renderiza por dispositivo
PDF_RENDERED = {
    "Resumo global (tabela)",
    "Resumo Executivo — Visão Geral",
    "Análise Abrangente da Navegação Web",
    "Resumo Executivo (por dispositivo)",
    "RESUMO DE UTILIZAÇÃO WEB (tabela parcial)",
    "Segurança Ampliada",
    "Gráfico timeline (placeholder)",
    "Top 10 Usuários Permitidas",
    "Top 10 Usuários Bloqueadas",
    "Categorias de Sites Mais Acessados",
    "Categoria com maior tempo de Navegação",
    "Top 20 Sites por Tempo de Navegação",
    "Principais Usuários Sites de Risco",
    "Aplicações SD-WAN (se houver dados)",
}

# Mapeamento chart title patterns -> parser field
CHART_TO_FIELD = [
    ("total de requis", "summary.allowed/blocked"),
    ("permitid", "top_users_allowed"),
    ("bloquead", "top_users_blocked"),
    ("top 20 sites", "top_sites_by_browsing"),
    ("maior tempo de naveg", "top_browsing_categories"),
    ("360 security", "top_categories"),
    ("sites de risco", "top_risk_users"),
    ("phishing", "top_risk_users (parcial)"),
    ("distribuicao de trafego", "sdwan_apps"),
    ("sd-wan", "sdwan_apps"),
    ("aplicativos web", "top_web_apps"),
    ("consumo de banda", "top_bandwidth_users"),
    ("timeline", "top_bandwidth_timeline (NÃO)"),
    ("360 degree", "summary widgets (NÃO)"),
    ("regras mais utilizadas", "policy_by_bandwidth"),
    ("politicas", "policy_by_bandwidth"),
    ("web usage request count", "summary counters (NÃO)"),
    ("device availability", "sdwan availability (NÃO)"),
]


def chart_title(chart: dict) -> str:
    name = chart.get("name") or ""
    try:
        return base64.b64decode(name + "==").decode("utf-8", errors="replace").strip()
    except Exception:
        return name


def normalize(t: str) -> str:
    return re.sub(r"\s+", " ", t.lower())


def inventory_json(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    charts = data.get("fortianalyzer-report", {}).get("charts") or []
    out = []
    for ch in charts:
        title = chart_title(ch)
        rows = len(ch.get("rows") or [])
        out.append({"title": title, "rows": rows, "type": ch.get("type", "")})
    return out


def match_field(title: str) -> str:
    t = normalize(title)
    for pat, field in CHART_TO_FIELD:
        if pat in t:
            return field
    return "NÃO MAPEADO"


def extract_pdf_sections(pdf_path: Path) -> list[str]:
    import pdfplumber

    headings: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                line = line.strip()
                if len(line) < 8:
                    continue
                if line.isupper() or re.match(r"^[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]", line):
                    if any(
                        k in line.lower()
                        for k in (
                            "resumo",
                            "top ",
                            "categor",
                            "navega",
                            "usuário",
                            "sd-wan",
                            "banda",
                            "risco",
                            "sumário",
                            "análise",
                            "aplic",
                            "polític",
                            "regra",
                            "phishing",
                            "360",
                        )
                    ):
                        headings.append(line[:100])
    return headings


def main() -> None:
    devices = sorted(CACHE.glob("fw-norte-*.json"))
    if not devices:
        devices = sorted(CACHE.glob("fw-*.json"))[:2]

    print("=" * 70)
    print("COMPARAÇÃO MENSAL GERAL")
    print("=" * 70)

    all_charts: dict[str, list[dict]] = {}
    for jp in devices:
        if "cas" not in jp.name:
            continue
        inv = inventory_json(jp)
        all_charts[jp.stem] = inv
        parsed = parse_mensal_json(jp.read_bytes(), device_name=jp.stem)
        pdf_ref = CACHE / f"{jp.stem}.pdf"

        print(f"\n### {jp.stem}")
        print(f"  JSON: {len(inv)} charts, {sum(1 for c in inv if c['rows']>0)} com dados")
        print(f"  Parser has_content: {parsed.has_content}")

        with_data = [c for c in inv if c["rows"] > 0]
        mapped = 0
        unmapped = []
        for c in with_data:
            field = match_field(c["title"])
            if field.startswith("NÃO"):
                unmapped.append((c["title"], c["rows"]))
            else:
                mapped += 1
        print(f"  Charts com dados mapeados: {mapped}/{len(with_data)}")
        if unmapped:
            print("  NÃO MAPEADOS no parser:")
            for t, r in unmapped[:15]:
                print(f"    - [{r} rows] {t[:70]}")

        if pdf_ref.is_file():
            import pypdf

            pages = len(pypdf.PdfReader(str(pdf_ref)).pages)
            headings = extract_pdf_sections(pdf_ref)
            print(f"  PDF FAZ original: {pages} páginas, ~{len(headings)} blocos de título detectados")
            print("  Amostra seções PDF FAZ:")
            seen = set()
            for h in headings[:12]:
                if h not in seen:
                    seen.add(h)
                    print(f"    · {h}")

    # PDF unificado
    print("\n" + "=" * 70)
    print("PDF UNIFICADO GERADO")
    print("=" * 70)
    if UNIFIED.is_file():
        import pypdf

        r = pypdf.PdfReader(str(UNIFIED))
        print(f"  Arquivo: {UNIFIED.name}")
        print(f"  Páginas: {len(r.pages)}")
        text0 = (r.pages[2].extract_text() or "")[:500] if len(r.pages) > 2 else ""
        print(f"  Seções renderizadas por dispositivo (código): {len(PDF_RENDERED)} tipos")
        for s in PDF_RENDERED:
            print(f"    · {s}")

    print("\n" + "=" * 70)
    print("GAPS CONHECIDOS (não 100%)")
    print("=" * 70)
    gaps = [
        "Gráficos visuais originais (pie, timeline, barras FAZ) — substituídos por Plotly ou placeholder",
        "360 Degree Application Visibility — não extraído",
        "Web Usage Request/Application/Category/User Count widgets — não extraídos do JSON",
        "Tempo de Uso da Internet (timeline multi-série) — placeholder, não dados reais",
        "Vítimas de Sites de Phishing — tabela no JSON, não no PDF unificado",
        "Principais fontes/destinos SD-WAN — parcial (sdwan_apps só)",
        "Top Usuários SD-WAN / Top 10 Maiores Consumidores Banda — não no PDF",
        "Regras mais utilizadas / Políticas por sessão — parseados mas não renderizados",
        "Textos introdutórios longos do layout FAZ — omitidos",
        "Capa/header/footer customizados FAZ — usamos assets próprios",
        "Planilhas CSV embutidas — não usamos CSV, só JSON",
    ]
    for g in gaps:
        print(f"  ✗ {g}")

    # Coverage estimate
    if all_charts:
        sample = next(iter(all_charts.values()))
        with_rows = [c for c in sample if c["rows"] > 0]
        mapped_n = sum(1 for c in with_rows if not match_field(c["title"]).startswith("NÃO"))
        rendered_n = 8  # main sections in unified pdf
        print(f"\nEstimativa CAS (1 dispositivo): JSON tabular ~{mapped_n}/{len(with_rows)} charts mapeados "
              f"({100*mapped_n//max(len(with_rows),1)}%)")
        print(f"Estimativa PDF unificado: ~{rendered_n} blocos principais vs ~{len(with_rows)} blocos com dados no FAZ")


if __name__ == "__main__":
    main()
