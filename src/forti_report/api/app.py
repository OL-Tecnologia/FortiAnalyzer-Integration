"""FastAPI — portal multi-tenant MENSAL (FAZ login + Super Admin)."""

from __future__ import annotations

import json
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse

from forti_report.admin import (
    AdminAuthError,
    AdminRateLimitError,
    AdminSession,
    admin_password_configured,
    authenticate_admin,
    invalidate_admin_session,
)
from forti_report.api.deps import (
    get_admin_session,
    get_portal_session,
    require_admin_session,
    require_faz_session,
)
from forti_report.api.schemas import (
    AdminLoginRequest,
    AdminMeResponse,
    AuthMeResponse,
    AutomationSettingsResponse,
    AutomationSettingsUpdate,
    ClientConnectionTestRequest,
    ClientConnectionTestResponse,
    ClientInfoResponse,
    ClientPublicResponse,
    ClientUpsertRequest,
    FazLoginRequest,
    GenerateMensalRequest,
    JobCreatedResponse,
    SchedulerStatusResponse,
)
from forti_report.clients import (
    ClientConfig,
    ClientStoreError,
    automation_password_set,
    delete_client,
    ensure_default_client_file,
    get_client,
    list_clients,
    list_clients_or_legacy,
    save_client,
    settings_from_client,
)
from forti_report.clients.assets import (
    ASSET_KINDS,
    ClientAssetError,
    resolve_client_asset_file,
    save_client_asset,
)
from forti_report.clients.connectivity import test_faz_connection
from forti_report.config import get_settings
from forti_report.pdf.branding_preview import (
    branding_preview_filename,
    build_branding_preview_pdf,
)
from forti_report.faz.auth import (
    FazAuthError,
    FazConnectionError,
    FazPortalSession,
    FazRateLimitError,
    authenticate_faz,
    invalidate_session,
    settings_for_session,
)
from forti_report.runtime_paths import frontend_dir
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
    ensure_default_client_file()
    stop_event = start_background_scheduler()
    yield
    stop_background_scheduler(stop_event)


app = FastAPI(
    title="FortiAnalyzer Reports API",
    description="Portal multi-tenant — relatório MENSAL unificado por cliente FAZ",
    version="2.0.0",
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


def _set_admin_cookie(response: Response, session: AdminSession) -> None:
    settings = get_settings()
    max_age = max(0, int(session.expires_at - time.time()))
    response.set_cookie(
        key=settings.portal_admin_cookie_name,
        value=session.session_id,
        max_age=max_age,
        httponly=True,
        secure=settings.faz_session_cookie_secure,
        samesite="lax",
        path="/",
    )


def _clear_admin_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.portal_admin_cookie_name,
        path="/",
        httponly=True,
        secure=settings.faz_session_cookie_secure,
        samesite="lax",
    )


def _require_job_access(record: JobRecord, session: FazPortalSession) -> None:
    if record.portal_session_id and record.portal_session_id != session.session_id:
        raise HTTPException(403, "Acesso negado a este job")


def _resolve_login_client(client_slug: str | None) -> ClientConfig:
    clients = list_clients_or_legacy()
    if not clients:
        raise HTTPException(503, "Nenhum cliente configurado. Acesse a Administração.")
    slug = (client_slug or "").strip().lower()
    if not slug:
        if len(clients) == 1:
            return clients[0]
        raise HTTPException(400, "Selecione o cliente (client_slug).")
    client = get_client(slug)
    if not client:
        raise HTTPException(404, f"Cliente não encontrado: {slug}")
    return client


def _merge_client_payload(existing: ClientConfig | None, body: ClientUpsertRequest) -> ClientConfig:
    data: dict[str, Any] = existing.model_dump() if existing else {}
    payload = body.model_dump(exclude_unset=True)
    password = payload.pop("automation_faz_password", None)
    payload.pop("require_connection_ok", None)
    for key in ("faz", "automation", "hierarchy", "pdf", "output", "schedule", "email"):
        if key in payload and isinstance(payload[key], dict):
            merged = dict(data.get(key) or {})
            merged.update({k: v for k, v in payload[key].items() if v is not None})
            data[key] = merged
            payload.pop(key, None)
    data.update({k: v for k, v in payload.items() if v is not None})
    if not data.get("slug") and body.slug:
        data["slug"] = body.slug
    if not data.get("display_name"):
        data["display_name"] = data.get("slug") or "Cliente"
    if "output" not in data or not (data.get("output") or {}).get("subdir"):
        data.setdefault("output", {})["subdir"] = data["slug"]
    client = ClientConfig.model_validate(data)
    return client


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/auth/faz/login")
def faz_login(body: FazLoginRequest, request: Request, response: Response) -> AuthMeResponse:
    client = _resolve_login_client(body.client_slug)
    tenant_settings = settings_from_client(client)
    try:
        session = authenticate_faz(
            body.user,
            body.password,
            tenant_settings,
            rate_limit_key=_client_ip(request),
            client_slug=client.slug,
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
        client_slug=session.client_slug,
        display_name=client.display_name,
    )


