from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """Centraliza la configuracion operativa del pipeline y de la CLI."""

    gemini_api_key: str
    embedding_model: str
    llm_model: str
    qdrant_url: str
    qdrant_collection: str
    doc_raw_dir: Path
    state_dir: Path
    chunk_size: int
    chunk_overlap: int
    retrieval_k: int
    embed_batch_size: int
    api_max_retries: int
    api_base_delay_ms: int
    api_max_delay_ms: int
    api_jitter_ms: int
    enable_multimodal: bool
    pdf_mode: str
    pdf_pages_per_chunk: int
    pdf_adaptive_pages: bool
    pdf_pages_per_chunk_tables: int
    pdf_adaptive_debug: bool
    media_fallback_to_text: bool
    output_dimensionality: int | None


def load_settings() -> Settings:
    """Carga variables de entorno y construye la configuracion efectiva del sistema."""

    load_dotenv()

    root = Path.cwd()
    doc_raw_dir = root / os.getenv("DOC_RAW_DIR", "doc_raw")
    state_dir = root / os.getenv("RAG_STATE_DIR", ".rag_state")

    output_dimensionality_raw = os.getenv("RAG_OUTPUT_DIMENSIONALITY", "").strip()

    return Settings(
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        embedding_model=os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-2-preview"),
        llm_model=os.getenv("GEMINI_LLM_MODEL", "gemini-3.1-flash-lite-preview"),
        qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        qdrant_collection=os.getenv("QDRANT_COLLECTION", "multirag_docs"),
        doc_raw_dir=doc_raw_dir,
        state_dir=state_dir,
        chunk_size=int(os.getenv("RAG_CHUNK_SIZE", "1200")),
        chunk_overlap=int(os.getenv("RAG_CHUNK_OVERLAP", "200")),
        retrieval_k=int(os.getenv("RAG_RETRIEVAL_K", "5")),
        embed_batch_size=int(os.getenv("RAG_EMBED_BATCH_SIZE", "16")),
        api_max_retries=int(os.getenv("GEMINI_API_MAX_RETRIES", "6")),
        api_base_delay_ms=int(os.getenv("GEMINI_API_BASE_DELAY_MS", "500")),
        api_max_delay_ms=int(os.getenv("GEMINI_API_MAX_DELAY_MS", "10000")),
        api_jitter_ms=int(os.getenv("GEMINI_API_JITTER_MS", "250")),
        enable_multimodal=_as_bool(os.getenv("RAG_ENABLE_MULTIMODAL", "true")),
        pdf_mode=os.getenv("RAG_PDF_MODE", "hybrid").strip().lower(),
        pdf_pages_per_chunk=max(1, int(os.getenv("RAG_PDF_PAGES_PER_CHUNK", "1"))),
        pdf_adaptive_pages=_as_bool(os.getenv("RAG_PDF_ADAPTIVE_PAGES", "true")),
        pdf_pages_per_chunk_tables=max(1, int(os.getenv("RAG_PDF_PAGES_PER_CHUNK_TABLES", "3"))),
        pdf_adaptive_debug=_as_bool(os.getenv("RAG_PDF_ADAPTIVE_DEBUG", "false")),
        media_fallback_to_text=_as_bool(os.getenv("RAG_MEDIA_FALLBACK_TO_TEXT", "true")),
        output_dimensionality=int(output_dimensionality_raw) if output_dimensionality_raw else None,
    )


def _as_bool(value: str) -> bool:
    """Normaliza valores de entorno para activar o desactivar banderas de forma consistente."""

    return value.strip().lower() in {"1", "true", "yes", "on"}
