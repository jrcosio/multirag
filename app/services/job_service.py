from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.domain.exceptions import NotFoundError
from app.infrastructure.document_status_store import DocumentStatusStore
from app.infrastructure.job_store import JobRecord, JobStore
from app.schemas.jobs import JobStatus
from app.services.index_service import IndexService


class JobService:
    """Gestiona creacion, seguimiento y ejecucion de jobs asincronos."""

    def __init__(self, job_store: JobStore, status_store: DocumentStatusStore) -> None:
        self.job_store = job_store
        self.status_store = status_store

    def create_index_job(self, document_ids: list[str], file_hash_map: dict[str, str]) -> JobRecord:
        """Crea un job en estado encolado para indexacion."""

        job_id = str(uuid.uuid4())
        job = self.job_store.create(
            job_id=job_id,
            job_type="index",
            document_ids=document_ids,
            file_hash_map=file_hash_map,
        )
        for doc_id in document_ids:
            file_hash = file_hash_map.get(doc_id, "")
            if file_hash:
                self.status_store.set_status(
                    document_id=doc_id,
                    status="queued",
                    file_hash=file_hash,
                    last_job_id=job_id,
                    last_error=None,
                )
        return job

    def get_job(self, job_id: str) -> JobRecord:
        """Recupera un job existente o lanza error de recurso inexistente."""

        job = self.job_store.get(job_id)
        if not job:
            raise NotFoundError(message="Job no encontrado.", details={"job_id": job_id})
        return job

    def list_jobs(self) -> list[JobRecord]:
        """Lista jobs registrados para consulta de historico reciente."""

        return self.job_store.list()

    def run_index_job(
        self,
        job_id: str,
        index_service: IndexService,
        document_ids: list[str] | None,
        all_pending: bool,
    ) -> None:
        """Ejecuta trabajo de indexado y persiste progreso/resultado final."""

        job = self.get_job(job_id)
        job.status = JobStatus.running
        job.started_at = datetime.now(tz=UTC)
        self.job_store.update(job)

        tracked = set(job.document_ids)

        def on_event(event: str, path: str) -> None:
            if tracked and path not in tracked:
                return
            file_hash = job.file_hash_map.get(path, "")
            if not file_hash:
                return
            if event == "file_started":
                self.status_store.set_status(
                    document_id=path,
                    status="processing",
                    file_hash=file_hash,
                    last_job_id=job_id,
                    last_error=None,
                )
            elif event in {"file_processed", "file_skipped", "file_empty"}:
                self.status_store.set_status(
                    document_id=path,
                    status="processed",
                    file_hash=file_hash,
                    last_job_id=job_id,
                    last_error=None,
                    last_indexed_at=datetime.now(tz=UTC),
                )

        try:
            result = index_service.index_with_events(
                document_ids=document_ids,
                all_pending=all_pending,
                on_event=on_event,
            )
            job.result = result
            job.total = int(result.get("total_files", 0))
            job.progress = int(result.get("processed_files", 0)) + int(result.get("skipped_files", 0))
            failed_reasons = result.get("failed_reasons", {}) or {}
            for path, reason in failed_reasons.items():
                if tracked and path not in tracked:
                    continue
                file_hash = job.file_hash_map.get(path, "")
                if not file_hash:
                    continue
                self.status_store.set_status(
                    document_id=path,
                    status="failed",
                    file_hash=file_hash,
                    last_job_id=job_id,
                    last_error=str(reason),
                )
            job.status = JobStatus.completed
        except Exception as exc:  # noqa: BLE001
            job.status = JobStatus.failed
            job.error = str(exc)
        finally:
            job.finished_at = datetime.now(tz=UTC)
            self.job_store.update(job)
