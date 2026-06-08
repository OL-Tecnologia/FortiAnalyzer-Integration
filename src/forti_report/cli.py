"""CLI: testes e geração de relatórios."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from forti_report.config import get_settings
from forti_report.faz.client import FortiAnalyzerClient, FortiAnalyzerError
from forti_report.faz.devices import DeviceService
from forti_report.faz.reports import ReportService
from forti_report.services.pipeline import ReportPipeline
from forti_report.services.mensal_pipeline import MensalReportPipeline
from forti_report.services.wan_pipeline import WanReportPipeline


def cmd_test_connection() -> int:
    settings = get_settings()
    try:
        with FortiAnalyzerClient(settings) as client:
            client.login()
            service = ReportService(client, settings)
            devices = DeviceService(client, settings).list_device_names()
            reports = service.list_reports(days=7)
            print(f"OK — login em {settings.jsonrpc_url}")
            print(f"ADOM: {settings.faz_adom}")
            print(f"Antenas (dispositivos): {len(devices)}")
            print(f"Relatórios gerados (7 dias): {len(reports)}")
        return 0
    except FortiAnalyzerError as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 1


def cmd_list_units() -> int:
    """Lista antenas (FortiGates) — alias legado."""
    pipeline = ReportPipeline()
    units = pipeline.list_unit_names()
    print(f"Antenas no ADOM {get_settings().faz_adom} ({len(units)}):\n")
    for name in units:
        print(f"  {name}")
    return 0


def cmd_list_hierarchy() -> int:
    pipeline = ReportPipeline()
    result = pipeline.fetch_hierarchy(days=60, download=False)
    print(f"Unidades regionais no ADOM {get_settings().faz_adom}:\n")
    for ru in result.regional_units:
        print(f"  [{ru.code.upper()}] {ru.display_name} — {ru.antenna_count} antena(s)")
        for ant in ru.antennas:
            status = "online" if ant.online else "offline" if ant.online is False else "?"
            rep = "com relatório" if ant.report and ant.report.faz_tid else "sem relatório"
            print(f"      • {ant.display_name} ({ant.device_name}) [{status}] — {rep}")
        print()
    return 0


def cmd_pull_all(args: argparse.Namespace) -> int:
    pipeline = ReportPipeline()
    result = pipeline.pull_all_units(
        days=args.days,
        download=not args.metadata_only,
    )
    print(f"\nAntenas processadas: {len(result.units)}")
    with_report = sum(1 for u in result.units if u.faz_tid)
    print(f"Com relatório vinculado: {with_report}")
    if result.download_denied:
        print(f"\nDownload negado pelo FAZ ({len(result.download_denied)} antenas).")
        print("  Peça permissão Read-Write ou acesso a download de relatórios ao admin.")
    if result.skipped:
        print(f"\nSem relatório ou sem parse ({len(result.skipped)}):")
        for s in result.skipped:
            print(f"  - {s['device']}: {s['reason']}")
    if result.errors:
        print(f"\nErros ({len(result.errors)}):")
        for e in result.errors:
            print(f"  - {e['device']}: {e['error']}")
    return 1 if result.errors and not result.units else 0


def cmd_pull_hierarchy(args: argparse.Namespace) -> int:
    pipeline = ReportPipeline()
    result = pipeline.pull_hierarchy(days=args.days, download=not args.metadata_only)
    total_antennas = sum(ru.antenna_count for ru in result.regional_units)
    total_reports = sum(ru.reports_linked for ru in result.regional_units)
    print(f"\n{len(result.regional_units)} unidade(s) regional(is), {total_antennas} antena(s)")
    print(f"Relatórios vinculados: {total_reports}")
    for ru in result.regional_units:
        print(f"  [{ru.code.upper()}] {ru.display_name}: {ru.reports_linked}/{ru.antenna_count} com relatório")
    if result.import_result and result.import_result.download_denied:
        print(f"\nDownload negado em {len(result.import_result.download_denied)} antena(s).")
    return 0


def cmd_generate_all(args: argparse.Namespace) -> int:
    pipeline = ReportPipeline()
    result, paths = pipeline.run_for_all_units(days=args.days)
    print(f"\nPDFs gerados: {len(paths)}")
    for p in paths:
        print(f"  {p}")
    return 0


def cmd_generate_regional(args: argparse.Namespace) -> int:
    pipeline = ReportPipeline()
    result = pipeline.fetch_hierarchy(days=args.days, download=not args.metadata_only)
    code = args.unit_code.lower()
    match = next((ru for ru in result.regional_units if ru.code == code), None)
    if not match:
        codes = ", ".join(ru.code for ru in result.regional_units)
        print(f"Unidade '{code}' não encontrada. Disponíveis: {codes}", file=sys.stderr)
        return 1
    path = pipeline.generate_regional_pdf(match)
    print(f"PDF da unidade [{match.code.upper()}] gerado: {path}")
    return 0


def cmd_generate_all_regional(args: argparse.Namespace) -> int:
    pipeline = ReportPipeline()
    result = pipeline.pull_hierarchy(days=args.days, download=not args.metadata_only)
    paths = pipeline.generate_all_regional_pdfs(result)
    print(f"\nPDFs por unidade regional: {len(paths)}")
    for p in paths:
        print(f"  {p}")
    return 0


def cmd_generate_mensal_unified(args: argparse.Namespace) -> int:
    settings = get_settings()
    updates: dict = {}
    if getattr(args, "no_charts", False):
        updates["pdf_mensal_charts"] = False
    if getattr(args, "force_download", False):
        updates["faz_prefer_cache"] = False
    if updates:
        settings = settings.model_copy(update=updates)
    pipeline = MensalReportPipeline(settings)
    path = pipeline.generate_unified_pdf(
        days=args.days,
        download=not args.metadata_only,
    )
    print(f"PDF MENSAL unificado gerado: {path}")
    return 0


def cmd_generate_wan_all(args: argparse.Namespace) -> int:
    pipeline = WanReportPipeline()
    pdf_path = Path(args.pdf) if args.pdf else None
    paths = pipeline.generate_all_wan_pdfs(pdf_path=pdf_path, days=args.days)
    print(f"\nPDFs WAN gerados: {len(paths)}")
    for p in paths:
        print(f"  {p}")
    return 0


def cmd_generate_wan_unit(args: argparse.Namespace) -> int:
    pipeline = WanReportPipeline()
    pdf_path = Path(args.pdf) if args.pdf else None
    path = pipeline.generate_wan_pdf_for_unit(args.unit_code, pdf_path=pdf_path, days=args.days)
    print(f"PDF WAN gerado: {path}")
    return 0


def cmd_list_reports() -> int:
    settings = get_settings()
    with FortiAnalyzerClient(settings) as client:
        client.login()
        service = ReportService(client, settings)
        reports = service.list_reports(days=30)
    print(f"Relatórios recentes ({len(reports)}):\n")
    for r in reports[:40]:
        print(f"  {r.get('name', '')}")
    return 0


def cmd_demo() -> int:
    path = ReportPipeline().run_demo()
    print(f"PDF demo gerado: {path}")
    return 0


def cmd_generate(device: str) -> int:
    path = ReportPipeline().run_for_device(device)
    print(f"PDF gerado: {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FortiAnalyzer → PDF (Plotly + ReportLab)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("test-connection", help="Testa login, antenas e relatórios")
    sub.add_parser("list-units", help="Lista antenas (FortiGates) do ADOM")
    sub.add_parser("list-hierarchy", help="Lista unidades regionais e suas antenas")
    sub.add_parser("list-reports", help="Lista nomes de relatórios recentes")

    pull = sub.add_parser("pull-all", help="Importa dados de todas as antenas")
    pull.add_argument("--days", type=int, default=60)
    pull.add_argument("--metadata-only", action="store_true")

    pull_h = sub.add_parser("pull-hierarchy", help="Importa e agrupa por unidade regional")
    pull_h.add_argument("--days", type=int, default=60)
    pull_h.add_argument("--metadata-only", action="store_true")

    gen_all = sub.add_parser("generate-all", help="PDF por antena (legado)")
    gen_all.add_argument("--days", type=int, default=60)

    gen_reg = sub.add_parser("generate-unit", help="PDF consolidado de uma unidade regional")
    gen_reg.add_argument("unit_code", help="Código da unidade: spo, cas, grs, oco, sne, sve")
    gen_reg.add_argument("--days", type=int, default=60)
    gen_reg.add_argument("--metadata-only", action="store_true")

    gen_regs = sub.add_parser("generate-all-units", help="PDF de cada unidade regional")
    gen_regs.add_argument("--days", type=int, default=60)
    gen_regs.add_argument("--metadata-only", action="store_true")

    gen_mensal = sub.add_parser(
        "generate-mensal-unified",
        help="PDF único MENSAL- RELATÓRIO GERAL (11 antenas / 6 unidades)",
    )
    gen_mensal.add_argument("--days", type=int, default=60)
    gen_mensal.add_argument("--metadata-only", action="store_true")
    gen_mensal.add_argument(
        "--no-charts",
        action="store_true",
        help="Gera PDF só com tabelas (muito mais rápido)",
    )
    gen_mensal.add_argument(
        "--force-download",
        action="store_true",
        help="Ignora cache JSON e baixa de novo do FAZ (novo mês / relatório novo)",
    )

    gen_wan = sub.add_parser("generate-wan-all", help="PDF WAN (6 unidades) baseado no SEMANAL Tráfego WAN")
    gen_wan.add_argument("--days", type=int, default=60)
    gen_wan.add_argument("--pdf", type=str, default="", help="Caminho do PDF FAZ de referência")

    gen_wan1 = sub.add_parser("generate-wan-unit", help="PDF WAN de uma unidade regional")
    gen_wan1.add_argument("unit_code", help="spo, cas, grs, oco, sne, sve")
    gen_wan1.add_argument("--days", type=int, default=60)
    gen_wan1.add_argument("--pdf", type=str, default="")

    sub.add_parser("demo", help="PDF demo com dados fictícios")
    gen = sub.add_parser("generate", help="PDF de uma antena específica")
    gen.add_argument("device", help="Nome do dispositivo (ex.: fw-spo-cruz-azul-centro)")

    args = parser.parse_args(argv)
    handlers = {
        "test-connection": cmd_test_connection,
        "list-units": cmd_list_units,
        "list-hierarchy": cmd_list_hierarchy,
        "list-reports": cmd_list_reports,
        "pull-all": lambda: cmd_pull_all(args),
        "pull-hierarchy": lambda: cmd_pull_hierarchy(args),
        "generate-all": lambda: cmd_generate_all(args),
        "generate-unit": lambda: cmd_generate_regional(args),
        "generate-all-units": lambda: cmd_generate_all_regional(args),
        "generate-mensal-unified": lambda: cmd_generate_mensal_unified(args),
        "generate-wan-all": lambda: cmd_generate_wan_all(args),
        "generate-wan-unit": lambda: cmd_generate_wan_unit(args),
        "demo": cmd_demo,
        "generate": lambda: cmd_generate(args.device),
    }
    return handlers[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
