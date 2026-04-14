from __future__ import annotations

from functools import lru_cache

from app.core.config import load_app_settings
from app.domain.exceptions import ApiError
from app.infrastructure.document_status_store import DocumentStatusStore
from app.infrastructure.file_storage import FileStorage
from app.infrastructure.job_store import JobStore
from app.services.cleanup_service import CleanupService
from app.services.document_service import DocumentService
from app.services.index_service import IndexService
from app.services.job_service import JobService
from app.services.query_service import QueryService
from multirag.config import Settings
from multirag.gemini_client import GeminiClient
from multirag.state import ProcessedState
from multirag.vector_store import VectorStore


@lru_cache
def get_settings() -> Settings:
    """Carga y cachea configuracion para reducir overhead por request."""

    return load_app_settings()


@lru_cache
def get_storage() -> FileStorage:
    """Entrega almacenamiento local de documentos para la API."""

    settings = get_settings()
    return FileStorage(root_dir=settings.doc_raw_dir)


@lru_cache
def get_vector_store() -> VectorStore:
    """Entrega acceso compartido a Qdrant."""

    settings = get_settings()
    return VectorStore(url=settings.qdrant_url, collection_name=settings.qdrant_collection)


@lru_cache
def get_processed_state() -> ProcessedState:
    """Entrega repositorio de estado incremental para documentos."""

    settings = get_settings()
    return ProcessedState(settings.state_dir / "processed.json")


@lru_cache
def get_job_store() -> JobStore:
    """Entrega almacenamiento en memoria para jobs asincronos."""

    return JobStore()


@lru_cache
def get_document_status_store() -> DocumentStatusStore:
    """Entrega repositorio persistente de estado de procesamiento por documento."""

    settings = get_settings()
    return DocumentStatusStore(settings.state_dir / "document_status.json")


@lru_cache
def get_gemini_client() -> GeminiClient:
    """Construye cliente Gemini compartido para indexacion y consultas."""

    settings = get_settings()
    if not settings.gemini_api_key:
        raise ApiError(
            code="missing_api_key",
            message="Falta GEMINI_API_KEY para operaciones de embedding/inferencia.",
            status_code=500,
        )
    return GeminiClient(
        api_key=settings.gemini_api_key,
        embedding_model=settings.embedding_model,
        llm_model=settings.llm_model,
        output_dimensionality=settings.output_dimensionality,
        max_retries=settings.api_max_retries,
        base_delay_ms=settings.api_base_delay_ms,
        max_delay_ms=settings.api_max_delay_ms,
        jitter_ms=settings.api_jitter_ms,
    )


def get_document_service() -> DocumentService:
    """Entrega servicio de administracion de documentos."""

    return DocumentService(
        storage=get_storage(),
        state=get_processed_state(),
        status_store=get_document_status_store(),
    )


def get_cleanup_service() -> CleanupService:
    """Entrega servicio de limpieza de datos vectoriales y estado."""

    return CleanupService(
        storage=get_storage(),
        store=get_vector_store(),
        state=get_processed_state(),
        status_store=get_document_status_store(),
    )


def get_index_service() -> IndexService:
    """Entrega servicio de indexacion RAG."""

    return IndexService(
        settings=get_settings(),
        gemini=get_gemini_client(),
        store=get_vector_store(),
        state=get_processed_state(),
        storage=get_storage(),
    )


def get_query_service() -> QueryService:
    """Entrega servicio de consulta RAG."""

    return QueryService(settings=get_settings(), gemini=get_gemini_client(), store=get_vector_store())


def get_job_service() -> JobService:
    """Entrega servicio de seguimiento y ejecucion de jobs."""

    return JobService(job_store=get_job_store(), status_store=get_document_status_store())