@app.post("/api/auth/logout")
def faz_logout(
    request: Request,
    response: Response,
    session: FazPortalSession | None = Depends(get_portal_session),
) -> dict[str, str]:
    if session:
        invalidate_session(session.session_id, settings=settings_for_session(session))
    _clear_session_cookie(response)
    return {"status": "ok"}


@app.get("/api/auth/me", response_model=AuthMeResponse)
def faz_me(session: FazPortalSession | None = Depends(get_portal_session)) -> AuthMeResponse:
    if not session:
        clients = list_clients_or_legacy()
        adom = clients[0].faz.adom if clients else get_settings().faz_adom
        return AuthMeResponse(authenticated=False, adom=adom)
    display = None
    if session.client_slug:
        client = get_client(session.client_slug, include_disabled=True)
        display = client.display_name if client else None
    return AuthMeResponse(
        authenticated=True,
        adom=session.adom,
        user=session.faz_user,
        expires_at=session.expires_at_iso(),
        client_slug=session.client_slug or None,
        display_name=display,
    )


@app.get("/api/clients", response_model=list[ClientPublicResponse])
def list_public_clients() -> list[ClientPublicResponse]:
    return [
        ClientPublicResponse(**c.public_dict())
        for c in list_clients_or_legacy()
    ]


@app.get("/api/client", response_model=ClientInfoResponse)
def client_info(session: FazPortalSession | None = Depends(get_portal_session)) -> ClientInfoResponse:
    if session and session.client_slug:
        client = get_client(session.client_slug, include_disabled=True)
        if client:
            return ClientInfoResponse(
                adom=client.faz.adom,
                display_name=client.display_name,
                report_schedule=client.faz.report_schedule_mensal or "MENSAL-RELATÓRIO DE ENDPOINT",
            )
    clients = list_clients_or_legacy()
    if clients:
        c = clients[0]
        return ClientInfoResponse(
            adom=c.faz.adom,
            display_name=c.display_name,
            report_schedule=c.faz.report_schedule_mensal or "MENSAL-RELATÓRIO DE ENDPOINT",
        )
    settings = get_settings()
    return ClientInfoResponse(
        adom=settings.faz_adom,
        display_name=settings.faz_adom,
        report_schedule=settings.faz_report_schedule or "MENSAL-RELATÓRIO DE ENDPOINT",
    )


@app.post("/api/admin/login", response_model=AdminMeResponse)
def admin_login(body: AdminLoginRequest, request: Request, response: Response) -> AdminMeResponse:
    try:
        session = authenticate_admin(body.password, rate_limit_key=_client_ip(request))
    except AdminRateLimitError as exc:
        raise HTTPException(429, str(exc)) from exc
    except AdminAuthError as exc:
        raise HTTPException(401, str(exc)) from exc
    _set_admin_cookie(response, session)
    return AdminMeResponse(
        authenticated=True,
        configured=True,
        expires_at=session.expires_at_iso(),
    )


@app.post("/api/admin/logout")
def admin_logout(
    response: Response,
    session: AdminSession | None = Depends(get_admin_session),
) -> dict[str, str]:
    if session:
        invalidate_admin_session(session.session_id)
    _clear_admin_cookie(response)
    return {"status": "ok"}


@app.get("/api/admin/me", response_model=AdminMeResponse)
def admin_me(session: AdminSession | None = Depends(get_admin_session)) -> AdminMeResponse:
    configured = admin_password_configured()
    if not session:
        return AdminMeResponse(authenticated=False, configured=configured)
    return AdminMeResponse(
        authenticated=True,
        configured=configured,
        expires_at=session.expires_at_iso(),
    )


@app.get("/api/admin/clients")
def admin_list_clients(_: AdminSession = Depends(require_admin_session)) -> list[dict[str, Any]]:
    items = list_clients(include_disabled=True)
    if not items:
        items = list_clients_or_legacy()
    return [
        c.admin_dict(automation_password_set=automation_password_set(c))
        for c in items
    ]


