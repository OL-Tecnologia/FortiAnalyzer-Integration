#!/usr/bin/env python3
"""Assistente interativo para configurar agendamento mensal + e-mail no .env.

Campos configuráveis por cliente (sem hardcode de senha no código):
  - FAZ_USER / FAZ_PASSWORD
  - Dia / hora / fuso do agendamento
  - SMTP From / To / Cc / alerta de falha

Segurança: senhas só no .env local (.gitignore); nunca versionadas.
"""

from __future__ import annotations

import argparse
import getpass
import shutil
import sys
from pathlib import Path

from forti_report.runtime_paths import bundled_config_env, project_root
from forti_report.services.env_file import apply_env_updates, mask_secret, read_env_file

# Campos que o assistente edita (e que devem permanecer configuráveis)
SCHEDULER_KEYS = [
    "FAZ_USER",
    "FAZ_PASSWORD",
    "MENSAL_SCHEDULE_ENABLED",
    "MENSAL_SCHEDULE_DAY",
    "MENSAL_SCHEDULE_HOUR",
    "MENSAL_SCHEDULE_MINUTE",
    "MENSAL_SCHEDULE_TIMEZONE",
    "MENSAL_SCHEDULE_DAYS",
    "MENSAL_SCHEDULE_FORCE_DOWNLOAD",
    "MENSAL_SCHEDULE_MAX_RETRIES",
    "MENSAL_SCHEDULE_RETRY_HOURS",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USE_TLS",
    "SMTP_USE_SSL",
    "SMTP_USE_AUTH",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "SMTP_TIMEOUT",
    "SMTP_FROM",
    "SMTP_TO",
    "SMTP_CC",
    "SMTP_ALERT_TO",
]

SECRET_KEYS = {"FAZ_PASSWORD", "SMTP_PASSWORD"}

# Defaults de PRODUÇÃO (sem senhas)
DEFAULTS: dict[str, str] = {
    "FAZ_USER": "",
    "FAZ_PASSWORD": "",
    "MENSAL_SCHEDULE_ENABLED": "true",
    "MENSAL_SCHEDULE_DAY": "5",
    "MENSAL_SCHEDULE_HOUR": "6",
    "MENSAL_SCHEDULE_MINUTE": "0",
    "MENSAL_SCHEDULE_TIMEZONE": "America/Sao_Paulo",
    "MENSAL_SCHEDULE_DAYS": "60",
    "MENSAL_SCHEDULE_FORCE_DOWNLOAD": "true",
    "MENSAL_SCHEDULE_MAX_RETRIES": "3",
    "MENSAL_SCHEDULE_RETRY_HOURS": "2",
    "SMTP_HOST": "smtp.office365.com",
    "SMTP_PORT": "587",
    "SMTP_USE_TLS": "true",
    "SMTP_USE_SSL": "false",
    "SMTP_USE_AUTH": "true",
    "SMTP_USER": "notificacao@onelinea.com.br",
    "SMTP_PASSWORD": "",
    "SMTP_TIMEOUT": "60",
    "SMTP_FROM": "notificacao@onelinea.com.br",
    "SMTP_TO": "leandro.souza@cruzazulsp.com.br",
    "SMTP_CC": "",
    "SMTP_ALERT_TO": "roliveira@onelinea.com.br",
}


def _ensure_env_file(env_path: Path) -> None:
    if env_path.is_file():
        return
    for template in (project_root() / ".env.example", bundled_config_env()):
        if template and template.is_file():
            shutil.copy2(template, env_path)
            print(f"Arquivo criado a partir de {template.name}")
            return
    env_path.write_text("# FortiAnalyzer Reports\n", encoding="utf-8")
    print("Arquivo .env criado (vazio).")


