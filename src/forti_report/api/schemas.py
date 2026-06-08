"""Schemas da API web."""

from pydantic import BaseModel, Field


class FazLoginRequest(BaseModel):
    user: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=1, max_length=256)


class AuthMeResponse(BaseModel):
    authenticated: bool
    adom: str
    user: str | None = None
    expires_at: str | None = None


class GenerateMensalRequest(BaseModel):
    days: int = Field(60, ge=1, le=365)
    download: bool = True
    force_download: bool = False
    charts: bool = True


class JobCreatedResponse(BaseModel):
    job_id: str
    adom: str
    stream_url: str
    download_url: str


class ClientInfoResponse(BaseModel):
    adom: str
    display_name: str
    report_schedule: str
