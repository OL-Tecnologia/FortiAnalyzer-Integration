"""Autenticação FortiAnalyzer para o portal web (sessão em memória)."""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

from forti_report.config import Settings, get_settings
from forti_report.faz.client import FortiAnalyzerClient, FortiAnalyzerError


class FazAuthError(Exception):
    """Erro de autenticação (credenciais ou sessão inválida)."""


class FazConnectionError(FazAuthError):
    """FAZ inacessível (rede, VPN, timeout)."""


class FazRateLimitError(FazAuthError):
    """Muitas tentativas de login."""


@dataclass
class FazPortalSession:
    session_id: str
    faz_user: str
    faz_password: str
    faz_rpc_session: str
    adom: str
    expires_at: float
    created_at: float = field(default_factory=time.time)

    @property
    def is_expired(self) -> bool:
        return time.time() >= self.expires_at

    def expires_at_iso(self) -> str:
        return datetime.fromtimestamp(self.expires_at, tz=timezone.utc).isoformat()


class FazSessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, FazPortalSession] = {}
        self._lock = threading.Lock()
        self._login_attempts: dict[str, list[float]] = {}

    def _prune_expired(self) -> None:
        now = time.time()
        expired = [sid for sid, rec in self._sessions.items() if rec.expires_at <= now]
        for sid in expired:
            self._sessions.pop(sid, None)

    def check_rate_limit(self, key: str, *, max_attempts: int, window_seconds: int) -> None:
        now = time.time()
        with self._lock:
            attempts = [t for t in self._login_attempts.get(key, []) if now - t < window_seconds]
            if len(attempts) >= max_attempts:
                raise FazRateLimitError("Muitas tentativas. Aguarde alguns minutos.")
            attempts.append(now)
            self._login_attempts[key] = attempts

    def create(
        self,
        *,
        faz_user: str,
        faz_password: str,
        faz_rpc_session: str,
        adom: str,
        ttl_seconds: int,
    ) -> FazPortalSession:
        session_id = secrets.token_urlsafe(32)
        record = FazPortalSession(
            session_id=session_id,
            faz_user=faz_user,
            faz_password=faz_password,
            faz_rpc_session=faz_rpc_session,
            adom=adom,
            expires_at=time.time() + ttl_seconds,
        )
        with self._lock:
            self._prune_expired()
            self._sessions[session_id] = record
        return record

    def get(self, session_id: str | None) -> FazPortalSession | None:
        if not session_id:
            return None
        with self._lock:
            self._prune_expired()
            rec = self._sessions.get(session_id)
            if rec and rec.is_expired:
                self._sessions.pop(session_id, None)
                return None
            return rec

    def invalidate(self, session_id: str | None, *, settings: Settings | None = None) -> None:
        if not session_id:
            return
        with self._lock:
            rec = self._sessions.pop(session_id, None)
        if not rec:
            return
        settings = settings or get_settings()
        try:
            with FortiAnalyzerClient(settings) as client:
                client.use_session(rec.faz_rpc_session)
                client.logout()
        except FortiAnalyzerError:
            pass


_store = FazSessionStore()


def get_session_store() -> FazSessionStore:
    return _store


def authenticate_faz(
    user: str,
    password: str,
    settings: Settings | None = None,
    *,
    rate_limit_key: str | None = None,
) -> FazPortalSession:
    """Valida credenciais no FAZ e cria sessão do portal."""
    settings = settings or get_settings()
    user = user.strip()
    if not user or not password:
        raise FazAuthError("Credenciais inválidas")

    if rate_limit_key:
        _store.check_rate_limit(rate_limit_key, max_attempts=8, window_seconds=300)

    cred_settings = settings.model_copy(update={"faz_user": user, "faz_password": password})
    try:
        with FortiAnalyzerClient(cred_settings) as client:
            faz_rpc_session = client.login()
    except httpx.TimeoutException as exc:
        raise FazConnectionError(
            "Timeout ao conectar no FortiAnalyzer. Verifique rede/VPN e FAZ_HOST."
        ) from exc
    except httpx.RequestError as exc:
        raise FazConnectionError(
            "Não foi possível conectar ao FortiAnalyzer. Verifique rede/VPN e FAZ_HOST."
        ) from exc
    except FortiAnalyzerError as exc:
        raise FazAuthError("Credenciais inválidas") from exc

    ttl_seconds = max(5, settings.faz_session_ttl_minutes * 60)
    return _store.create(
        faz_user=user,
        faz_password=password,
        faz_rpc_session=faz_rpc_session,
        adom=settings.faz_adom,
        ttl_seconds=ttl_seconds,
    )


def settings_for_session(session: FazPortalSession, base: Settings | None = None) -> Settings:
    """Settings com credenciais da sessão (para pipeline / jobs)."""
    base = base or get_settings()
    return base.model_copy(
        update={
            "faz_user": session.faz_user,
            "faz_password": session.faz_password,
        }
    )


def invalidate_session(session_id: str | None, *, settings: Settings | None = None) -> None:
    _store.invalidate(session_id, settings=settings)
