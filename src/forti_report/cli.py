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
from forti_report.services.mensal_scheduler import get_scheduler_status, run_scheduled_mensal
from forti_report.services.email_delivery import probe_smtp, send_email
from forti_report.config import get_settings


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
            print(f"Dispositivos: {len(devices)}")
            print(f"Relatórios gerados (7 dias): {len(reports)}")
        return 0
    except FortiAnalyzerError as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 1


def cmd_list_units() -> int:
    """Lista dispositivos (FortiGates) — alias legado."""
    pipeline = ReportPipeline()
    units = pipeline.list_unit_names()
    print(f"Dispositivos no ADOM {get_settings().faz_adom} ({len(units)}):\n")
    for name in units:
        print(f"  {name}")
    return 0


def cmd_list_hierarchy() -> int:
    pipeline = ReportPipeline()
    result = pipeline.fetch_hierarchy(days=60, download=False)
    print(f"Unidades regionais no ADOM {get_settings().faz_adom}:\n")
    for ru in result.regional_units:
        print(f"  [{ru.code.upper()}] {ru.display_name} — {ru.antenna_count} dispositivo(s)")
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
    print(f"\nDispositivos processados: {len(result.units)}")
    with_report = sum(1 for u in result.units if u.faz_tid)
    print(f"Com relatório vinculado: {with_report}")
    if result.download_denied:
        print(f"\nDownload negado pelo FAZ ({len(result.download_denied)} dispositivos).")
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
    print(f"\n{len(result.regional_units)} unidade(s) regional(is), {total_antennas} dispositivo(s)")
    print(f"Relatórios vinculados: {total_reports}")
    for ru in result.regional_units:
        print(f"  [{ru.code.upper()}] {ru.display_name}: {ru.reports_linked}/{ru.antenna_count} com relatório")
    if result.import_result and result.import_result.download_denied:
        print(f"\nDownload negado em {len(result.import_result.download_denied)} dispositivo(s).")
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


def cmd_run_scheduled_mensal(args: argparse.Namespace) -> int:
    result = run_scheduled_mensal(force=args.force)
    print(f"Status: {result.status}")
    print(f"Período: {result.period}")
    print(result.message)
    if result.pdf_path:
        print(f"PDF: {result.pdf_path}")
    if result.error:
        print(f"Erro: {result.error}", file=sys.stderr)
    if result.status == "skipped":
        return 0
    return 0 if result.status == "success" else 1


def cmd_scheduler_status() -> int:
    settings = get_settings()
    status = get_scheduler_status(settings)
    print(f"Agendamento habilitado: {status.enabled}")
    print(f"Período atual: {status.period}")
    print(f"Próxima execução: {status.next_run_at}")
    print(f"Dia/hora: {settings.mensal_schedule_day} às {settings.mensal_schedule_hour:02d}:{settings.mensal_schedule_minute:02d} ({settings.mensal_schedule_timezone})")
    print(f"Scheduler em background: {status.running}")
    if status.last_success_period:
        print(f"Último sucesso: {status.last_success_period} em {status.last_success_at}")
    if status.last_status:
        print(f"Último status: {status.last_status}")
    if status.last_error:
        print(f"Último erro: {status.last_error}")
    return 0


def cmd_test_smtp(args: argparse.Namespace) -> int:
    settings = get_settings()
    if not settings.smtp_host:
        print("ERRO: SMTP_HOST não configurado no .env", file=sys.stderr)
        return 1

    print(f"SMTP: {settings.smtp_host}:{settings.smtp_port} "
          f"(tls={settings.smtp_use_tls}, auth={settings.smtp_use_auth})")
    print(f"From: {settings.smtp_from}")
    print(f"To: {settings.smtp_to}\n")

    try:
        for line in probe_smtp(settings):
            print(f"  {line}")
    except Exception as exc:
        print(f"ERRO na sonda SMTP: {exc}", file=sys.stderr)
        return 1

    if args.probe_only:
        print("\nSonda concluída (sem envio).")
        return 0

    try:
        send_email(
            settings,
            subject="TESTE SMTP — FortiAnalyzer Reports",
            body="E-mail de teste da rotina automática FortiAnalyzer.\n",
            to_addrs=[settings.smtp_to] if settings.smtp_to else [],
        )
    except Exception as exc:
        print(f"ERRO no envio: {exc}", file=sys.stderr)
        return 1

    print(f"\nE-mail de teste enviado para {settings.smtp_to}")
    print("Verifique caixa de entrada e spam.")
    print("Nota: envio via SMTP relay não aparece em 'Itens enviados' do Outlook.")
    return 0