@app.get("/api/admin/clients/{slug}")
def admin_get_client(slug: str, _: AdminSession = Depends(require_admin_session)) -> dict[str, Any]:
    client = get_client(slug, include_disabled=True)
    if not client:
        raise HTTPException(404, "Cliente não encontrado")
    return client.admin_dict(automation_password_set=automation_password_set(client))


def _admin_save_client(
    body: ClientUpsertRequest,
    *,
    slug: str | None = None,
    existing: ClientConfig | None = None,
    allow_create: bool = True,
) -> dict[str, Any]:
    """Cria ou atualiza tenant (com teste de conexão opcional)."""
    target_slug = (slug or body.slug or "").strip().lower()
    if not target_slug:
        raise HTTPException(400, "slug é obrigatório")
    if body.slug and body.slug.strip().lower() != target_slug:
        raise HTTPException(400, "slug do path não pode ser alterado neste endpoint")

    if existing is None:
        existing = get_client(target_slug, include_disabled=True)
    if existing is None and not allow_create:
        raise HTTPException(404, "Cliente não encontrado")

    try:
        client = _merge_client_payload(existing, body)
        client.slug = target_slug
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc

    if body.require_connection_ok:
        auto_user = None
        if body.automation and isinstance(body.automation, dict):
            auto_user = body.automation.get("faz_user")
        result = test_faz_connection(
            client,
            faz_user=auto_user or client.automation.faz_user,
            faz_password=body.automation_faz_password,
        )
        if not result.get("ok"):
            raise HTTPException(400, result.get("detail") or "Teste de conexão falhou")

    try:
        saved = save_client(client, automation_password=body.automation_faz_password)
    except ClientStoreError as exc:
        raise HTTPException(400, str(exc)) from exc
    except OSError as exc:
        raise HTTPException(500, f"Não foi possível gravar cliente: {exc}") from exc
    return saved.admin_dict(automation_password_set=automation_password_set(saved))


@app.post("/api/admin/clients")
def admin_create_client(
    body: ClientUpsertRequest,
    _: AdminSession = Depends(require_admin_session),
) -> dict[str, Any]:
    if not body.slug:
        raise HTTPException(400, "slug é obrigatório")
    if get_client(body.slug, include_disabled=True):
        raise HTTPException(409, f"Cliente já existe: {body.slug}")
    return _admin_save_client(body, slug=body.slug, existing=None, allow_create=True)


@app.put("/api/admin/clients/{slug}")
def admin_update_client(
    slug: str,
    body: ClientUpsertRequest,
    _: AdminSession = Depends(require_admin_session),
) -> dict[str, Any]:
    # Upsert: se o YAML não existe (lista limpa / 1º cadastro), cria em vez de 404
    return _admin_save_client(body, slug=slug, allow_create=True)


@app.post("/api/admin/clients/{slug}/test-connection", response_model=ClientConnectionTestResponse)
def admin_test_client_connection(
    slug: str,
    body: ClientConnectionTestRequest,
    _: AdminSession = Depends(require_admin_session),
) -> ClientConnectionTestResponse:
    """Testa FAZ com draft do formulário (mesmo antes do YAML existir)."""
    existing = get_client(slug, include_disabled=True)
    draft = body.draft if isinstance(body.draft, dict) else None
    if draft is not None:
        data = existing.model_dump() if existing else {"slug": slug, "display_name": slug}
        for key, value in draft.items():
            if key in {"automation_faz_password", "require_connection_ok"}:
                continue
            if isinstance(value, dict) and isinstance(data.get(key), dict):
                merged = dict(data.get(key) or {})
                merged.update({k: v for k, v in value.items() if v is not None})
                data[key] = merged
            elif value is not None:
                data[key] = value
        data["slug"] = slug
        if not data.get("display_name"):
            data["display_name"] = slug
        try:
            client = ClientConfig.model_validate(data)
        except Exception as exc:
            raise HTTPException(400, str(exc)) from exc
    else:
        if not existing:
            raise HTTPException(
                404,
                "Cliente não encontrado. Preencha o formulário e teste de novo, ou salve o cliente antes.",
            )
        client = existing
    result = test_faz_connection(client, faz_user=body.faz_user, faz_password=body.faz_password)
    return ClientConnectionTestResponse(**result)


@app.delete("/api/admin/clients/{slug}")
def admin_delete_client(slug: str, _: AdminSession = Depends(require_admin_session)) -> dict[str, str]:
    if not delete_client(slug):
        raise HTTPException(404, "Cliente não encontrado")
    return {"status": "ok"}


