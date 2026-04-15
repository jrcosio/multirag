from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock

from app.schemas.jobs import JobStatus


@dataclass
class JobRecord:
    """Estado interno de un trabajo asincrono de la API."""

    job_id: str
    job_type: str
    status: JobStatus
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    progress: int = 0
    total: int = 0
    result: dict = field(default_factory=dict)
    error: str | None = None
    document_ids: list[str] = field(default_factory=list)
    file_hash_map: dict[str, str] = field(default_factory=dict)


class JobStore:
    """Repositorio en memoria para seguimiento de jobs asincronos."""

    def __init__(self) -> None:
        self._items: dict[str, JobRecord] = {}
        self._lock = Lock()

    def create(
        self,
        job_id: str,
        job_type: str,
        document_ids: list[str] | None = None,
        file_hash_map: dict[str, str] | None = None,
    ) -> JobRecord:
        """Crea y guarda un job en estado queued."""

        with self._lock:
            job = JobRecord(
                job_id=job_id,
                job_type=job_type,
                status=JobStatus.queued,
                created_at=datetime.now(tz=UTC),
                document_ids=document_ids or [],
                file_hash_map=file_hash_map or {},
            )
            self._items[job_id] = job
            return job

    def get(self, job_id: str) -> JobRecord | None:
        """Obtiene un job por id si esta registrado."""

        with self._lock:
            return self._items.get(job_id)

    def list(self) -> list[JobRecord]:
        """Devuelve jobs ordenados por fecha de creacion descendente."""

        with self._lock:
            return sorted(self._items.values(), key=lambda item: item.created_at, reverse=True)

    def update(self, job: JobRecord) -> None:
        """Sobrescribe un job existente con su estado mas reciente."""

        with self._lock:
            self._items[job.job_id] = job

    def is_active(self, job_id: str) -> bool:
        """Indica si un job existe y sigue en ejecucion o en cola."""

        with self._lock:
            job = self._items.get(job_id)
            if not job:
                return False
            return job.status in {JobStatus.queued, JobStatus.running}