def cmd_send_mensal_email(args: argparse.Namespace) -> int:
    """Reenvia o PDF MENSAL já gerado (sem regerar)."""
    settings = get_settings()
    pdf_path = Path(args.pdf) if args.pdf else settings.output_dir / f"MENSAL_UNIFICADO_{settings.faz_adom}.pdf"
    if not pdf_path.is_file():
        print(f"ERRO: PDF não encontrado: {pdf_path}", file=sys.stderr)
        return 1
    try:
        from forti_report.services.email_delivery import send_mensal_report_email

        send_mensal_report_email(settings, pdf_path)
    except Exception as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1
    print(f"E-mail enviado com anexo: {pdf_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FortiAnalyzer → PDF (Plotly + ReportLab)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("test-connection", help="Testa login, dispositivos e relatórios")
    sub.add_parser("list-units", help="Lista dispositivos (FortiGates) do ADOM")
    sub.add_parser("list-hierarchy", help="Lista unidades regionais e dispositivos")
    sub.add_parser("list-reports", help="Lista nomes de relatórios recentes")

    pull = sub.add_parser("pull-all", help="Importa dados de todos os dispositivos")
    pull.add_argument("--days", type=int, default=60)
    pull.add_argument("--metadata-only", action="store_true")

    pull_h = sub.add_parser("pull-hierarchy", help="Importa e agrupa por unidade regional")
    pull_h.add_argument("--days", type=int, default=60)
    pull_h.add_argument("--metadata-only", action="store_true")

    gen_all = sub.add_parser("generate-all", help="PDF por dispositivo (legado)")
    gen_all.add_argument("--days", type=int, default=60)

    gen_reg = sub.add_parser("generate-unit", help="PDF consolidado de uma unidade regional")
    gen_reg.add_argument("unit_code", help="Código da unidade regional cadastrada no tenant")
    gen_reg.add_argument("--days", type=int, default=60)
    gen_reg.add_argument("--metadata-only", action="store_true")

    gen_regs = sub.add_parser("generate-all-units", help="PDF de cada unidade regional")
    gen_regs.add_argument("--days", type=int, default=60)
    gen_regs.add_argument("--metadata-only", action="store_true")

    gen_mensal = sub.add_parser(
        "generate-mensal-unified",
        help="PDF único MENSAL- RELATÓRIO GERAL (11 dispositivos / 6 unidades regionais)",
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
    gen_wan1.add_argument("unit_code", help="Código da unidade regional cadastrada no tenant")
    gen_wan1.add_argument("--days", type=int, default=60)
    gen_wan1.add_argument("--pdf", type=str, default="")

    sub.add_parser("demo", help="PDF demo com dados fictícios")
    gen = sub.add_parser("generate", help="PDF de um dispositivo específico")
    gen.add_argument("device", help="Nome do dispositivo (ex.: fw-norte-matriz)")

    run_sched = sub.add_parser(
        "run-scheduled-mensal",
        help="Rotina agendada: gera PDF MENSAL e envia por e-mail (Task Scheduler / manual)",
    )
    run_sched.add_argument(
        "--force",
        action="store_true",
        help="Ignora idempotência e janela de horário (teste)",
    )

    sub.add_parser("scheduler-status", help="Exibe status do agendamento mensal")

    test_smtp = sub.add_parser("test-smtp", help="Testa conexão SMTP e envia e-mail de teste")
    test_smtp.add_argument(
        "--probe-only",
        action="store_true",
        help="Só testa conexão (EHLO/MAIL/RCPT), sem enviar",
    )

    send_mail = sub.add_parser(
        "send-mensal-email",
        help="Reenvia o PDF MENSAL já gerado por e-mail (sem regerar)",
    )
    send_mail.add_argument("--pdf", type=str, default="", help="Caminho do PDF (opcional)")

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
        "run-scheduled-mensal": lambda: cmd_run_scheduled_mensal(args),
        "scheduler-status": cmd_scheduler_status,
        "test-smtp": lambda: cmd_test_smtp(args),
        "send-mensal-email": lambda: cmd_send_mensal_email(args),
    }
    return handlers[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
