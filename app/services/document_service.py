from __future__ import annotations

from datetime import datetime

from app.domain.exceptions import NotFoundError
from app.infrastructure.document_status_store import DocumentStatusStore
from app.infrastructure.file_storage import FileStorage, StoredDocument
from multirag.state import ProcessedState


class DocumentService:
    """Orquesta operaciones de carga y consulta de documentos PDF."""

    def __init__(self, storage: FileStorage, state: ProcessedState, status_store: DocumentStatusStore) -> None:
        self.storage = storage
        self.state = state
        self.status_store = status_store

    def upload_documents(self, files: list[tuple[str, bytes]]) -> list[StoredDocument]:
        """Guarda multiples PDFs y devuelve metadata de los archivos persistidos."""

        uploaded: list[StoredDocument] = []
        for filename, content in files:
            item = self.storage.save_pdf(filename=filename, content=content)
            self.status_store.set_status(
                document_id=item.document_id,
                status="not_started",
                file_hash=item.file_hash,
                last_error=None,
            )
            uploaded.append(item)
        return uploaded

    def list_documents(self) -> list[dict]:
        """Lista documentos junto con su estado de indexacion incremental."""

        items = self.storage.list_pdfs()
        out: list[dict] = []
        for doc in items:
            indexed = self.state.is_processed(doc.document_id, doc.file_hash)
            status_record = self.status_store.get(doc.document_id) or {}
            if status_record.get("file_hash") == doc.file_hash:
                processing_status = status_record.get("status", "not_started")
            elif indexed:
                processing_status = "processed"
            else:
                processing_status = "not_started"

            out.append(
                {
                    "document": doc,
                    "indexed": indexed,
                    "processing_status": processing_status,
                    "last_job_id": status_record.get("last_job_id"),
                    "last_error": status_record.get("last_error"),
                    "last_indexed_at": _parse_dt(status_record.get("last_indexed_at")),
                }
            )
        return out

    def ensure_exists(self, document_id: str) -> None:
        """Valida existencia de documento para operaciones dirigidas."""

        if not self.storage.exists(document_id):
            raise NotFoundError(message="Documento no encontrado.", details={"document_id": document_id})


def _parse_dt(value: str | None) -> datetime | None:
    """Convierte ISO string a datetime para respuesta de API."""

    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
