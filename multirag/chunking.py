from __future__ import annotations

import uuid

from multirag.types import Chunk, RawDocument


def split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Divide texto largo en fragmentos para mejorar recuperacion y contexto."""

    clean = text.strip()
    if not clean:
        return []

    chunks: list[str] = []
    start = 0
    text_len = len(clean)
    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunks.append(clean[start:end])
        if end >= text_len:
            break
        start = max(0, end - chunk_overlap)
    return chunks


def build_chunks(doc: RawDocument, chunk_size: int, chunk_overlap: int) -> list[Chunk]:
    """Convierte un documento ya leido en chunks listos para indexarse."""

    parts = split_text(doc.text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    out: list[Chunk] = []
    for idx, part in enumerate(parts):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc.relative_path}:{doc.file_hash}:{idx}"))
        out.append(
            Chunk(
                id=point_id,
                text=part,
                source_path=doc.relative_path,
                modality=doc.modality,
                chunk_index=idx,
                file_hash=doc.file_hash,
                surrogate_text=part,
                media_kind="text",
            )
        )
    return out
