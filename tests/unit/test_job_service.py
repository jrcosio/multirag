from __future__ import annotations

from pathlib import Path

from app.infrastructure.document_status_store import DocumentStatusStore
from app.infrastructure.job_store import JobStore
from app.schemas.jobs import JobStatus
from app.services.job_service import JobService


class _OkIndexService:
    def index_with_events(self, document_ids=None, all_pending=False, on_event=None):
        return {
            "total_files": 2,
            "processed_files": 1,
            "skipped_files": 1,
            "indexed_chunks": 10,
        }


class _FailIndexService:
    def index_with_events(self, document_ids=None, all_pending=False, on_event=None):
        raise RuntimeError("boom")


def test_job_service_completes_index_job() -> None:
    status_store = DocumentStatusStore(Path(".rag_state/test_status_unit.json"))
    status_store.clear()
    service = JobService(JobStore(), status_store)
    job = service.create_index_job(document_ids=[], file_hash_map={})

    service.run_index_job(job.job_id, _OkIndexService(), document_ids=None, all_pending=False)

    done = service.get_job(job.job_id)
    assert done.status == JobStatus.completed
    assert done.result["indexed_chunks"] == 10
    assert done.progress == 2
    assert done.total == 2


def test_job_service_marks_failed_job() -> None:
    status_store = DocumentStatusStore(Path(".rag_state/test_status_unit2.json"))
    status_store.clear()
    service = JobService(JobStore(), status_store)
    job = service.create_index_job(document_ids=[], file_hash_map={})

    service.run_index_job(job.job_id, _FailIndexService(), document_ids=None, all_pending=False)

    failed = service.get_job(job.job_id)
    assert failed.status == JobStatus.failed
    assert failed.error == "boom"
