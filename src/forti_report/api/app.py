"""FastAPI — geração MENSAL CRUZ_AZUL com progresso, download e login FAZ."""

from __future__ import annotations

import json
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from forti_report.api.deps import get_portal_session, require_faz_session
from forti_report.api.schemas import (
    AuthMeResponse,
    AutomationSettingsResponse,
    AutomationSettingsUpdate,
    ClientInfoResponse,
    FazLoginRequest,
    GenerateMensalRequest,
    JobCreatedResponse,
    SchedulerStatusResponse,
)
from forti_report.config import get_settings
from forti_report.runtime_paths import frontend_dir
from forti_report.faz.auth import (
    FazAuthError,
    FazConnectionError,
    FazPortalSession,
    FazRateLimitError,
    authenticate_faz,
    invalidate_session,
    settings_for_session,
)
from forti_report.services.automation_settings import (
    get_automation_settings,
    update_automation_settings,
)
from forti_report.services.job_store import JobRecord
from forti_report.services.mensal_job import get_job_store, start_mensal_job
from forti_report.services.mensal_scheduler import (
    get_scheduler_status,
    start_background_scheduler,
    stop_background_scheduler,
)

FRONTEND_DIR = frontend_dir()


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    stop_event = start_background_scheduler()
    yield
    stop_background_scheduler(stop_event)


