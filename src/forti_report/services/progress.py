"""Callbacks de progresso para jobs longos (API / frontend)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

PHASE_LABELS: dict[str, str] = {
    "faz": "FortiAnalyzer",
    "hierarchy": "Hierarquia",
    "pdf": "Montagem do PDF",
    "finalize": "Finalização",
}

PHASE_WEIGHTS: dict[str, int] = {
    "faz": 62,
    "hierarchy": 3,
    "pdf": 32,
    "finalize": 3,
}

PHASE_ORDER: tuple[str, ...] = ("faz", "hierarchy", "pdf", "finalize")

STEP_TO_PHASE: dict[str, str] = {
    "init": "faz",
    "faz": "faz",
    "cache": "faz",
    "metadata": "faz",
    "device": "faz",
    "antenna": "faz",  # legado
    "hierarchy": "hierarchy",
    "pdf": "pdf",
    "finalize": "finalize",
    "done": "finalize",
}


@dataclass
class ProgressUpdate:
    phase: str
    step: str
    message: str
    phase_percent: int = 0
    percent: int = 0


ProgressCallback = Callable[[ProgressUpdate], None]


@dataclass
class ProgressEvent:
    percent: int
    step: str
    message: str
    status: str = "running"
    phase: str = ""
    phase_percent: int = 0
    extra: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        phase = self.phase or STEP_TO_PHASE.get(self.step, self.step)
        data: dict[str, Any] = {
            "percent": self.percent,
            "step": self.step,
            "message": self.message,
            "status": self.status,
            "phase": phase,
            "phase_percent": clamp_percent(self.phase_percent),
            "phase_label": PHASE_LABELS.get(phase, phase),
        }
        if self.extra:
            data.update(self.extra)
        return data


def clamp_percent(value: int) -> int:
    return max(0, min(100, int(value)))


def overall_percent(phase: str, phase_percent: int) -> int:
    phase_percent = clamp_percent(phase_percent)
    total = 0
    for name in PHASE_ORDER:
        weight = PHASE_WEIGHTS.get(name, 0)
        if name == phase:
            total += int(weight * phase_percent / 100)
            break
        total += weight
    return clamp_percent(total)


class ProgressReporter:
    """Emite progresso por fase (barra independente) e percentual global."""

    def __init__(self, callback: ProgressCallback | None) -> None:
        self._callback = callback

    def emit(
        self,
        *,
        phase: str,
        step: str,
        message: str,
        phase_percent: int,
    ) -> None:
        if not self._callback:
            return
        phase_percent = clamp_percent(phase_percent)
        self._callback(
            ProgressUpdate(
                phase=phase,
                step=step,
                message=message,
                phase_percent=phase_percent,
                percent=overall_percent(phase, phase_percent),
            )
        )
