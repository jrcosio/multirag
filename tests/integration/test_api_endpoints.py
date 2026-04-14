from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.core import dependencies
from app.infrastructure.document_status_store import DocumentStatusStore
from app.infrastructure.job_store import JobStore
from app.main import create_app
from app.services.job_service import JobService


class _FakeStored:
    def __init__(self, document_id: str, filename: str, file_hash: str = "abc") -> None:
        self.document_id = document_id
        self.filename = filename
        self.size_bytes = 12
        self.file_hash = file_hash
        self.updated_at = datetime.now(tz=UTC)


class _FakeDocumentService:
    def __init__(self) -> None:
        self.items = {
            "demo.pdf": _FakeStored("demo.pdf", "demo.pdf"),
        }

    def upload_documents(self, files):
        out = []
        for name, _content in files:
            doc = _FakeStored(name, name)
            self.items[doc.document_id] = doc
            out.append(doc)
        return out

    def list_documents(self):
        out = []
        for item in self.items.values():
            out.append(
                {
                    "document": item,
                    "indexed": False,
                    "processing_status": "not_started",
                    "last_job_id": None,
                    "last_error": None,
                    "last_indexed_at": None,
                }
            )
        return out

    def ensure_exists(self, document_id: str):
        if document_id not in self.items:
            raise RuntimeError("not found")


class _FakeCleanupService:
    def delete_document(self, document_id: str):
        return {"vectors_deleted": True, "state_deleted": True, "file_deleted": True}

    def delete_all(self):
        return {"collection_deleted": True, "state_cleared": True, "files_deleted": 3}


class _FakeIndexService:
    def resolve_target_documents(self, document_ids=None, all_pending=False):
        if document_ids:
            return document_ids
        return ["demo.pdf"]

    def file_hash_map(self, document_ids):
        return {doc_id: "abc" for doc_id in document_ids}

    def index(self, document_ids=None, all_pending=False):
        return {
            "total_files": 1,
            "processed_files": 1,
            "skipped_files": 0,
            "failed_count": 0,
            "indexed_chunks": 2,
        }

    def index_with_events(self, document_ids=None, all_pending=False, on_event=None):
        if on_event:
            for doc_id in (document_ids or ["demo.pdf"]):
                on_event("file_started", doc_id)
                on_event("file_processed", doc_id)
        return self.index(document_ids=document_ids, all_pending=all_pending)


class _FakeQueryService:
    def ask(self, question: str, retrieval_k=None):
        return {
            "answer": f"ok: {question}",
            "matches": [
                {
                    "source_path": "demo.pdf",
                    "modality": "pdf",
                    "chunk_index": 0,
                    "score": 0.9,
                }
            ],
        }


def _build_client() -> TestClient:
    app = create_app()
    shared_job_service = JobService(JobStore(), DocumentStatusStore(Path(".rag_state/test_status_integration.json")))
    app.dependency_overrides[dependencies.get_document_service] = lambda: _FakeDocumentService()
    app.dependency_overrides[dependencies.get_cleanup_service] = lambda: _FakeCleanupService()
    app.dependency_overrides[dependencies.get_index_service] = lambda: _FakeIndexService()
    app.dependency_overrides[dependencies.get_query_service] = lambda: _FakeQueryService()
    app.dependency_overrides[dependencies.get_job_service] = lambda: shared_job_service
    return TestClient(app)


def test_health_endpoint() -> None:
    client = _build_client()
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_upload_and_list_documents() -> None:
    client = _build_client()
    response = client.post(
        "/api/v1/documents/upload",
        files={"files": ("nuevo.pdf", b"%PDF-1.4 test", "application/pdf")},
    )
    assert response.status_code == 200
    assert response.json()["uploaded"][0]["document_id"] == "nuevo.pdf"

    listed = client.get("/api/v1/documents")
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1


def test_create_index_job_and_check_status() -> None:
    client = _build_client()
    create = client.post("/api/v1/jobs/index", json={"all_pending": True})
    assert create.status_code == 200
    job_id = create.json()["job_id"]

    status = client.get(f"/api/v1/jobs/{job_id}")
    assert status.status_code == 200
    assert status.json()["status"] in {"queued", "running", "completed"}


def test_query_endpoint() -> None:
    client = _build_client()
    response = client.post("/api/v1/query", json={"question": "hola"})
    assert response.status_code == 200
    assert response.json()["answer"].startswith("ok:")
    assert response.json()["sources"][0]["source_path"] == "demo.pdf"


def test_delete_all_requires_confirm() -> None:
    client = _build_client()
    response = client.delete("/api/v1/documents")
    assert response.status_code == 400
    assert response.json()["code"] == "confirmation_required"
