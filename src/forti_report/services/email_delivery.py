"""Envio de e-mail com relatório MENSAL (SMTP relay ou autenticado)."""

from __future__ import annotations

import logging
import smtplib
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from pathlib import Path

from forti_report.config import Settings

logger = logging.getLogger(__name__)

EMAIL_BODY_TEMPLATE = """Bom dia!

Conforme nossa rotina de acompanhamento do ambiente, encaminhamos o Relatório Mensal do FortiAnalyzer, contendo a consolidação dos indicadores operacionais e de segurança referentes ao período analisado.

O relatório apresenta informações de utilização da rede, consumo de banda, aplicações, categorias de navegação, políticas de firewall, eventos de segurança e demais métricas coletadas dos dispositivos monitorados.

Em caso de dúvidas, nossa equipe permanece à disposição."""


def format_email_subject(when: datetime | None = None) -> str:
    ref = when or datetime.now()
    return f"Cruz Azul | Relatório Mensal FortiAnalyzer – {ref.strftime('%m/%Y')}"


def _parse_recipients(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _attach_pdf(message: MIMEMultipart, pdf_path: Path) -> None:
    part = MIMEBase("application", "pdf")
    part.set_payload(pdf_path.read_bytes())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{pdf_path.name}"')
    message.attach(part)


def _append_email_log(settings: Settings, line: str) -> None:
    logs_dir = settings.output_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    path = logs_dir / f"email-{datetime.now().strftime('%Y-%m-%d')}.log"
    try:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"{datetime.now().isoformat(timespec='seconds')} {line}\n")
    except OSError:
        logger.warning("Não foi possível gravar log de e-mail")


def send_email(
    settings: Settings,
    *,
    subject: str,
    body: str,
    to_addrs: list[str],
    cc_addrs: list[str] | None = None,
    pdf_path: Path | None = None,
) -> None:
    if not settings.smtp_host:
        raise ValueError("SMTP_HOST não configurado")

    to_addrs = [addr for addr in to_addrs if addr]
    if not to_addrs:
        raise ValueError("Nenhum destinatário informado")

    message = MIMEMultipart()
    message["From"] = settings.smtp_from
    message["To"] = ", ".join(to_addrs)
    if cc_addrs:
        cc_addrs = [addr for addr in cc_addrs if addr]
        if cc_addrs:
            message["Cc"] = ", ".join(cc_addrs)
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain=settings.smtp_from.split("@")[-1])
    message.attach(MIMEText(body, "plain", "utf-8"))

    if pdf_path is not None:
        if not pdf_path.is_file():
            raise FileNotFoundError(f"PDF não encontrado: {pdf_path}")
        _attach_pdf(message, pdf_path)

    recipients = to_addrs + (cc_addrs or [])

    timeout = settings.smtp_timeout
    if settings.smtp_use_ssl:
        server: smtplib.SMTP = smtplib.SMTP_SSL(
            settings.smtp_host, settings.smtp_port, timeout=timeout
        )
    else:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=timeout)

    try:
        server.ehlo()
        if settings.smtp_use_tls and not settings.smtp_use_ssl:
            server.starttls()
            server.ehlo()
        if settings.smtp_use_auth:
            if not settings.smtp_user or not settings.smtp_password:
                raise ValueError("SMTP_USE_AUTH=true exige SMTP_USER e SMTP_PASSWORD")
            server.login(settings.smtp_user, settings.smtp_password)
        refused = server.sendmail(settings.smtp_from, recipients, message.as_string())
        if refused:
            detail = "; ".join(f"{addr}: {err}" for addr, err in refused.items())
            raise smtplib.SMTPException(f"Destinatário(s) recusado(s) pelo servidor: {detail}")
    finally:
        try:
            server.quit()
        except smtplib.SMTPException:
            pass

    attachment = pdf_path.name if pdf_path else "(sem anexo)"
    log_line = (
        f"OK host={settings.smtp_host}:{settings.smtp_port} "
        f"from={settings.smtp_from} to={','.join(recipients)} subject={subject!r} attachment={attachment}"
    )
    logger.info(log_line)
    _append_email_log(settings, log_line)


def send_mensal_report_email(settings: Settings, pdf_path: Path, *, when: datetime | None = None) -> None:
    send_email(
        settings,
        subject=format_email_subject(when),
        body=EMAIL_BODY_TEMPLATE,
        to_addrs=_parse_recipients(settings.smtp_to),
        cc_addrs=_parse_recipients(settings.smtp_cc),
        pdf_path=pdf_path,
    )


def send_failure_alert(settings: Settings, error: str, *, context: str = "") -> None:
    alert_to = _parse_recipients(settings.smtp_alert_to)
    if not alert_to:
        return

    subject = "FALHA — Relatório Mensal FortiAnalyzer Cruz Azul"
    body = "Falha na rotina automática de geração/envio do relatório MENSAL.\n\n"
    if context:
        body += f"Contexto: {context}\n\n"
    body += f"Erro:\n{error}\n"

    send_email(
        settings,
        subject=subject,
        body=body,
        to_addrs=alert_to,
    )


def probe_smtp(settings: Settings) -> list[str]:
    """Testa conexão SMTP (EHLO + MAIL/RCPT) sem enviar DATA."""
    lines: list[str] = []
    timeout = settings.smtp_timeout
    if settings.smtp_use_ssl:
        server: smtplib.SMTP = smtplib.SMTP_SSL(
            settings.smtp_host, settings.smtp_port, timeout=timeout
        )
    else:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=timeout)
    try:
        code, resp = server.ehlo()
        lines.append(f"EHLO {code} {resp!r}")
        if settings.smtp_use_tls and not settings.smtp_use_ssl:
            server.starttls()
            code, resp = server.ehlo()
            lines.append(f"STARTTLS+EHLO {code} {resp!r}")
        if settings.smtp_use_auth:
            server.login(settings.smtp_user, settings.smtp_password)
            lines.append("AUTH OK")
        for label, addr in (("MAIL FROM", settings.smtp_from), ("RCPT TO", settings.smtp_to)):
            if label.startswith("MAIL"):
                code, resp = server.mail(addr)
            else:
                code, resp = server.rcpt(addr)
            lines.append(f"{label} {code} {resp!r}")
    finally:
        try:
            server.quit()
        except smtplib.SMTPException:
            pass
    return lines
