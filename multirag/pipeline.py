from __future__ import annotations

import sys
import uuid
from collections.abc import Callable
from pathlib import Path

from tqdm import tqdm

from multirag.chunking import build_chunks
from multirag.config import Settings
from multirag.gemini_client import GeminiClient
from multirag.loader import (
    IMAGE_EXTENSIONS,
    PDF_EXTENSIONS,
    build_image_media_segment,
    build_pdf_media_segments,
    build_raw_document,
    image_mime_type,
    recommend_pdf_pages_per_chunk,
    sha256_file,
    supported_files,
)
from multirag.state import ProcessedState
from multirag.types import Chunk, MediaSegment
from multirag.vector_store import VectorStore


IngestEvent = Callable[[str, str], None]
AskStageEvent = Callable[[str], None]


def ingest_documents(
    settings: Settings,
    gemini: GeminiClient,
    store: VectorStore,
    use_progress: bool = True,
    on_event: IngestEvent | None = None,
) -> dict[str, object]:
    """Orquesta la ingesta incremental y deja el indice listo para consultas."""

    state = ProcessedState(settings.state_dir / "processed.json")
    files = supported_files(settings.doc_raw_dir)
    force_reindex = not store.collection_exists()

    processed = 0
    skipped = 0
    chunks_indexed = 0
    collection_ready = False
    failed_files: list[str] = []
    failed_reasons: dict[str, str] = {}

    show_progress = use_progress and sys.stdout.isatty()
    file_bar = tqdm(files, desc="Documentos", unit="file", disable=not show_progress)

    for file_path in file_bar:
        try:
            relative_path = str(file_path.relative_to(settings.doc_raw_dir)).replace("\\", "/")
            file_hash = sha256_file(file_path)
            if not force_reindex and state.is_processed(relative_path, file_hash):
                skipped += 1
                _emit(on_event, "file_skipped", relative_path)
                continue

            chunks, vectors = _index_file(
                path=file_path,
                root=settings.doc_raw_dir,
                file_hash=file_hash,
                settings=settings,
                gemini=gemini,
                show_progress=show_progress,
                on_event=on_event,
            )
            if not chunks:
                state.mark_processed(relative_path, file_hash)
                skipped += 1
                _emit(on_event, "file_empty", relative_path)
                continue

            if not collection_ready:
                store.ensure_collection(vector_size=len(vectors[0]))
                collection_ready = True

            store.remove_source(relative_path)
            store.upsert_chunks(chunks, vectors)

            state.mark_processed(relative_path, file_hash)
            processed += 1
            chunks_indexed += len(chunks)
            _emit(on_event, "file_processed", relative_path)
        except Exception as exc:  # noqa: BLE001
            failed_path = str(file_path.relative_to(settings.doc_raw_dir)).replace("\\", "/")
            failed_files.append(failed_path)
            failed_reasons[failed_path] = str(exc)
            _emit(on_event, "file_failed", failed_path)
            continue

    file_bar.close()

    return {
        "processed_files": processed,
        "skipped_files": skipped,
        "indexed_chunks": chunks_indexed,
        "total_files": len(files),
        "failed_count": len(failed_files),
        "failed_files": failed_files,
        "failed_reasons": failed_reasons,
    }


def answer_question(
    settings: Settings,
    gemini: GeminiClient,
    store: VectorStore,
    question: str,
    on_stage: AskStageEvent | None = None,
) -> dict:
    """Resuelve una pregunta combinando recuperacion vectorial y generacion con contexto."""

    _emit_stage(on_stage, "embedding_question")
    query_embedding = gemini.embed_text(question)
    _emit_stage(on_stage, "search_qdrant")
    if store.collection_exists():
        matches = store.search(query_vector=query_embedding, limit=settings.retrieval_k)
    else:
        matches = []

    context_blocks = []
    for m in matches:
        context_text = m.get("surrogate_text") or m.get("text", "")
        context_blocks.append(
            (
                f"[fuente={m['source_path']} modalidad={m['modality']} "
                f"chunk={m['chunk_index']} score={m['score']:.4f}]\n{context_text}"
            )
        )

    _emit_stage(on_stage, "generating_answer")
    answer = gemini.answer_with_context(question=question, context_blocks=context_blocks)
    return {"answer": answer, "matches": matches}


