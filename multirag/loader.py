from __future__ import annotations

import hashlib
import io
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from multirag.types import MediaSegment, RawDocument

TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".py", ".json", ".csv", ".html", ".xml"}
PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def supported_files(root: Path) -> list[Path]:
    """Lista los archivos candidatos para ingesta segun extensiones soportadas."""

    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)
        return []

    paths: list[Path] = []
    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() in TEXT_EXTENSIONS | PDF_EXTENSIONS | IMAGE_EXTENSIONS:
            paths.append(file_path)

    return sorted(paths)


def sha256_file(path: Path) -> str:
    """Calcula una huella estable para detectar cambios incrementales por archivo."""

    digest = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def read_text_file(path: Path) -> str:
    """Obtiene contenido textual de archivos planos con tolerancia basica de codificacion."""

    for encoding in ("utf-8", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return ""


def read_pdf(path: Path) -> str:
    """Entrega una version textual unificada del PDF para el flujo de fallback."""

    return "\n\n".join(read_pdf_pages(path)).strip()


def read_pdf_pages(path: Path) -> list[str]:
    """Extrae texto por pagina para mantener trazabilidad y segmentacion del PDF."""

    reader = PdfReader(str(path))
    pages: list[str] = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return pages


def recommend_pdf_pages_per_chunk(
    path: Path,
    default_pages_per_chunk: int,
    table_pages_per_chunk: int,
) -> tuple[int, str]:
    """Sugiere tamano de segmento PDF segun presencia de patrones tipo tabla."""

    base = max(1, default_pages_per_chunk)
    table_size = max(1, table_pages_per_chunk)
    page_texts = read_pdf_pages(path)
    if not page_texts:
        return base, "sin texto detectable; se usa tamano base"

    sample_pages = page_texts[: min(8, len(page_texts))]
    table_hits = 0
    numeric_hits = 0
    for text in sample_pages:
        lower = text.lower()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if any(token in lower for token in ("tabla", "table", "column", "fila", "row")):
            table_hits += 1
        if any(line.count("|") >= 2 or line.count("\t") >= 2 for line in lines):
            table_hits += 1
        if any(_looks_numeric_row(line) for line in lines):
            numeric_hits += 1

    table_score = table_hits + numeric_hits
    if table_score >= 3:
        chosen = max(base, table_size)
        return chosen, f"patron tabular detectado (score={table_score})"
    return base, f"sin patron tabular fuerte (score={table_score})"


def _looks_numeric_row(line: str) -> bool:
    """Detecta filas con densidad numerica alta, utiles para inferir tablas."""

    digits = sum(ch.isdigit() for ch in line)
    separators = sum(ch in ",.;:%/-" for ch in line)
    spaces = line.count(" ")
    return digits >= 6 and (separators >= 2 or spaces >= 4)


def image_mime_type(path: Path) -> str:
    """Infiere el MIME de imagen para enviar el archivo al endpoint multimodal correcto."""

    ext = path.suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }.get(ext, "application/octet-stream")


def build_raw_document(path: Path, root: Path, image_summary: str | None = None) -> RawDocument:
    """Construye la representacion base de un archivo para indexacion textual clasica."""

    ext = path.suffix.lower()
    file_hash = sha256_file(path)
    relative = str(path.relative_to(root)).replace("\\", "/")

    if ext in TEXT_EXTENSIONS:
        text = read_text_file(path)
        modality = "text"
    elif ext in PDF_EXTENSIONS:
        text = read_pdf(path)
        modality = "pdf"
    elif ext in IMAGE_EXTENSIONS:
        text = image_summary or ""
        modality = "image"
    else:
        text = ""
        modality = "unknown"

    return RawDocument(
        path=path,
        relative_path=relative,
        modality=modality,
        text=text,
        file_hash=file_hash,
    )


def build_pdf_media_segments(
    path: Path,
    root: Path,
    file_hash: str,
    pages_per_chunk: int,
) -> list[MediaSegment]:
    """Prepara segmentos de PDF como entradas multimodales reutilizables en embeddings."""

    reader = PdfReader(str(path))
    page_texts = [page.extract_text() or "" for page in reader.pages]
    total_pages = len(reader.pages)
    if total_pages == 0:
        return []

    relative = str(path.relative_to(root)).replace("\\", "/")
    chunk_size = max(1, pages_per_chunk)
    segments: list[MediaSegment] = []

    for segment_idx, start in enumerate(range(0, total_pages, chunk_size)):
        end = min(total_pages, start + chunk_size)
        writer = PdfWriter()
        for page_idx in range(start, end):
            writer.add_page(reader.pages[page_idx])

        buffer = io.BytesIO()
        writer.write(buffer)
        segment_text = "\n\n".join(page_texts[start:end]).strip()
        if not segment_text:
            segment_text = f"PDF {relative}, paginas {start + 1}-{end}"

        segments.append(
            MediaSegment(
                source_path=relative,
                modality="pdf",
                chunk_index=segment_idx,
                file_hash=file_hash,
                surrogate_text=segment_text,
                media_bytes=buffer.getvalue(),
                media_mime="application/pdf",
                page_start=start + 1,
                page_end=end,
            )
        )

    return segments


def build_image_media_segment(
    path: Path,
    root: Path,
    file_hash: str,
    surrogate_text: str,
) -> MediaSegment:
    """Genera un segmento multimodal de imagen con texto de apoyo para recuperacion."""

    relative = str(path.relative_to(root)).replace("\\", "/")
    text = surrogate_text.strip() or f"Imagen {relative}"
    return MediaSegment(
        source_path=relative,
        modality="image",
        chunk_index=0,
        file_hash=file_hash,
        surrogate_text=text,
        media_bytes=path.read_bytes(),
        media_mime=image_mime_type(path),
    )
