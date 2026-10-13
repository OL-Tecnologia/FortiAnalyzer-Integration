"""Autenticação Super Admin do portal (senha em PORTAL_ADMIN_PASSWORD)."""

from __future__ import annotations

import hmac
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from forti_report.config import Settings, get_settings


class AdminAuthError(Exception):
    pass


class AdminRateLimitError(AdminAuthError):
    pass


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


def get_admin_store() -> AdminSessionStore:
    return _store


def admin_password_configured(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return bool(settings.portal_admin_password.strip())


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
    expected = (settings.portal_admin_password or "").strip()
    provided = (password or "").strip()
    if not expected:
        raise AdminAuthError(
            "Super Admin não configurado. Defina PORTAL_ADMIN_PASSWORD no arquivo .env."
        )
    if rate_limit_key:
        _store.check_rate_limit(rate_limit_key)
    if not _passwords_match(provided, expected):
        raise AdminAuthError("Senha inválida")
    ttl = max(5, settings.portal_admin_session_ttl_minutes * 60)
    return _store.create(ttl_seconds=ttl)


def invalidate_admin_session(session_id: str | None) -> None:
    _store.invalidate(session_id)
