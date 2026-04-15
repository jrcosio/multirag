from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends

from app.core.dependencies import get_index_service, get_job_service
from app.schemas.jobs import CreateIndexJobRequest, JobListResponse, JobResponse
from app.services.index_service import IndexService
from app.services.job_service import JobService

router = APIRouter()


@router.post("/index", response_model=JobResponse, summary="Crea job asincrono de indexacion")
def create_index_job(
    payload: CreateIndexJobRequest,
    background_tasks: BackgroundTasks,
    job_service: JobService = Depends(get_job_service),
    index_service: IndexService = Depends(get_index_service),
) -> JobResponse:
    """Encola un trabajo de indexacion y devuelve su identificador para seguimiento."""

    targets = index_service.resolve_target_documents(
        document_ids=payload.document_ids,
        all_pending=payload.all_pending,
    )
    file_hash_map = index_service.file_hash_map(targets)
    job, created = job_service.create_or_reuse_index_job(document_ids=targets, file_hash_map=file_hash_map)
    if created:
        background_tasks.add_task(
            job_service.run_index_job,
            job.job_id,
            index_service,
            job.document_ids,
            payload.all_pending,
        )
    return _to_job_response(job)


@router.get("/{job_id}", response_model=JobResponse, summary="Consulta estado de un job")
def get_job(job_id: str, job_service: JobService = Depends(get_job_service)) -> JobResponse:
    """Devuelve estado, progreso y resultado del job solicitado."""

    return _to_job_response(job_service.get_job(job_id))


@router.get("", response_model=JobListResponse, summary="Lista jobs recientes")
def list_jobs(job_service: JobService = Depends(get_job_service)) -> JobListResponse:
    """Lista trabajos asincronos de indexacion para monitoreo operativo."""

    jobs = [_to_job_response(item) for item in job_service.list_jobs()]
    return JobListResponse(total=len(jobs), items=jobs)


def _to_job_response(job) -> JobResponse:
    """Mapea el estado interno de job al contrato publico de API."""

    return JobResponse(
        job_id=job.job_id,
        job_type=job.job_type,
        status=job.status,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        progress=job.progress,
        total=job.total,
        document_ids=job.document_ids,
        result=job.result,
        error=job.error,
    )
