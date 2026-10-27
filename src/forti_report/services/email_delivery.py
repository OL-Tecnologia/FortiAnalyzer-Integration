"""Envio de e-mail com relatório MENSAL (SMTP relay ou autenticado)."""

from __future__ import annotations

import logging
import smtplib
import socket
import ssl
from dataclasses import dataclass
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


def format_email_subject(when: datetime | None = None, settings: Settings | None = None) -> str:
    ref = when or datetime.now()
    prefix = ""
    if settings and settings.email_subject_prefix.strip():
        prefix = settings.email_subject_prefix.strip()
    elif settings and settings.client_display_name.strip():
        prefix = f"{settings.client_display_name.strip()} | Relatório Mensal FortiAnalyzer"
    else:
        prefix = "Relatório Mensal FortiAnalyzer"
    return f"{prefix} – {ref.strftime('%m/%Y')}"


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
        subject=format_email_subject(when, settings),
        body=EMAIL_BODY_TEMPLATE,
        to_addrs=_parse_recipients(settings.smtp_to),
        cc_addrs=_parse_recipients(settings.smtp_cc),
        pdf_path=pdf_path,
    )


def send_failure_alert(settings: Settings, error: str, *, context: str = "") -> None:
    alert_to = _parse_recipients(settings.smtp_alert_to)
    if not alert_to:
        return

    label = settings.client_display_name or settings.faz_adom or "FortiAnalyzer"
    subject = f"FALHA — Relatório Mensal {label}"
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


TEST_EMAIL_SUBJECT = "Teste de envio — Relatório FortiAnalyzer"
TEST_EMAIL_BODY = (
    "Este é um e-mail de teste do FortiAnalyzer Reports.\n\n"
    "Se você recebeu esta mensagem, o envio automático está conseguindo sair por este servidor.\n"
    "O teste não traz o relatório em anexo."
)


@dataclass
class EmailTestResult:
    ok: bool
    message: str
    problem: str = ""
    fix: str = ""


def _failure(problem: str, fix: str) -> EmailTestResult:
    return EmailTestResult(ok=False, message=problem, problem=problem, fix=fix)


def _error_text(exc: BaseException) -> str:
    parts = [str(exc)]
    code = getattr(exc, "smtp_code", None)
    if code:
        parts.append(str(code))
    err = getattr(exc, "smtp_error", "")
    if isinstance(err, bytes):
        parts.append(err.decode("utf-8", errors="replace"))
    elif err:
        parts.append(str(err))
    return " ".join(parts).lower()


def _is_gmail(host: str) -> bool:
    return "gmail.com" in host or "googlemail.com" in host


def _is_microsoft(host: str) -> bool:
    lowered = host.lower()
    return "office365" in lowered or "outlook" in lowered


def _password_has_edge_space(env_path: Path) -> bool:
    if not env_path.is_file():
        return False
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    for line in lines:
        if line.startswith("SMTP_PASSWORD="):
            raw = line.split("=", 1)[1]
            return raw != raw.strip().strip('"').strip("'")
    return False


