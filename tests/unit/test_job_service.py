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


def test_job_service_marks_queued_documents_failed_on_global_error() -> None:
    status_store = DocumentStatusStore(Path(".rag_state/test_status_unit3.json"))
    status_store.clear()
    service = JobService(JobStore(), status_store)
    doc_id = "demo.pdf"
    file_hash = "abc123"
    job = service.create_index_job(document_ids=[doc_id], file_hash_map={doc_id: file_hash})

    service.run_index_job(job.job_id, _FailIndexService(), document_ids=[doc_id], all_pending=False)

    status = status_store.get(doc_id)
    assert status is not None
    assert status["status"] == "failed"
    assert status["last_job_id"] == job.job_id
    assert status["last_error"] == "boom"


def test_job_service_reuses_active_job_instead_of_requeue() -> None:
    status_store = DocumentStatusStore(Path(".rag_state/test_status_unit4.json"))
    status_store.clear()
    service = JobService(JobStore(), status_store)
    doc_id = "demo.pdf"
    file_hash = "abc123"

    first = service.create_index_job(document_ids=[doc_id], file_hash_map={doc_id: file_hash})
    reused, created = service.create_or_reuse_index_job(
        document_ids=[doc_id],
        file_hash_map={doc_id: file_hash},
    )

    assert created is False
    assert reused.job_id == first.job_id


def test_job_service_requeues_when_previous_job_is_not_active() -> None:
    status_store = DocumentStatusStore(Path(".rag_state/test_status_unit5.json"))
    status_store.clear()
    job_store = JobStore()
    service = JobService(job_store, status_store)
    doc_id = "demo.pdf"
    file_hash = "abc123"

    first = service.create_index_job(document_ids=[doc_id], file_hash_map={doc_id: file_hash})
    first.status = JobStatus.failed
    job_store.update(first)

    second, created = service.create_or_reuse_index_job(
        document_ids=[doc_id],
        file_hash_map={doc_id: file_hash},
    )

    assert created is True
    assert second.job_id != first.job_id


def test_job_service_creates_new_job_only_for_non_active_documents() -> None:
    status_store = DocumentStatusStore(Path(".rag_state/test_status_unit6.json"))
    status_store.clear()
    service = JobService(JobStore(), status_store)
    doc_active = "active.pdf"
    doc_new = "new.pdf"
    file_hash_map = {doc_active: "hash-active", doc_new: "hash-new"}

    active_job = service.create_index_job(document_ids=[doc_active], file_hash_map={doc_active: "hash-active"})
    mixed, created = service.create_or_reuse_index_job(
        document_ids=[doc_active, doc_new],
        file_hash_map=file_hash_map,
    )

    assert created is True
    assert mixed.job_id != active_job.job_id
    assert mixed.document_ids == [doc_new]
