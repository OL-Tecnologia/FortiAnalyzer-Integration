"""Autenticação Super Admin do portal (senha em PORTAL_ADMIN_PASSWORD)."""

from __future__ import annotations

import hmac
import os
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from forti_report.config import Settings, get_settings
from forti_report.runtime_paths import project_root
from forti_report.services.env_file import apply_env_updates

# Valor do template de instalação. Não autentica: a primeira entrada cria a senha.
_INSTALL_PASSWORD = "altereestasenha"
_MIN_PASSWORD_LENGTH = 8


class AdminAuthError(Exception):
    pass


class AdminRateLimitError(AdminAuthError):
    pass


class AdminSetupError(AdminAuthError):
    status_code = 400


class AdminAlreadyConfigured(AdminSetupError):
    status_code = 409


@dataclass
class AdminSession:
    session_id: str
    expires_at: float
    created_at: float = field(default_factory=time.time)

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.expires_at

    def expires_at_iso(self) -> str:
        return datetime.fromtimestamp(self.expires_at, tz=timezone.utc).isoformat()


class AdminSessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, AdminSession] = {}
        self._lock = threading.Lock()
        self._attempts: dict[str, list[float]] = {}

    def check_rate_limit(self, key: str, *, max_attempts: int = 8, window_seconds: int = 300) -> None:
        now = time.time()
        with self._lock:
            attempts = [t for t in self._attempts.get(key, []) if now - t < window_seconds]
            if len(attempts) >= max_attempts:
                raise AdminRateLimitError("Muitas tentativas. Aguarde alguns minutos.")
            attempts.append(now)
            self._attempts[key] = attempts

    def create(self, *, ttl_seconds: int) -> AdminSession:
        record = AdminSession(
            session_id=secrets.token_urlsafe(32),
            expires_at=time.time() + ttl_seconds,
        )
        with self._lock:
            self._prune()
            self._sessions[record.session_id] = record
        return record

    def get(self, session_id: str | None) -> AdminSession | None:
        if not session_id:
            return None
        with self._lock:
            self._prune()
            rec = self._sessions.get(session_id)
            if rec and rec.is_expired:
                self._sessions.pop(session_id, None)
                return None
            return rec

    def invalidate(self, session_id: str | None) -> None:
        if not session_id:
            return
        with self._lock:
            self._sessions.pop(session_id, None)

    def _prune(self) -> None:
        now = time.time()
        expired = [sid for sid, rec in self._sessions.items() if rec.expires_at <= now]
        for sid in expired:
            self._sessions.pop(sid, None)


_store = AdminSessionStore()
_password_lock = threading.Lock()


def get_admin_store() -> AdminSessionStore:
    return _store


def _password_value(settings: Settings) -> str:
    return (settings.portal_admin_password or "").strip()


def _is_install_password(value: str) -> bool:
    return value.casefold() == _INSTALL_PASSWORD


def admin_password_configured(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    value = _password_value(settings)
    return bool(value) and not _is_install_password(value)


def _passwords_match(provided: str, expected: str) -> bool:
    """compare_digest exige mesmo tamanho — senão levanta ValueError (vira 500 no API)."""
    left = provided.encode("utf-8")
    right = expected.encode("utf-8")
    if len(left) != len(right):
        return False
    return hmac.compare_digest(left, right)


def authenticate_admin(
    password: str,
    settings: Settings | None = None,
    *,
    rate_limit_key: str | None = None,
) -> AdminSession:
    settings = settings or get_settings()
    expected = _password_value(settings)
    provided = (password or "").strip()
    if not admin_password_configured(settings):
        raise AdminAuthError(
            "A senha do Super Admin ainda não foi criada. Crie a senha nesta tela."
        )
    if rate_limit_key:
        _store.check_rate_limit(rate_limit_key)
    if not _passwords_match(provided, expected):
        raise AdminAuthError("Senha inválida")
    ttl = max(5, settings.portal_admin_session_ttl_minutes * 60)
    return _store.create(ttl_seconds=ttl)


def invalidate_admin_session(session_id: str | None) -> None:
    _store.invalidate(session_id)


def set_initial_admin_password(
    password: str,
    confirm: str,
    *,
    env_path: Path | None = None,
    rate_limit_key: str | None = None,
) -> AdminSession:
    """Grava a senha no .env na primeira entrada e abre a sessão."""
    if rate_limit_key:
        _store.check_rate_limit(rate_limit_key)
    chosen = (password or "").strip()
    repeated = (confirm or "").strip()
    if len(chosen) < _MIN_PASSWORD_LENGTH:
        raise AdminSetupError("A senha precisa ter pelo menos 8 caracteres.")
    if chosen != repeated:
        raise AdminSetupError("A confirmação não confere com a senha.")
    if _is_install_password(chosen):
        raise AdminSetupError("Escolha uma senha própria. A senha de instalação não entra.")
    if any(char in chosen for char in "\r\n"):
        raise AdminSetupError("A senha não pode ter quebra de linha.")

    with _password_lock:
        settings = get_settings()
        if admin_password_configured(settings):
            raise AdminAlreadyConfigured(
                "A senha do Super Admin já foi definida. "
                "Se esqueceu, não há como entrar de novo."
            )
        target = env_path or (project_root() / ".env")
        apply_env_updates(target, {"PORTAL_ADMIN_PASSWORD": chosen})
        os.environ["PORTAL_ADMIN_PASSWORD"] = chosen
        fresh = get_settings()
        ttl = max(5, fresh.portal_admin_session_ttl_minutes * 60)
        return _store.create(ttl_seconds=ttl)