def explain_email_failure(exc: BaseException, settings: Settings) -> tuple[str, str]:
    """Traduz a falha de SMTP para o problema e o que fazer na instalação."""
    text = _error_text(exc)
    host = (settings.smtp_host or "").strip()
    gmail = _is_gmail(host)
    microsoft = _is_microsoft(host)

    if isinstance(exc, ValueError):
        if "smtp_host" in text:
            return (
                "O servidor de e-mail não está configurado.",
                "No arquivo .env, ao lado do programa, preencha SMTP_HOST. "
                "Gmail: smtp.gmail.com. Microsoft: smtp.office365.com. "
                "Salve o arquivo e reinicie o programa.",
            )
        if "destinatário" in text:
            return (
                "Não há destinatário para enviar o e-mail.",
                "Preencha Destinatário (To) com o e-mail de quem deve receber o relatório. "
                "Mais de um endereço pode ser separado por vírgula. Salve a configuração.",
            )
        if "smtp_user" in text or "smtp_password" in text:
            return (
                "O envio pede usuário e senha, mas um dos dois está vazio.",
                "Preencha SMTP_USER e SMTP_PASSWORD no arquivo .env e reinicie o programa. "
                "No Gmail, SMTP_PASSWORD tem que ser uma senha de app, não a senha normal da caixa.",
            )

    if isinstance(exc, (TimeoutError, socket.timeout)) or "timed out" in text or "10060" in text:
        return (
            f"O servidor {host or 'SMTP'} não respondeu a tempo.",
            "Confira SMTP_HOST e SMTP_PORT no arquivo .env. "
            "A porta 587 precisa estar liberada no firewall desta máquina. "
            "Gmail e Microsoft usam smtp.gmail.com ou smtp.office365.com na porta 587, com TLS ligado. "
            "Reinicie o programa depois de salvar o .env.",
        )

    if isinstance(exc, socket.gaierror) or "getaddrinfo" in text or "name or service not known" in text:
        return (
            f"Não foi possível encontrar o servidor {host or 'SMTP'}.",
            "Confira o nome em SMTP_HOST no arquivo .env e se esta máquina acessa a internet. "
            "Gmail: smtp.gmail.com. Microsoft: smtp.office365.com. Reinicie o programa depois de salvar.",
        )

    if isinstance(exc, ConnectionRefusedError) or "connection refused" in text or "10061" in text:
        return (
            f"O servidor {host or 'SMTP'} recusou a conexão na porta {settings.smtp_port}.",
            "Confira SMTP_PORT. Gmail e Microsoft na porta 587 usam TLS, não SSL direto. "
            "No .env: SMTP_USE_TLS=true e SMTP_USE_SSL=false. "
            "Se a rede só libera a porta 25 de um relay interno, aponte SMTP_HOST para esse relay. "
            "Reinicie o programa depois de salvar.",
        )

    if isinstance(exc, ssl.SSLError) or "wrong version number" in text or "certificate verify failed" in text:
        return (
            "A conexão segura com o servidor de e-mail falhou.",
            "Para a porta 587, deixe SMTP_USE_TLS=true e SMTP_USE_SSL=false. "
            "Para a porta 465, deixe SMTP_USE_SSL=true e SMTP_USE_TLS=false. "
            "Salve o .env e reinicie o programa.",
        )

    if (
        isinstance(exc, smtplib.SMTPAuthenticationError)
        or "535" in text
        or "534" in text
        or "username and password not accepted" in text
        or "application-specific password" in text
        or "authentication unsuccessful" in text
    ):
        if gmail:
            return (
                "O Gmail recusou o usuário ou a senha.",
                "O Gmail não aceita a senha normal da caixa neste programa. "
                "Na conta Google, com a verificação em duas etapas ligada, crie uma senha de app para e-mail "
                "e coloque só essa senha em SMTP_PASSWORD, sem espaço antes ou depois do sinal de igual. "
                "SMTP_USER e o remetente (From) precisam ser o mesmo e-mail. "
                "Se a caixa ainda estiver na Microsoft, volte SMTP_HOST para smtp.office365.com. "
                "Salve o .env e reinicie o programa.",
            )
        if microsoft:
            return (
                "A Microsoft recusou o usuário ou a senha.",
                "Confira SMTP_USER e SMTP_PASSWORD no arquivo .env, sem espaço antes ou depois da senha. "
                "Na caixa Microsoft 365, o envio SMTP autenticado precisa estar habilitado. "
                "O remetente (From) precisa ser o mesmo e-mail de SMTP_USER. "
                "Salve o .env e reinicie o programa.",
            )
        return (
            "O servidor de e-mail recusou o usuário ou a senha.",
            "Confira SMTP_USER e SMTP_PASSWORD no arquivo .env, sem espaço antes ou depois da senha. "
            "SMTP_HOST tem que ser o servidor da caixa que está em SMTP_USER. "
            "Salve o .env e reinicie o programa.",
        )

    if isinstance(exc, smtplib.SMTPSenderRefused) or "from address" in text or "553" in text:
        return (
            "O servidor recusou o remetente.",
            "Preencha Remetente (From) com o mesmo e-mail de SMTP_USER. "
            "No Gmail e na Microsoft o remetente precisa ser a conta que faz o login. Salve e teste de novo.",
        )

    if isinstance(exc, (smtplib.SMTPRecipientsRefused, smtplib.SMTPDataError)) or "recipient" in text:
        return (
            "O servidor recusou um destinatário.",
            "Confira Destinatário (To) e Cópia (Cc). Use e-mails válidos, separados por vírgula se houver mais de um. "
            "Salve a configuração e teste de novo.",
        )

    if "starttls" in text:
        return (
            "O servidor exigiu uma conexão segura e ela não foi aceita.",
            "No arquivo .env, para a porta 587, deixe SMTP_USE_TLS=true e SMTP_USE_SSL=false. "
            "Salve e reinicie o programa.",
        )

    return (
        "O e-mail não foi enviado.",
        "Confira SMTP_HOST, SMTP_PORT, SMTP_USER e SMTP_PASSWORD no arquivo .env, "
        "e o remetente e o destinatário na configuração do cliente. "
        "Salve, reinicie o programa e teste de novo. "
        f"Detalhe técnico: {exc}",
    )


