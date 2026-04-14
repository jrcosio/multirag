from __future__ import annotations

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Entrada para ejecutar una consulta RAG."""

    question: str = Field(min_length=3, description="Pregunta del usuario final.")
    retrieval_k: int | None = Field(
        default=None,
        ge=1,
        le=50,
        description="Numero de resultados a recuperar; si se omite, usa configuracion global.",
    )


class QuerySource(BaseModel):
    """Fuente recuperada usada para responder la consulta."""

    source_path: str
    modality: str
    chunk_index: int
    score: float
    page_start: int | None = None
    page_end: int | None = None
    start_sec: float | None = None
    end_sec: float | None = None


class QueryResponse(BaseModel):
    """Respuesta compacta para consumo de aplicaciones cliente."""

    answer: str
    sources: list[QuerySource]


class QueryDebugResponse(QueryResponse):
    """Respuesta extendida para diagnosticar calidad de retrieval."""

    raw_matches: list[dict]