def _prompt(label: str, current: str, *, default: str = "", secret: bool = False) -> str:
    hint = current if current else default
    if secret and current:
        display = mask_secret(current)
    else:
        display = hint or "(vazio)"
    suffix = " [Enter mantém]" if current else (f" [Enter={default}]" if default else "")
    while True:
        if secret:
            typed = getpass.getpass(f"{label}{suffix} (atual: {display}): ")
        else:
            typed = input(f"{label}{suffix} (atual: {display}): ").strip()
        if typed:
            return typed
        if current:
            return current
        if default:
            return default
        return ""


def _prompt_bool(label: str, current: str, *, default: bool = True) -> str:
    default_str = "s" if default else "n"
    current_bool = current.lower() in {"1", "true", "yes", "sim", "s"}
    current_label = "sim" if current_bool else "nao"
    while True:
        typed = input(
            f"{label} (s/n) [atual: {current_label}, Enter={default_str}]: "
        ).strip().lower()
        if not typed:
            if current:
                return "true" if current_bool else "false"
            return "true" if default else "false"
        if typed in {"s", "sim", "y", "yes", "true", "1"}:
            return "true"
        if typed in {"n", "nao", "no", "false", "0"}:
            return "false"
        print("  Responda s ou n.")


def _prompt_int(label: str, current: str, *, default: int, min_value: int, max_value: int) -> str:
    while True:
        typed = input(
            f"{label} [{min_value}-{max_value}] (atual: {current or default}, Enter mantém): "
        ).strip()
        if not typed:
            return current or str(default)
        try:
            value = int(typed)
        except ValueError:
            print("  Informe um número inteiro.")
            continue
        if value < min_value or value > max_value:
            print(f"  Valor deve estar entre {min_value} e {max_value}.")
            continue
        return str(value)