def send_test_message(settings: Settings, *, env_path: Path | None = None) -> EmailTestResult:
    """Envia um e-mail de teste e devolve o problema e a correção quando falha."""
    from forti_report.runtime_paths import project_root

    host = (settings.smtp_host or "").strip()
    recipients = _parse_recipients(settings.smtp_to)
    sender = (settings.smtp_from or "").strip()
    user = (settings.smtp_user or "").strip()

    if not host:
        return _failure(
            "O servidor de e-mail não está configurado.",
            "No arquivo .env, ao lado do programa, preencha SMTP_HOST. "
            "Gmail: smtp.gmail.com. Microsoft: smtp.office365.com. "
            "Salve o arquivo e reinicie o programa.",
        )
    if not sender:
        return _failure(
            "O remetente está vazio.",
            "Preencha Remetente (From) com o e-mail da conta que envia. "
            "Ele precisa ser o mesmo valor de SMTP_USER no arquivo .env. Salve a configuração.",
        )
    if not recipients:
        return _failure(
            "Não há destinatário para enviar o e-mail.",
            "Preencha Destinatário (To) com o e-mail de quem deve receber o relatório. "
            "Mais de um endereço pode ser separado por vírgula. Salve a configuração.",
        )
    if settings.smtp_use_auth and (not user or not settings.smtp_password):
        return _failure(
            "O envio pede usuário e senha, mas um dos dois está vazio.",
            "Preencha SMTP_USER e SMTP_PASSWORD no arquivo .env e reinicie o programa. "
            "No Gmail, SMTP_PASSWORD tem que ser uma senha de app, não a senha normal da caixa.",
        )
    if settings.smtp_password and settings.smtp_password != settings.smtp_password.strip():
        return _failure(
            "A senha do e-mail tem espaço no começo ou no fim.",
            "No arquivo .env, deixe SMTP_PASSWORD=senha sem espaço antes ou depois do valor. "
            "Salve e reinicie o programa.",
        )
    env_file = env_path or (project_root() / ".env")
    if settings.smtp_use_auth and _password_has_edge_space(env_file):
        return _failure(
            "A senha do e-mail no arquivo .env tem espaço no começo ou no fim.",
            "Abra o .env ao lado do programa e apague o espaço antes ou depois da senha em SMTP_PASSWORD. "
            "Salve e reinicie o programa.",
        )
    if settings.smtp_use_auth and user and sender.lower() != user.lower() and (_is_gmail(host) or _is_microsoft(host)):
        return _failure(
            "O remetente é diferente da conta que faz o login no servidor de e-mail.",
            f"Deixe Remetente (From) igual a {user}. No Gmail e na Microsoft o remetente precisa ser essa conta. "
            "Salve a configuração e teste de novo.",
        )
    if (_is_gmail(host) or _is_microsoft(host)) and settings.smtp_port == 587 and settings.smtp_use_ssl:
        return _failure(
            "A porta 587 está combinada com SSL direto.",
            "No arquivo .env deixe SMTP_PORT=587, SMTP_USE_TLS=true e SMTP_USE_SSL=false. "
            "Salve e reinicie o programa.",
        )
    if (_is_gmail(host) or _is_microsoft(host)) and settings.smtp_port == 465 and not settings.smtp_use_ssl:
        return _failure(
            "A porta 465 precisa de SSL direto.",
            "No arquivo .env deixe SMTP_USE_SSL=true e SMTP_USE_TLS=false, ou use a porta 587 com TLS ligado e SSL desligado. "
            "Salve e reinicie o programa.",
        )

    try:
        send_email(
            settings,
            subject=TEST_EMAIL_SUBJECT,
            body=TEST_EMAIL_BODY,
            to_addrs=recipients,
            cc_addrs=_parse_recipients(settings.smtp_cc),
        )
    except Exception as exc:
        problem, fix = explain_email_failure(exc, settings)
        logger.warning("Teste de e-mail falhou: %s", exc)
        return _failure(problem, fix)

    target = ", ".join(recipients)
    return EmailTestResult(
        ok=True,
        message=(
            f"E-mail de teste enviado para {target}. "
            "Confira a caixa de entrada e a pasta de spam. Este teste não anexa o relatório."
        ),
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
