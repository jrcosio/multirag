from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Estados posibles del ciclo de vida de un job asincrono."""

    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class CreateIndexJobRequest(BaseModel):
    """Solicitud para crear un job de indexado asincrono."""

    document_ids: list[str] | None = Field(
        default=None,
        description="Lista de documentos concretos a indexar. Si se omite, procesa todos.",
    )
    all_pending: bool = Field(
        default=False,
        description="Si es true, prioriza solo documentos pendientes segun estado incremental.",
    )


class JobResponse(BaseModel):
    """Representacion publica del estado de un job."""

    job_id: str
    job_type: str
    status: JobStatus
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    progress: int = 0
    total: int = 0
    document_ids: list[str] = Field(default_factory=list)
    result: dict = Field(default_factory=dict)
    error: str | None = None


class JobListResponse(BaseModel):
    """Listado de jobs recientes."""

    total: int
    items: list[JobResponse]
