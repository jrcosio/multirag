from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.dependencies import get_settings, get_vector_store
from multirag.config import Settings
from multirag.vector_store import VectorStore

router = APIRouter()


@router.get("/health", summary="Liveness de la API")
def health(settings: Settings = Depends(get_settings)) -> dict:
    """Confirma que la API esta en ejecucion y expone datos minimos de versionado."""

    return {
        "status": "ok",
        "service": "multirag-api",
        "embedding_model": settings.embedding_model,
        "llm_model": settings.llm_model,
    }


@router.get("/ready", summary="Readiness con dependencias")
def ready(store: VectorStore = Depends(get_vector_store), settings: Settings = Depends(get_settings)) -> dict:
    """Verifica conectividad basica con Qdrant para readiness checks."""

    qdrant_ok = False
    collection_exists = False
    error = None
    try:
        collection_exists = store.collection_exists()
        qdrant_ok = True
    except Exception as exc:  # noqa: BLE001
        error = str(exc)

    return {
        "status": "ready" if qdrant_ok else "degraded",
        "qdrant_ok": qdrant_ok,
        "collection": settings.qdrant_collection,
        "collection_exists": collection_exists,
        "error": error,
    }
