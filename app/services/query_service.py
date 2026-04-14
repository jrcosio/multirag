from __future__ import annotations

from dataclasses import replace

from multirag.config import Settings
from multirag.gemini_client import GeminiClient
from multirag.pipeline import answer_question
from multirag.vector_store import VectorStore


class QueryService:
    """Expone consultas RAG de forma reutilizable para endpoints HTTP."""

    def __init__(self, settings: Settings, gemini: GeminiClient, store: VectorStore) -> None:
        self.settings = settings
        self.gemini = gemini
        self.store = store

    def ask(self, question: str, retrieval_k: int | None = None) -> dict:
        """Responde una pregunta usando retrieval sobre Qdrant y Gemini para generacion."""

        if retrieval_k is None:
            return answer_question(
                settings=self.settings,
                gemini=self.gemini,
                store=self.store,
                question=question,
                on_stage=None,
            )

        # Sobrescribe retrieval_k de forma puntual sin mutar configuracion global.
        settings_override = replace(self.settings, retrieval_k=retrieval_k)
        return answer_question(
            settings=settings_override,
            gemini=self.gemini,
            store=self.store,
            question=question,
            on_stage=None,
        )
