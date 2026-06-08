"""Servidor local do wizard de instalacao (stdlib — nao exige venv)."""

from __future__ import annotations

import json
import mimetypes
import subprocess
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from install.engine import PROJECT_ROOT, get_state, is_installed, run_preflight, start_install_async
from install.paths import frontend_dir

FRONTEND_DIR = frontend_dir()
PORT = 8765


class WizardHandler(BaseHTTPRequestHandler):
    server_version = "FortiInstaller/1.0"

    def log_message(self, fmt: str, *args) -> None:
        return

    def _send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path

        if path == "/api/install/preflight":
            run_preflight()
            self._send_json(get_state().to_dict())
            return

        if path == "/api/install/status":
            self._send_json(get_state().to_dict())
            return

        if path in ("/", ""):
            path = "/index.html"

        file_path = (FRONTEND_DIR / path.lstrip("/")).resolve()
        if not str(file_path).startswith(str(FRONTEND_DIR.resolve())):
            self.send_error(403)
            return
        if not file_path.is_file():
            self.send_error(404)
            return

        content = file_path.read_bytes()
        mime, _ = mimetypes.guess_type(str(file_path))
        self.send_response(200)
        self.send_header("Content-Type", mime or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self) -> None:
        path = urlparse(self.path).path

        if path == "/api/install/run":
            body = self._read_json()
            ok = start_install_async(
                force=bool(body.get("force")),
                force_env=bool(body.get("force_env")),
                shortcut=body.get("shortcut", True),
            )
            if not ok:
                self._send_json({"error": "Instalacao ja em andamento"}, 409)
                return
            self._send_json({"status": "started"})
            return

        if path == "/api/install/launch-portal":
            venv_python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
            if not venv_python.is_file():
                self._send_json({"error": "Instale o sistema primeiro"}, 400)
                return
            subprocess.Popen(
                [str(venv_python), "-m", "forti_report.api.app"],
                cwd=PROJECT_ROOT,
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
            )
            self._send_json({"url": "http://localhost:8000/login.html"})
            return

        self.send_error(404)


def main() -> None:
    run_preflight()
    if not FRONTEND_DIR.is_dir():
        print(f"ERRO: pasta nao encontrada: {FRONTEND_DIR}")
        sys.exit(1)

    url = f"http://127.0.0.1:{PORT}/"
    print(f"Wizard de instalacao: {url}")
    if not is_installed():
        webbrowser.open(url)

    server = ThreadingHTTPServer(("127.0.0.1", PORT), WizardHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrado.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
