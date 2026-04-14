from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from multirag.loader import sha256_file


@dataclass
class StoredDocument:
    """Representa un PDF almacenado localmente y listo para indexar."""

    document_id: str
    filename: str
    size_bytes: int
    file_hash: str
    updated_at: datetime


class FileStorage:
    """Administra el almacenamiento local de documentos PDF para la API."""

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def save_pdf(self, filename: str, content: bytes) -> StoredDocument:
        """Persiste un PDF en el directorio de documentos y retorna su metadata."""

        safe_name = self._sanitize_filename(filename)
        target = self.root_dir / safe_name
        target.write_bytes(content)
        return self._to_stored(target)

    def list_pdfs(self) -> list[StoredDocument]:
        """Lista todos los PDFs disponibles para indexacion o gestion."""

        docs: list[StoredDocument] = []
        for path in self.root_dir.rglob("*.pdf"):
            if path.is_file():
                docs.append(self._to_stored(path))
        return sorted(docs, key=lambda item: item.document_id)

    def exists(self, document_id: str) -> bool:
        """Indica si un documento existe en almacenamiento local."""

        return (self.root_dir / document_id).is_file()

    def delete(self, document_id: str) -> bool:
        """Elimina un documento concreto si existe."""

        path = self.root_dir / document_id
        if not path.exists() or not path.is_file():
            return False
        path.unlink()
        return True

    def delete_all_pdfs(self) -> int:
        """Elimina todos los PDFs almacenados y devuelve cuantos borro."""

        count = 0
        for path in list(self.root_dir.rglob("*.pdf")):
            if path.is_file():
                path.unlink()
                count += 1
        return count

    def _to_stored(self, path: Path) -> StoredDocument:
        """Convierte un archivo del filesystem en metadata de dominio."""

        relative = str(path.relative_to(self.root_dir)).replace("\\", "/")
        stat = path.stat()
        return StoredDocument(
            document_id=relative,
            filename=path.name,
            size_bytes=stat.st_size,
            file_hash=sha256_file(path),
            updated_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
        )

    def _sanitize_filename(self, filename: str) -> str:
        """Normaliza nombres de archivo para evitar rutas inseguras o ilegibles."""

        clean = filename.replace("\\", "/").split("/")[-1].strip()
        clean = re.sub(r"[^A-Za-z0-9._-]", "_", clean)
        if not clean.lower().endswith(".pdf"):
            clean = f"{clean}.pdf"
        return clean or "document.pdf"