def _index_file(
    path: Path,
    root: Path,
    file_hash: str,
    settings: Settings,
    gemini: GeminiClient,
    show_progress: bool,
    on_event: IngestEvent | None,
) -> tuple[list[Chunk], list[list[float]]]:
    """Selecciona la estrategia de indexacion adecuada segun modalidad y configuracion."""

    ext = path.suffix.lower()
    pdf_mode = settings.pdf_mode if settings.pdf_mode in {"direct", "text", "hybrid"} else "hybrid"

    if settings.enable_multimodal and ext in IMAGE_EXTENSIONS:
        relative = str(path.relative_to(root)).replace("\\", "/")
        _emit(on_event, "image_describing", relative)
        image_bytes = path.read_bytes()
        mime_type = image_mime_type(path)
        summary = gemini.describe_image(image_bytes, mime_type, relative)
        segment = build_image_media_segment(path, root, file_hash, summary)
        chunk = _chunk_from_media_segment(segment)
        vector = _embed_media_segment(gemini, segment, settings.media_fallback_to_text)
        return [chunk], [vector]

    if settings.enable_multimodal and ext in PDF_EXTENSIONS and pdf_mode in {"direct", "hybrid"}:
        pages_per_chunk = settings.pdf_pages_per_chunk
        reason = f"modo fijo ({pages_per_chunk} paginas por chunk)"
        if settings.pdf_adaptive_pages:
            pages_per_chunk, reason = recommend_pdf_pages_per_chunk(
                path=path,
                default_pages_per_chunk=settings.pdf_pages_per_chunk,
                table_pages_per_chunk=settings.pdf_pages_per_chunk_tables,
            )
        if settings.pdf_adaptive_debug:
            relative = str(path.relative_to(root)).replace("\\", "/")
            _emit(
                on_event,
                "pdf_chunking_strategy",
                f"{relative} -> {pages_per_chunk} paginas/chunk ({reason})",
            )
        segments = build_pdf_media_segments(
            path=path,
            root=root,
            file_hash=file_hash,
            pages_per_chunk=pages_per_chunk,
        )
        if not segments:
            return [], []

        allow_fallback = pdf_mode == "hybrid" and settings.media_fallback_to_text
        chunks, vectors = _embed_media_segments(
            gemini=gemini,
            segments=segments,
            allow_fallback=allow_fallback,
            show_progress=show_progress,
            desc=f"Embeddings {segments[0].source_path}",
        )
        if chunks:
            return chunks, vectors
        if pdf_mode == "direct":
            raise RuntimeError("No se pudieron generar embeddings multimodales para el PDF.")

    raw_doc = build_raw_document(path=path, root=root)
    chunks = build_chunks(
        raw_doc,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    if not chunks:
        return [], []

    vectors = _embed_chunks_resilient(
        gemini=gemini,
        chunks=chunks,
        batch_size=settings.embed_batch_size,
        show_progress=show_progress,
        desc=f"Embeddings {raw_doc.relative_path}",
    )
    return chunks, vectors


def _chunk_from_media_segment(segment: MediaSegment) -> Chunk:
    """Convierte un segmento multimodal en la estructura estandar que usa Qdrant."""

    point_id = str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"{segment.source_path}:{segment.file_hash}:{segment.modality}:{segment.chunk_index}",
        )
    )
    return Chunk(
        id=point_id,
        text=segment.surrogate_text,
        source_path=segment.source_path,
        modality=segment.modality,
        chunk_index=segment.chunk_index,
        file_hash=segment.file_hash,
        surrogate_text=segment.surrogate_text,
        page_start=segment.page_start,
        page_end=segment.page_end,
        start_sec=segment.start_sec,
        end_sec=segment.end_sec,
        media_mime=segment.media_mime,
        media_kind=segment.modality,
    )


def _embed_media_segment(gemini: GeminiClient, segment: MediaSegment, allow_fallback: bool) -> list[float]:
    """Obtiene el vector de un segmento de media aplicando fallback cuando corresponde."""

    if segment.media_mime == "application/pdf":
        if allow_fallback:
            try:
                return gemini.embed_pdf_bytes(segment.media_bytes)
            except Exception:  # noqa: BLE001
                return gemini.embed_text(segment.surrogate_text)
        return gemini.embed_pdf_bytes(segment.media_bytes)

    if segment.modality == "image":
        if allow_fallback:
            try:
                return gemini.embed_image_bytes(segment.media_bytes, segment.media_mime)
            except Exception:  # noqa: BLE001
                return gemini.embed_text(segment.surrogate_text)
        return gemini.embed_image_bytes(segment.media_bytes, segment.media_mime)

    return gemini.embed_text(segment.surrogate_text)


def _embed_media_segments(
    gemini: GeminiClient,
    segments: list[MediaSegment],
    allow_fallback: bool,
    show_progress: bool,
    desc: str,
) -> tuple[list[Chunk], list[list[float]]]:
    """Procesa una coleccion de segmentos multimodales de forma tolerante a fallos."""

    chunks: list[Chunk] = []
    vectors: list[list[float]] = []
    progress = tqdm(total=len(segments), desc=desc, unit="chunk", leave=False, disable=not show_progress)

    for segment in segments:
        try:
            vector = _embed_media_segment(gemini, segment, allow_fallback=allow_fallback)
        except Exception:  # noqa: BLE001
            progress.update(1)
            continue
        chunks.append(_chunk_from_media_segment(segment))
        vectors.append(vector)
        progress.update(1)

    progress.close()
    return chunks, vectors


def _emit(callback: IngestEvent | None, event: str, detail: str) -> None:
    """Publica eventos de ingesta para desacoplar pipeline y presentacion CLI."""

    if callback:
        callback(event, detail)


def _emit_stage(callback: AskStageEvent | None, stage: str) -> None:
    """Notifica cambios de etapa durante una consulta para mejorar observabilidad."""

    if callback:
        callback(stage)


def _embed_chunks_resilient(
    gemini: GeminiClient,
    chunks: list,
    batch_size: int,
    show_progress: bool,
    desc: str,
) -> list[list[float]]:
    """Genera embeddings textuales por lotes para equilibrar velocidad y estabilidad."""

    effective_batch = max(1, batch_size)
    vectors: list[list[float]] = []
    progress = tqdm(total=len(chunks), desc=desc, unit="chunk", leave=False, disable=not show_progress)

    for start in range(0, len(chunks), effective_batch):
        batch = chunks[start : start + effective_batch]
        texts = [chunk.text for chunk in batch]
        batch_vectors = gemini.embed_texts(texts)
        vectors.extend(batch_vectors)
        progress.update(len(batch))

    progress.close()
    return vectors
