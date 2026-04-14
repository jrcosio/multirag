from __future__ import annotations

from app.infrastructure.document_status_store import DocumentStatusStore
from app.infrastructure.file_storage import FileStorage
from multirag.state import ProcessedState
from multirag.vector_store import VectorStore


class CleanupService:
    """Centraliza operaciones destructivas de limpieza para mantener consistencia."""

    def __init__(
        self,
        storage: FileStorage,
        store: VectorStore,
        state: ProcessedState,
        status_store: DocumentStatusStore,
    ) -> None:
        self.storage = storage
        self.store = store
        self.state = state
        self.status_store = status_store

    def delete_document(self, document_id: str) -> dict[str, bool]:
        """Elimina un documento de vectores, estado incremental y almacenamiento local."""

        vectors_deleted = False
        if self.store.collection_exists():
            self.store.remove_source(document_id)
            vectors_deleted = True

        state_deleted = self.state.unmark_processed(document_id)
        file_deleted = self.storage.delete(document_id)
        self.status_store.remove(document_id)
        return {
            "vectors_deleted": vectors_deleted,
            "state_deleted": state_deleted,
            "file_deleted": file_deleted,
        }

    def delete_all(self) -> dict[str, int | bool]:
        """Borra coleccion, estado incremental y todos los PDFs gestionados por la API."""

        collection_deleted = self.store.delete_collection()
        self.state.clear()
        self.status_store.clear()
        files_deleted = self.storage.delete_all_pdfs()
        return {
            "collection_deleted": collection_deleted,
            "state_cleared": True,
            "files_deleted": files_deleted,
        }
