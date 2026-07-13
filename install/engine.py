"""Motor de instalacao — usado pelo wizard web e scripts."""

from __future__ import annotations

import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path

from install.paths import config_env_path, project_root, venv_python

PROJECT_ROOT = project_root()
VENV_PYTHON = venv_python()


@dataclass
class InstallState:
    status: str = "idle"  # idle | running | completed | failed
    step: str = ""
    message: str = ""
    percent: int = 0
    logs: list[str] = field(default_factory=list)
    error: str | None = None
    python_version: str | None = None
    installed: bool = False
    adom: str | None = None
    project_ok: bool = False
    project_path: str | None = None
    project_error: str | None = None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "step": self.step,
            "message": self.message,
            "percent": self.percent,
            "logs": self.logs[-80:],
            "error": self.error,
            "python_version": self.python_version,
            "installed": self.installed,
            "adom": self.adom,
            "project_ok": self.project_ok,
            "project_path": self.project_path,
            "project_error": self.project_error,
        }


_state = InstallState()
_lock = threading.Lock()


def get_state() -> InstallState:
    with _lock:
        return _state


def _log(msg: str) -> None:
    with _lock:
        _state.logs.append(msg)


def _set(*, percent: int | None = None, step: str | None = None, message: str | None = None) -> None:
    with _lock:
        if percent is not None:
            _state.percent = max(0, min(100, int(percent)))
        if step is not None:
            _state.step = step
        if message is not None:
            _state.message = message
            _state.logs.append(message)


