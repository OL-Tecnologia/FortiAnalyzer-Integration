"""Ponto de entrada do FortiAnalyzer Reports (.exe completo)."""

from __future__ import annotations

import shutil
import sys
import webbrowser
from threading import Timer

from forti_report.runtime_paths import bundled_config_env, project_root


def _ensure_runtime() -> None:
    root = project_root()
    for sub in ("output", "output/faz_mensal", "output/chart_cache", "output/scheduler", "output/logs"):
        (root / sub).mkdir(parents=True, exist_ok=True)

    env_file = root / ".env"
    if env_file.is_file():
        return
    template = bundled_config_env()
    if template and template.is_file():
        shutil.copy2(template, env_file)


def _open_browser() -> None:
    webbrowser.open("http://localhost:8000/login.html")


def main() -> None:
    _ensure_runtime()
    print("FortiAnalyzer Reports")
    print("Portal: http://localhost:8000/login.html")
    print("Feche esta janela para encerrar o servidor.")
    Timer(1.5, _open_browser).start()

    import uvicorn

    from forti_report.api.app import app

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
