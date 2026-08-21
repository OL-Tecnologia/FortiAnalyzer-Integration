"""Dependencies FastAPI — sessão FAZ e Super Admin."""

from __future__ import annotations

from fastapi import HTTPException, Request

from forti_report.admin.auth import AdminSession, get_admin_store
from forti_report.config import get_settings
from forti_report.faz.auth import FazPortalSession, get_session_store


def _faz_cookie_name() -> str:
    return get_settings().faz_session_cookie_name


def _admin_cookie_name() -> str:
    return get_settings().portal_admin_cookie_name


def get_portal_session(request: Request) -> FazPortalSession | None:
    session_id = request.cookies.get(_faz_cookie_name())
    return get_session_store().get(session_id)


def require_faz_session(request: Request) -> FazPortalSession:
    session = get_portal_session(request)
    if not session:
        raise HTTPException(status_code=401, detail="Autenticação necessária")
    return session


def get_admin_session(request: Request) -> AdminSession | None:
    session_id = request.cookies.get(_admin_cookie_name())
    return get_admin_store().get(session_id)


def require_admin_session(request: Request) -> AdminSession:
    session = get_admin_session(request)
    if not session:
        raise HTTPException(status_code=401, detail="Autenticação Super Admin necessária")
    return session
