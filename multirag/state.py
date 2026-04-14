from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FileState:
    """Describe el estado minimo persistido para deteccion de cambios por archivo."""

    file_hash: str


class ProcessedState:
    """Gestiona el registro incremental de archivos ya ingeridos."""

    def __init__(self, state_file: Path) -> None:
        """Prepara el almacenamiento de estado para soportar ingesta incremental."""

        self.state_file = state_file
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.state_file.exists():
            self._save({})

    def _load(self) -> dict[str, dict[str, str]]:
        """Recupera el estado persistido que guia que archivos se omiten o reprocesan."""

        with self.state_file.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, data: dict[str, dict[str, str]]) -> None:
        """Guarda el estado actualizado para mantener continuidad entre ejecuciones."""

        with self.state_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=True, indent=2)

    def is_processed(self, relative_path: str, file_hash: str) -> bool:
        """Indica si un archivo puede omitirse porque su contenido no ha cambiado."""

        current = self._load().get(relative_path)
        if not current:
            return False
        return current.get("file_hash") == file_hash

    def mark_processed(self, relative_path: str, file_hash: str) -> None:
        """Registra un archivo como procesado para evitar trabajo repetido en futuras corridas."""

        all_state = self._load()
        all_state[relative_path] = {"file_hash": file_hash}
        self._save(all_state)

    def unmark_processed(self, relative_path: str) -> bool:
        """Elimina una entrada concreta del estado incremental si existe."""

        all_state = self._load()
        removed = all_state.pop(relative_path, None) is not None
        if removed:
            self._save(all_state)
        return removed

    def clear(self) -> None:
        """Reinicia por completo el estado incremental de archivos procesados."""

        self._save({})