def _collect_updates(current: dict[str, str]) -> dict[str, str]:
    merged = {**DEFAULTS, **current}
    updates: dict[str, str] = {}

    print("\n=== 1) Credenciais FortiAnalyzer (configurável / segredo) ===")
    print("  Conta de serviço da automação. Senha NÃO é exibida nem versionada.")
    updates["FAZ_USER"] = _prompt(
        "Usuário FAZ",
        merged.get("FAZ_USER", ""),
        default=DEFAULTS["FAZ_USER"],
    )
    updates["FAZ_PASSWORD"] = _prompt(
        "Senha FAZ",
        merged.get("FAZ_PASSWORD", ""),
        secret=True,
    )

    print("\n=== 2) Agendamento (configurável: dia / hora) ===")
    print("  Padrão produção: dia 5 às 06:00 (America/Sao_Paulo).")
    updates["MENSAL_SCHEDULE_ENABLED"] = _prompt_bool(
        "Habilitar agendamento automático",
        merged.get("MENSAL_SCHEDULE_ENABLED", DEFAULTS["MENSAL_SCHEDULE_ENABLED"]),
        default=True,
    )
    updates["MENSAL_SCHEDULE_DAY"] = _prompt_int(
        "Dia do mês",
        merged.get("MENSAL_SCHEDULE_DAY", DEFAULTS["MENSAL_SCHEDULE_DAY"]),
        default=5,
        min_value=1,
        max_value=28,
    )
    updates["MENSAL_SCHEDULE_HOUR"] = _prompt_int(
        "Hora",
        merged.get("MENSAL_SCHEDULE_HOUR", DEFAULTS["MENSAL_SCHEDULE_HOUR"]),
        default=6,
        min_value=0,
        max_value=23,
    )
    updates["MENSAL_SCHEDULE_MINUTE"] = _prompt_int(
        "Minuto",
        merged.get("MENSAL_SCHEDULE_MINUTE", DEFAULTS["MENSAL_SCHEDULE_MINUTE"]),
        default=0,
        min_value=0,
        max_value=59,
    )
    updates["MENSAL_SCHEDULE_TIMEZONE"] = _prompt(
        "Fuso horário",
        merged.get("MENSAL_SCHEDULE_TIMEZONE", DEFAULTS["MENSAL_SCHEDULE_TIMEZONE"]),
        default=DEFAULTS["MENSAL_SCHEDULE_TIMEZONE"],
    )
    updates["MENSAL_SCHEDULE_DAYS"] = _prompt_int(
        "Janela de busca no FAZ (dias)",
        merged.get("MENSAL_SCHEDULE_DAYS", DEFAULTS["MENSAL_SCHEDULE_DAYS"]),
        default=60,
        min_value=1,
        max_value=365,
    )
    updates["MENSAL_SCHEDULE_FORCE_DOWNLOAD"] = _prompt_bool(
        "Forçar download do FAZ (ignorar cache)",
        merged.get("MENSAL_SCHEDULE_FORCE_DOWNLOAD", DEFAULTS["MENSAL_SCHEDULE_FORCE_DOWNLOAD"]),
        default=True,
    )
    updates["MENSAL_SCHEDULE_MAX_RETRIES"] = _prompt_int(
        "Máximo de tentativas em falha",
        merged.get("MENSAL_SCHEDULE_MAX_RETRIES", DEFAULTS["MENSAL_SCHEDULE_MAX_RETRIES"]),
        default=3,
        min_value=1,
        max_value=10,
    )
    updates["MENSAL_SCHEDULE_RETRY_HOURS"] = _prompt_int(
        "Intervalo entre tentativas (horas)",
        merged.get("MENSAL_SCHEDULE_RETRY_HOURS", DEFAULTS["MENSAL_SCHEDULE_RETRY_HOURS"]),
        default=2,
        min_value=1,
        max_value=24,
    )

    print("\n=== 3) E-mail SMTP (configurável: From / To / alerta) ===")
    print("  Opção A: smtp.office365.com:587 + autenticação (produção)")
    print("  Opção B: mail.onelinea.com.br:25 sem auth (só rede interna)")
    print("  NÃO use mail.protection.outlook.com\n")
    updates["SMTP_HOST"] = _prompt(
        "Servidor SMTP",
        merged.get("SMTP_HOST", DEFAULTS["SMTP_HOST"]),
        default=DEFAULTS["SMTP_HOST"],
    )
    updates["SMTP_PORT"] = _prompt_int(
        "Porta SMTP",
        merged.get("SMTP_PORT", DEFAULTS["SMTP_PORT"]),
        default=587,
        min_value=1,
        max_value=65535,
    )
    updates["SMTP_USE_TLS"] = _prompt_bool(
        "Usar STARTTLS",
        merged.get("SMTP_USE_TLS", DEFAULTS["SMTP_USE_TLS"]),
        default=True,
    )
    updates["SMTP_USE_SSL"] = _prompt_bool(
        "Usar SSL direto",
        merged.get("SMTP_USE_SSL", DEFAULTS["SMTP_USE_SSL"]),
        default=False,
    )
    updates["SMTP_USE_AUTH"] = _prompt_bool(
        "Autenticar no SMTP",
        merged.get("SMTP_USE_AUTH", DEFAULTS["SMTP_USE_AUTH"]),
        default=True,
    )
    updates["SMTP_USER"] = _prompt(
        "Usuário SMTP",
        merged.get("SMTP_USER", DEFAULTS["SMTP_USER"]),
        default=DEFAULTS["SMTP_USER"],
    )
    updates["SMTP_PASSWORD"] = _prompt(
        "Senha SMTP",
        merged.get("SMTP_PASSWORD", ""),
        secret=True,
    )
    updates["SMTP_TIMEOUT"] = _prompt_int(
        "Timeout SMTP (segundos)",
        merged.get("SMTP_TIMEOUT", DEFAULTS["SMTP_TIMEOUT"]),
        default=60,
        min_value=10,
        max_value=300,
    )
    updates["SMTP_FROM"] = _prompt(
        "Remetente (From)",
        merged.get("SMTP_FROM", DEFAULTS["SMTP_FROM"]),
        default=DEFAULTS["SMTP_FROM"],
    )
    updates["SMTP_TO"] = _prompt(
        "Destinatário cliente (To)",
        merged.get("SMTP_TO", DEFAULTS["SMTP_TO"]),
        default=DEFAULTS["SMTP_TO"],
    )
    updates["SMTP_CC"] = _prompt("Cópia (Cc)", merged.get("SMTP_CC", ""))
    updates["SMTP_ALERT_TO"] = _prompt(
        "Alerta de falha (interno)",
        merged.get("SMTP_ALERT_TO", DEFAULTS["SMTP_ALERT_TO"]),
        default=DEFAULTS["SMTP_ALERT_TO"],
    )
    return updates