@app.post("/api/admin/clients/{slug}/assets")
async def admin_upload_client_asset(
    slug: str,
    kind: str = Form(...),
    file: UploadFile = File(...),
    _: AdminSession = Depends(require_admin_session),
) -> dict[str, Any]:
    """Upload de logo/capa/rodapé → assets/clients/{slug}/ e atualiza o YAML se existir."""
    content = await file.read()
    try:
        result = save_client_asset(
            slug,
            kind,
            filename=file.filename or "",
            content=content,
        )
    except ClientAssetError as exc:
        raise HTTPException(400, str(exc)) from exc
    except OSError as exc:
        raise HTTPException(500, f"Não foi possível gravar asset: {exc}") from exc
    return result


@app.get("/api/admin/clients/{slug}/assets/{kind}")
def admin_get_client_asset(
    slug: str,
    kind: str,
    _: AdminSession = Depends(require_admin_session),
) -> FileResponse:
    if kind not in ASSET_KINDS:
        raise HTTPException(400, f"kind inválido. Use: {', '.join(ASSET_KINDS)}")
    client = get_client(slug, include_disabled=True)
    if not client:
        # fallback: arquivo já enviado antes do YAML
        from forti_report.clients.assets import client_assets_dir

        directory = client_assets_dir(slug)
        matches = list(directory.glob(f"{ASSET_KINDS[kind]}.*"))
        if not matches:
            raise HTTPException(404, "Asset não encontrado")
        path = matches[0]
    else:
        path = resolve_client_asset_file(client, kind)
        if not path:
            raise HTTPException(404, "Asset não encontrado")
    return FileResponse(path)


@app.get("/api/admin/clients/{slug}/branding-preview")
def admin_branding_preview_saved(
    slug: str,
    _: AdminSession = Depends(require_admin_session),
) -> Response:
    """Download PDF de amostra: capa + página interna (rodapé do corpo)."""
    client = get_client(slug, include_disabled=True)
    if not client:
        raise HTTPException(404, "Cliente não encontrado")
    settings = settings_from_client(client)
    pdf = build_branding_preview_pdf(
        settings,
        adom=client.faz.adom,
        display_name=client.display_name,
    )
    filename = branding_preview_filename(client.slug)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/admin/branding-preview")
def admin_branding_preview_draft(
    body: ClientUpsertRequest,
    _: AdminSession = Depends(require_admin_session),
) -> Response:
    """Prévia com dados do formulário (mesmo sem salvar o tenant)."""
    slug = (body.slug or "").strip().lower()
    if not slug:
        raise HTTPException(400, "slug é obrigatório para a prévia")
    existing = get_client(slug, include_disabled=True)
    try:
        client = _merge_client_payload(existing, body)
        client.slug = slug
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
    # Faixas OL sempre fixas
    pdf_cfg = client.pdf.model_copy(
        update={
            "cover_header": "assets/img/cabecalho_capa.png",
            "cover_footer": "assets/img/rodape_capa.png",
        }
    )
    client = client.model_copy(update={"pdf": pdf_cfg})
    settings = settings_from_client(client)
    pdf = build_branding_preview_pdf(
        settings,
        adom=client.faz.adom,
        display_name=client.display_name,
    )
    filename = branding_preview_filename(client.slug)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/admin/asset-preview")
def admin_asset_preview(
    path: str,
    _: AdminSession = Depends(require_admin_session),
) -> FileResponse:
    """Serve imagem sob assets/ para a prévia da capa (somente Super Admin)."""
    from forti_report.runtime_paths import resolve_asset_file

    rel = (path or "").strip().replace("\\", "/").lstrip("/")
    if not rel or ".." in rel.split("/"):
        raise HTTPException(400, "Caminho inválido")
    if not rel.startswith("assets/"):
        raise HTTPException(400, "Somente arquivos em assets/ são permitidos")
    full = resolve_asset_file(rel)
    if full is None:
        raise HTTPException(404, "Arquivo não encontrado")
    return FileResponse(full)


@app.get("/api/scheduler/status", response_model=SchedulerStatusResponse)
def scheduler_status(
    session: FazPortalSession = Depends(require_faz_session),
) -> SchedulerStatusResponse:
    settings = settings_for_session(session)
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

    @app.get("/admin.html", include_in_schema=False)
    def serve_admin() -> FileResponse:
        return _file("admin.html")

    @app.get("/app.js", include_in_schema=False)
    def serve_app_js() -> FileResponse:
        return _file("app.js")

    @app.get("/login.js", include_in_schema=False)
    def serve_login_js() -> FileResponse:
        return _file("login.js")

    @app.get("/admin.js", include_in_schema=False)
    def serve_admin_js() -> FileResponse:
        return _file("admin.js")

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
