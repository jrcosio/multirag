from __future__ import annotations

from app.domain.exceptions import NotFoundError
from app.infrastructure.file_storage import FileStorage
from multirag.config import Settings
from multirag.gemini_client import GeminiClient
from multirag.pipeline import ingest_documents
from multirag.state import ProcessedState
from multirag.vector_store import VectorStore


class IndexService:
    """Ejecuta indexacion RAG aplicando reglas de seleccion de documentos."""

    def __init__(
        self,
        settings: Settings,
        gemini: GeminiClient,
        store: VectorStore,
        state: ProcessedState,
        storage: FileStorage,
    ) -> None:
        self.settings = settings
        self.gemini = gemini
        self.store = store
        self.state = state
        self.storage = storage

    def index(self, document_ids: list[str] | None = None, all_pending: bool = False) -> dict[str, object]:
        """Lanza la ingesta incremental, opcionalmente forzando documentos concretos."""

        return self.index_with_events(document_ids=document_ids, all_pending=all_pending, on_event=None)

    def index_with_events(
        self,
        document_ids: list[str] | None,
        all_pending: bool,
        on_event,
    ) -> dict[str, object]:
        """Ejecuta indexacion incremental permitiendo observabilidad por eventos."""

        if document_ids:
            for document_id in document_ids:
                if not self.storage.exists(document_id):
                    raise NotFoundError(
                        message="Documento no encontrado para indexacion.",
                        details={"document_id": document_id},
                    )
            # Al desmarcar, forzamos reindexado en la corrida incremental siguiente.
            for document_id in document_ids:
                self.state.unmark_processed(document_id)

        if all_pending:
            # No requiere accion adicional: ingest_documents aplica incremental de forma nativa.
            pass

        return ingest_documents(
            settings=self.settings,
            gemini=self.gemini,
            store=self.store,
            use_progress=False,
            on_event=on_event,
        )

    def resolve_target_documents(self, document_ids: list[str] | None, all_pending: bool) -> list[str]:
        """Determina el conjunto real de documentos objetivo para un job de indexacion."""

        if document_ids:
            missing = [doc_id for doc_id in document_ids if not self.storage.exists(doc_id)]
            if missing:
                raise NotFoundError(
                    message="Hay documentos inexistentes en la solicitud.",
                    details={"missing": missing},
                )
            return sorted(set(document_ids))

        docs = self.storage.list_documents()
        if all_pending:
            pending: list[str] = []
            for doc in docs:
                if not self.state.is_processed(doc.document_id, doc.file_hash):
                    pending.append(doc.document_id)
            return pending
        return [doc.document_id for doc in docs]

    def file_hash_map(self, document_ids: list[str]) -> dict[str, str]:
        """Devuelve hash actual por documento para trazabilidad de estado por job."""

        by_id = {doc.document_id: doc.file_hash for doc in self.storage.list_documents()}
        return {doc_id: by_id.get(doc_id, "") for doc_id in document_ids}
