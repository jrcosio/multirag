from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock


class DocumentStatusStore:
    """Persiste el estado de procesamiento por documento para la API."""

    def __init__(self, status_file: Path) -> None:
        self.status_file = status_file
        self.status_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        if not self.status_file.exists():
            self._save({})

    def get(self, document_id: str) -> dict | None:
        """Obtiene el estado almacenado de un documento concreto."""

        with self._lock:
            data = self._load()
            return data.get(document_id)

    def set_status(
        self,
        document_id: str,
        status: str,
        file_hash: str,
        last_job_id: str | None = None,
        last_error: str | None = None,
        last_indexed_at: datetime | None = None,
    ) -> None:
        """Actualiza el estado persistido de un documento con metadata de seguimiento."""

        with self._lock:
            data = self._load()
            previous = data.get(document_id, {})
            data[document_id] = {
                "status": status,
                "file_hash": file_hash,
                "last_job_id": last_job_id,
                "last_error": last_error,
                "last_indexed_at": (
                    last_indexed_at.astimezone(UTC).isoformat() if last_indexed_at else previous.get("last_indexed_at")
                ),
                "updated_at": datetime.now(tz=UTC).isoformat(),
            }
            self._save(data)

    def remove(self, document_id: str) -> bool:
        """Elimina el estado de un documento si existe."""

        with self._lock:
            data = self._load()
            removed = data.pop(document_id, None) is not None
            if removed:
                self._save(data)
            return removed

    def clear(self) -> None:
        """Limpia todos los estados de documentos almacenados."""

        with self._lock:
            self._save({})

    def _load(self) -> dict[str, dict]:
        with self.status_file.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, data: dict[str, dict]) -> None:
        with self.status_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=True, indent=2)