def _print_summary(values: dict[str, str]) -> None:
    print("\n=== Resumo (senhas mascaradas) ===")
    for key in SCHEDULER_KEYS:
        value = values.get(key, "")
        if key in SECRET_KEYS:
            value = mask_secret(value)
        print(f"  {key}={value}")


def _validate_required(updates: dict[str, str]) -> list[str]:
    warnings: list[str] = []
    if updates.get("MENSAL_SCHEDULE_ENABLED", "").lower() == "true":
        if not updates.get("FAZ_USER") or not updates.get("FAZ_PASSWORD"):
            warnings.append("FAZ_USER/FAZ_PASSWORD vazios — a rotina agendada falhará no login.")
        if not updates.get("SMTP_HOST"):
            warnings.append("SMTP_HOST vazio — o envio de e-mail falhará.")
        if updates.get("SMTP_USE_AUTH", "").lower() == "true" and not updates.get("SMTP_PASSWORD"):
            warnings.append("SMTP_PASSWORD vazio com SMTP_USE_AUTH=true — autenticação falhará.")
        if not updates.get("SMTP_TO"):
            warnings.append("SMTP_TO vazio — sem destinatário do cliente.")
    return warnings


def cmd_show(env_path: Path) -> int:
    _ensure_env_file(env_path)
    current = read_env_file(env_path)
    merged = {**DEFAULTS, **current}
    _print_summary(merged)
    print(f"\nArquivo: {env_path}")
    print("Segurança: .env está no .gitignore — não versionar senhas.")
    return 0


def cmd_configure(env_path: Path, *, yes: bool = False) -> int:
    _ensure_env_file(env_path)
    current = read_env_file(env_path)
    updates = _collect_updates(current)
    _print_summary(updates)

    for warning in _validate_required(updates):
        print(f"\nAVISO: {warning}")

    if not yes:
        confirm = input("\nSalvar no .env? (s/n) [s]: ").strip().lower()
        if confirm in {"n", "nao", "no"}:
            print("Cancelado — nenhuma alteração gravada.")
            return 0

    apply_env_updates(env_path, updates)
    print(f"\nConfiguração salva em: {env_path}")
    print("\nPróximos passos:")
    print("  1. Conferir: python scripts/configure_scheduler.py --show")
    print("  2. Status:   python -m forti_report.cli scheduler-status")
    print("  3. Teste SMTP: python -m forti_report.cli test-smtp --probe-only")
    print("  4. Task Scheduler (backup): scripts\\run-scheduled-mensal.ps1")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Configura agendamento mensal e e-mail no .env. "
            "Campos FAZ, dia/hora e destinatários são editáveis por cliente."
        ),
    )
    parser.add_argument(
        "--env",
        type=Path,
        default=project_root() / ".env",
        help="Caminho do .env (padrão: raiz do projeto)",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Exibe configuração atual (senhas mascaradas)",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Salva sem confirmar",
    )
    args = parser.parse_args(argv)

    print("FortiAnalyzer — Configuração PRODUÇÃO (agendamento + e-mail)")
    print("Campos configuráveis: FAZ login, dia/hora, From/To/alerta")
    print("Segurança: senhas só no .env local (não versionar)")
    print(f"Projeto: {project_root()}")

    if args.show:
        return cmd_show(args.env)
    return cmd_configure(args.env, yes=args.yes)


if __name__ == "__main__":
    raise SystemExit(main())
