"""Utilitários para ler e atualizar o arquivo .env preservando comentários."""

from __future__ import annotations

from pathlib import Path


def parse_env_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, raw = stripped.partition("=")
        values[key.strip()] = raw.strip()
    return values


def read_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    return parse_env_values(path.read_text(encoding="utf-8"))


def apply_env_updates(path: Path, updates: dict[str, str]) -> None:
    if path.is_file():
        lines = path.read_text(encoding="utf-8").splitlines()
    else:
        lines = []

    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key, _, _ = stripped.partition("=")
            key = key.strip()
            if key in updates:
                out.append(f"{key}={updates[key]}")
                seen.add(key)
                continue
        out.append(line)

    missing = [key for key in updates if key not in seen]
    if missing:
        if out and out[-1].strip():
            out.append("")
        out.append("# Configurado via scripts/configure_scheduler.py")
        for key in missing:
            out.append(f"{key}={updates[key]}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def mask_secret(value: str, *, visible: int = 2) -> str:
    if not value:
        return "(vazio)"
    if len(value) <= visible:
        return "*" * len(value)
    return value[:visible] + ("*" * (len(value) - visible))