def find_system_python() -> tuple[list[str], str] | None:
    """Retorna ([exe, ...args], version) ou None."""
    candidates: list[list[str]] = [
        ["py", "-3.13"],
        ["py", "-3.12"],
        ["py", "-3.11"],
        ["py", "-3"],
        ["python"],
    ]
    for cmd in candidates:
        exe = shutil.which(cmd[0])
        if not exe:
            continue
        full = [exe, *cmd[1:]]
        try:
            result = subprocess.run(
                [*full, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            ver = (result.stdout or "").strip()
            if result.returncode == 0 and ver.startswith("3."):
                minor = int(ver.split(".")[1])
                if minor >= 11:
                    return full, ver
        except (OSError, ValueError, subprocess.TimeoutExpired):
            continue
    return None


def is_installed() -> bool:
    return VENV_PYTHON.is_file()


def validate_project() -> tuple[bool, str | None]:
    """Verifica se a pasta contem o projeto completo (nao apenas o .exe)."""
    missing: list[str] = []
    if not (PROJECT_ROOT / "pyproject.toml").is_file():
        missing.append("pyproject.toml")
    if not (PROJECT_ROOT / "src" / "forti_report").is_dir():
        missing.append("src/forti_report/")
    if missing:
        return False, (
            f"Pasta incompleta: {PROJECT_ROOT}. "
            f"Faltando: {', '.join(missing)}. "
            "Execute install.bat na raiz do projeto (codigo-fonte completo)."
        )
    return True, None


def read_adom() -> str | None:
    env_file = PROJECT_ROOT / ".env"
    if not env_file.is_file():
        return None
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("FAZ_ADOM="):
            return line.split("=", 1)[1].strip() or None
    return None


def run_preflight() -> InstallState:
    project_ok, project_error = validate_project()
    with _lock:
        _state.installed = is_installed()
        _state.adom = read_adom()
        _state.project_ok = project_ok
        _state.project_path = str(PROJECT_ROOT)
        _state.project_error = project_error
        found = find_system_python()
        if found:
            _state.python_version = found[1]
        else:
            _state.python_version = None
    return get_state()


def _run_cmd(cmd: list[str], *, cwd: Path | None = None) -> None:
    result = subprocess.run(
        cmd,
        cwd=cwd or PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        msg = f"Comando falhou: {' '.join(cmd)} (exit {result.returncode})"
        if detail:
            last_line = detail.splitlines()[-1].strip()
            if last_line:
                msg = f"{msg}\n{last_line}"
        raise RuntimeError(msg)


def create_desktop_shortcut() -> None:
    bat = PROJECT_ROOT / "FortiAnalyzer Reports.bat"
    ps = f"""
$desktop = [Environment]::GetFolderPath('Desktop')
$lnk = Join-Path $desktop 'FortiAnalyzer Reports.lnk'
$WshShell = New-Object -ComObject WScript.Shell
$sc = $WshShell.CreateShortcut($lnk)
$sc.TargetPath = '{bat}'
$sc.WorkingDirectory = '{PROJECT_ROOT}'
$sc.Description = 'Relatorio MENSAL FortiAnalyzer - Cruz Azul'
$sc.Save()
"""
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
        check=True,
        cwd=PROJECT_ROOT,
    )


def run_install(*, force: bool = False, force_env: bool = False, shortcut: bool = True) -> None:
    global _state
    with _lock:
        if _state.status == "running":
            return
        _state = InstallState(status="running", percent=0)
        _state.logs.clear()

    try:
        project_ok, project_error = validate_project()
        if not project_ok:
            raise RuntimeError(project_error or "Pasta do projeto incompleta.")

        _set(percent=5, step="python", message="Verificando Python 3.11+...")
        found = find_system_python()
        if not found:
            raise RuntimeError(
                "Python 3.11+ não encontrado. Instale em python.org com 'Add to PATH'."
            )
        py_cmd, py_ver = found
        with _lock:
            _state.python_version = py_ver
        _log(f"Python {py_ver} OK")

        venv_dir = PROJECT_ROOT / ".venv"
        _set(percent=18, step="venv", message="Criando ambiente virtual...")
        if force and venv_dir.is_dir():
            shutil.rmtree(venv_dir, ignore_errors=True)
        if not VENV_PYTHON.is_file():
            _run_cmd([*py_cmd, "-m", "venv", str(venv_dir)])
            _log("Ambiente virtual criado")
        else:
            _log("Ambiente virtual já existe")

        _set(percent=38, step="deps", message="Instalando dependências...")
        _run_cmd([str(VENV_PYTHON), "-m", "pip", "install", "--upgrade", "pip", "wheel", "setuptools", "-q"])
        _run_cmd([str(VENV_PYTHON), "-m", "pip", "install", "-e", ".", "-q"])
        _log("Pacote forti-analyzer-reports instalado")

        _set(percent=55, step="folders", message="Preparando pastas de saída...")
        for sub in ("output", "output/faz_mensal", "output/chart_cache"):
            (PROJECT_ROOT / sub).mkdir(parents=True, exist_ok=True)
        _log("Pastas output/ prontas")

        _set(percent=68, step="config", message="Aplicando configuração Cruz Azul...")
        config_env = config_env_path()
        env_file = PROJECT_ROOT / ".env"
        if config_env.is_file() and (force_env or not env_file.is_file()):
            shutil.copy2(config_env, env_file)
            _log("Configuração aplicada (install/config.env → .env)")
        else:
            _log(".env mantido")

        _set(percent=82, step="verify", message="Verificando instalação...")
        result = subprocess.run(
            [
                str(VENV_PYTHON),
                "-c",
                "import forti_report; from forti_report.config import get_settings; print(get_settings().faz_adom)",
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            check=False,
        )
        adom = (result.stdout or "").strip() if result.returncode == 0 else None
        if not adom:
            raise RuntimeError((result.stderr or "Verificação falhou").strip())
        _log(f"Sistema OK — ADOM {adom}")

        if shortcut:
            _set(percent=92, step="shortcut", message="Criando atalho na área de trabalho...")
            create_desktop_shortcut()
            _log("Atalho 'FortiAnalyzer Reports' criado")

        with _lock:
            _state.status = "completed"
            _state.percent = 100
            _state.step = "done"
            _state.message = "Instalação concluída com sucesso."
            _state.installed = True
            _state.adom = adom
            _state.logs.append("Pronto para usar.")
    except Exception as exc:
        with _lock:
            _state.status = "failed"
            _state.error = str(exc)
            _state.message = str(exc)
            _state.logs.append(f"ERRO: {exc}")


def start_install_async(**kwargs) -> bool:
    state = get_state()
    if state.status == "running":
        return False

    def _worker() -> None:
        run_install(**kwargs)

    threading.Thread(target=_worker, daemon=True).start()
    return True
