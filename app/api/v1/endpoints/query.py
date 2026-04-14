from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.dependencies import get_query_service
from app.schemas.query import QueryDebugResponse, QueryRequest, QueryResponse, QuerySource
from app.services.query_service import QueryService

router = APIRouter()


@router.post("", response_model=QueryResponse, summary="Ejecuta inferencia RAG")
def query(payload: QueryRequest, query_service: QueryService = Depends(get_query_service)) -> QueryResponse:
    """Responde una pregunta devolviendo texto final y fuentes relevantes."""

    result = query_service.ask(question=payload.question, retrieval_k=payload.retrieval_k)
    return QueryResponse(answer=result["answer"], sources=_to_sources(result.get("matches", [])))


@router.post("/debug", response_model=QueryDebugResponse, summary="Ejecuta inferencia RAG con debug")
def query_debug(
    payload: QueryRequest,
    query_service: QueryService = Depends(get_query_service),
) -> QueryDebugResponse:
    """Responde una pregunta incluyendo resultados crudos para troubleshooting."""

    result = query_service.ask(question=payload.question, retrieval_k=payload.retrieval_k)
    matches = result.get("matches", [])
    return QueryDebugResponse(
        answer=result["answer"],
        sources=_to_sources(matches),
        raw_matches=matches,
    )


def _to_sources(matches: list[dict]) -> list[QuerySource]:
    """Convierte payload de retrieval interno al esquema publico de fuentes."""

    return [
        QuerySource(
            source_path=match.get("source_path", "desconocido"),
            modality=match.get("modality", "unknown"),
            chunk_index=int(match.get("chunk_index", -1)),
            score=float(match.get("score", 0.0)),
            page_start=match.get("page_start"),
            page_end=match.get("page_end"),
            start_sec=match.get("start_sec"),
            end_sec=match.get("end_sec"),
        )
        for match in matches
    ]
