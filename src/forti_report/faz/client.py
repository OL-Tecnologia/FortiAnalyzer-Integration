"""Cliente JSON-RPC FortiAnalyzer (/jsonrpc)."""

from __future__ import annotations

import uuid
from typing import Any

import httpx

from forti_report.config import Settings, get_settings


class FortiAnalyzerError(Exception):
    def __init__(self, message: str, *, code: int | None = None, payload: Any = None):
        super().__init__(message)
        self.code = code
        self.payload = payload


class FortiAnalyzerClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._session: str | None = None
        self._client = httpx.Client(
            verify=self.settings.faz_verify_ssl,
            timeout=httpx.Timeout(60.0, connect=20.0),
        )

    def close(self) -> None:
        if self._session:
            try:
                self.logout()
            except FortiAnalyzerError:
                pass
        self._client.close()

    def __enter__(self) -> FortiAnalyzerClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @property
    def session(self) -> str:
        if not self._session:
            raise FortiAnalyzerError("Não autenticado. Chame login() primeiro.")
        return self._session

    def _request(
        self,
        method: str,
        params: list[dict[str, Any]],
        *,
        rpc_id: str | int | None = None,
        include_session: bool = True,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
            "id": rpc_id or str(uuid.uuid4()),
            "params": params,
        }
        if include_session and self._session:
            body["session"] = self._session

        response = self._client.post(
            self.settings.jsonrpc_url,
            json=body,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            err = data["error"]
            raise FortiAnalyzerError(
                err.get("message", "Erro JSON-RPC"),
                code=err.get("code"),
                payload=data,
            )
        return data

    def use_session(self, session_id: str) -> None:
        """Reutiliza session JSON-RPC já obtida (ex.: logout no encerramento do portal)."""
        self._session = session_id

    def login(self) -> str:
        if not self.settings.faz_user or not self.settings.faz_password:
            raise FortiAnalyzerError("FAZ_USER e FAZ_PASSWORD são obrigatórios")

        data = self._request(
            "exec",
            [
                {
                    "url": "/sys/login/user",
                    "data": {
                        "user": self.settings.faz_user,
                        "passwd": self.settings.faz_password,
                    },
                }
            ],
            include_session=False,
        )
        session = data.get("session")
        if not session:
            raise FortiAnalyzerError("Login sem session na resposta", payload=data)
        self._session = session
        return session

    def logout(self) -> None:
        if not self._session:
            return
        self._request("exec", [{"url": "/sys/logout"}])
        self._session = None

    def get(self, url: str, *, apiver: int = 3, extra: dict[str, Any] | None = None) -> Any:
        param: dict[str, Any] = {"url": url, "apiver": apiver}
        if extra:
            param.update(extra)
        data = self._request("get", [param])
        return data.get("result")

    def add(self, url: str, *, apiver: int = 3, extra: dict[str, Any] | None = None) -> Any:
        param: dict[str, Any] = {"url": url, "apiver": apiver}
        if extra:
            param.update(extra)
        data = self._request("add", [param])
        return data.get("result")