app = FastAPI(
    title="FortiAnalyzer Reports API",
    description="Geração do relatório MENSAL unificado (CRUZ_AZUL)",
    version="1.2.0",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _set_session_cookie(response: Response, session: FazPortalSession) -> None:
    settings = get_settings()
    max_age = max(0, int(session.expires_at - time.time()))
    response.set_cookie(
        key=settings.faz_session_cookie_name,
        value=session.session_id,
        max_age=max_age,
        httponly=True,
        secure=settings.faz_session_cookie_secure,
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.faz_session_cookie_name,
        path="/",
        httponly=True,
        secure=settings.faz_session_cookie_secure,
        samesite="lax",
    )


def _require_job_access(record: JobRecord, session: FazPortalSession) -> None:
    if record.portal_session_id and record.portal_session_id != session.session_id:
        raise HTTPException(403, "Acesso negado a este job")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/auth/faz/login")
def faz_login(body: FazLoginRequest, request: Request, response: Response) -> AuthMeResponse:
    settings = get_settings()
    try:
        session = authenticate_faz(
            body.user,
            body.password,
            settings,
            rate_limit_key=_client_ip(request),
        )
    except FazRateLimitError as exc:
        raise HTTPException(429, str(exc)) from exc
    except FazConnectionError as exc:
        raise HTTPException(503, str(exc)) from exc
    except FazAuthError as exc:
        raise HTTPException(401, str(exc)) from exc

    _set_session_cookie(response, session)
    return AuthMeResponse(
        authenticated=True,
        adom=session.adom,
        user=session.faz_user,
        expires_at=session.expires_at_iso(),
    )


@app.post("/api/auth/logout")
def faz_logout(
    request: Request,
    response: Response,
    session: FazPortalSession | None = Depends(get_portal_session),
) -> dict[str, str]:
    if session:
        invalidate_session(session.session_id)
    _clear_session_cookie(response)
    return {"status": "ok"}


@app.get("/api/auth/me", response_model=AuthMeResponse)
def faz_me(session: FazPortalSession | None = Depends(get_portal_session)) -> AuthMeResponse:
    settings = get_settings()
    if not session:
        return AuthMeResponse(authenticated=False, adom=settings.faz_adom)
    return AuthMeResponse(
        authenticated=True,
        adom=session.adom,
        user=session.faz_user,
        expires_at=session.expires_at_iso(),
    )


@app.get("/api/client", response_model=ClientInfoResponse)
def client_info() -> ClientInfoResponse:
    settings = get_settings()
    return ClientInfoResponse(
        adom=settings.faz_adom,
        display_name="Cruz Azul",
        report_schedule=settings.faz_report_schedule or "MENSAL- RELATÓRIO GERAL",
    )


@app.get("/api/scheduler/status", response_model=SchedulerStatusResponse)
def scheduler_status(
    session: FazPortalSession = Depends(require_faz_session),
) -> SchedulerStatusResponse:
    settings = get_settings()
    status = get_scheduler_status(settings)
    return SchedulerStatusResponse(
        enabled=status.enabled,
        period=status.period,
        next_run_at=status.next_run_at,
        last_success_period=status.last_success_period,
        last_success_at=status.last_success_at,
        last_status=status.last_status,
        last_error=status.last_error,
        attempts=status.attempts,
        running=status.running,
        schedule_day=settings.mensal_schedule_day,
        schedule_time=f"{settings.mensal_schedule_hour:02d}:{settings.mensal_schedule_minute:02d}",
        timezone=settings.mensal_schedule_timezone,
    )


@app.get("/api/settings/automation", response_model=AutomationSettingsResponse)
def get_automation_config(
    session: FazPortalSession = Depends(require_faz_session),
) -> AutomationSettingsResponse:
    view = get_automation_settings()
    return AutomationSettingsResponse(**view.__dict__)


@app.put("/api/settings/automation", response_model=AutomationSettingsResponse)
def put_automation_config(
    body: AutomationSettingsUpdate,
    session: FazPortalSession = Depends(require_faz_session),
) -> AutomationSettingsResponse:
    try:
        view = update_automation_settings(body.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except OSError as exc:
        raise HTTPException(500, f"Não foi possível gravar .env: {exc}") from exc
    return AutomationSettingsResponse(**view.__dict__)


@app.post("/api/reports/mensal/generate", response_model=JobCreatedResponse)
def generate_mensal(
    body: GenerateMensalRequest,
    session: FazPortalSession = Depends(require_faz_session),
) -> JobCreatedResponse:
    settings = settings_for_session(session)
    record = start_mensal_job(
        days=body.days,
        download=body.download,
        force_download=body.force_download,
        charts=body.charts,
        settings=settings,
        portal_session_id=session.session_id,
    )
    base = f"/api/reports/mensal/jobs/{record.job_id}"
    return JobCreatedResponse(
        job_id=record.job_id,
        adom=record.adom,
        stream_url=f"{base}/stream",
        download_url=f"{base}/download",
    )


def _sse_stream(record: JobRecord):
    sent = 0
    while True:
        if sent < len(record.events):
            event = record.events[sent]
            sent += 1
            yield f"data: {json.dumps(event.to_dict(), ensure_ascii=False)}\n\n"
            if event.status in ("completed", "failed"):
                break
            continue

        if record.status in ("completed", "failed"):
            break

        fresh = record.wait_event(timeout=25.0)
        if fresh is None:
            yield ": keepalive\n\n"
            continue

        if sent < len(record.events):
            continue

        payload = fresh.to_dict()
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        if fresh.status in ("completed", "failed"):
            break

    yield 'data: {"status":"closed"}\n\n'


@app.get("/api/reports/mensal/jobs/{job_id}/stream")
def stream_job(
    job_id: str,
    session: FazPortalSession = Depends(require_faz_session),
) -> StreamingResponse:
    record = get_job_store().get(job_id)
    if not record:
        raise HTTPException(404, "Job não encontrado")
    _require_job_access(record, session)
    return StreamingResponse(
        _sse_stream(record),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/reports/mensal/jobs/{job_id}")
def job_status(
    job_id: str,
    session: FazPortalSession = Depends(require_faz_session),
) -> dict:
    record = get_job_store().get(job_id)
    if not record:
        raise HTTPException(404, "Job não encontrado")
    _require_job_access(record, session)
    last = record.events[-1].to_dict() if record.events else {}
    return {
        "job_id": record.job_id,
        "status": record.status,
        "adom": record.adom,
        "error": record.error,
        "pdf_filename": record.pdf_path.name if record.pdf_path else None,
        "last_event": last,
    }


@app.get("/api/reports/mensal/jobs/{job_id}/download")
def download_job(
    job_id: str,
    session: FazPortalSession = Depends(require_faz_session),
) -> FileResponse:
    record = get_job_store().get(job_id)
    if not record:
        raise HTTPException(404, "Job não encontrado")
    _require_job_access(record, session)
    if record.status != "completed" or not record.pdf_path or not record.pdf_path.is_file():
        raise HTTPException(409, "PDF ainda não está disponível")
    return FileResponse(
        path=record.pdf_path,
        filename=record.pdf_path.name,
        media_type="application/pdf",
    )


def _register_frontend(app: FastAPI) -> None:
    """Rotas explícitas do frontend — evita StaticFiles em / capturar POST /api/*."""
    if not FRONTEND_DIR.is_dir():
        return

    media_types = {
        ".html": "text/html; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
    }

    def _file(name: str) -> FileResponse:
        path = FRONTEND_DIR / name
        if not path.is_file():
            raise HTTPException(404, "Arquivo não encontrado")
        suffix = path.suffix.lower()
        return FileResponse(path, media_type=media_types.get(suffix, "application/octet-stream"))

    @app.get("/", include_in_schema=False)
    def serve_index() -> FileResponse:
        return _file("index.html")

    @app.get("/login.html", include_in_schema=False)
    def serve_login() -> FileResponse:
        return _file("login.html")

    @app.get("/app.js", include_in_schema=False)
    def serve_app_js() -> FileResponse:
        return _file("app.js")

    @app.get("/login.js", include_in_schema=False)
    def serve_login_js() -> FileResponse:
        return _file("login.js")

    @app.get("/styles.css", include_in_schema=False)
    def serve_styles() -> FileResponse:
        return _file("styles.css")

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> Response:
        return Response(status_code=204)


_register_frontend(app)


def main() -> None:
    import uvicorn

    uvicorn.run(
        "forti_report.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()
