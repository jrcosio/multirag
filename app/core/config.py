from __future__ import annotations

from multirag.config import Settings, load_settings


def load_app_settings() -> Settings:
    """Expone configuracion del dominio RAG para la capa API."""

    return load_settings()
