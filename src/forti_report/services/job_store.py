"""Estado em memória dos jobs de geração (frontend V1)."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from queue import Empty, Queue

from forti_report.services.progress import ProgressEvent


@dataclass
class JobRecord:
    job_id: str
    adom: str
    portal_session_id: str = ""
    status: str = "pending"
    events: list[ProgressEvent] = field(default_factory=list)
    pdf_path: Path | None = None
    error: str | None = None
    _queue: Queue = field(default_factory=Queue, repr=False)

    def push(self, event: ProgressEvent) -> None:
        self.events.append(event)
        self.status = event.status
        self._queue.put(event)

    def wait_event(self, timeout: float = 30.0) -> ProgressEvent | None:
        try:
            return self._queue.get(timeout=timeout)
        except Empty:
            return None


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = threading.Lock()

    def create(self, *, adom: str, portal_session_id: str = "") -> JobRecord:
        job_id = uuid.uuid4().hex
        record = JobRecord(job_id=job_id, adom=adom, portal_session_id=portal_session_id)
        with self._lock:
            self._jobs[job_id] = record
        return record

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)
