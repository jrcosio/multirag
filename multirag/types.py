from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class RawDocument:
    """Representa un archivo listo para pasar por chunking e indexacion."""

    path: Path
    relative_path: str
    modality: str
    text: str
    file_hash: str


@dataclass
class Chunk:
    """Define la unidad recuperable que se almacena en la base vectorial."""

    id: str
    text: str
    source_path: str
    modality: str
    chunk_index: int
    file_hash: str
    surrogate_text: str = ""
    page_start: int | None = None
    page_end: int | None = None
    start_sec: float | None = None
    end_sec: float | None = None
    media_mime: str | None = None
    media_kind: str | None = None


@dataclass
class MediaSegment:
    """Modela un segmento multimodal previo a su conversion en chunk indexable."""

    source_path: str
    modality: str
    chunk_index: int
    file_hash: str
    surrogate_text: str
    media_bytes: bytes
    media_mime: str
    page_start: int | None = None
    page_end: int | None = None
    start_sec: float | None = None
    end_sec: float | None = None
