from __future__ import annotations

import random
import time
from collections.abc import Callable

from google import genai
from google.genai import errors as genai_errors
from google.genai import types


class GeminiClient:
    """Encapsula acceso a Gemini para embeddings y generacion con reintentos."""

    def __init__(
        self,
        api_key: str,
        embedding_model: str,
        llm_model: str,
        output_dimensionality: int | None = None,
        max_retries: int = 6,
        base_delay_ms: int = 500,
        max_delay_ms: int = 10000,
        jitter_ms: int = 250,
    ) -> None:
        """Inicializa modelos y politicas de resiliencia usadas en todo el pipeline."""

        if not api_key:
            raise ValueError("Falta GEMINI_API_KEY en el entorno.")
        self.client = genai.Client(api_key=api_key)
        self.embedding_model = embedding_model
        self.llm_model = llm_model
        self.output_dimensionality = output_dimensionality
        self.max_retries = max(1, max_retries)
        self.base_delay_ms = max(50, base_delay_ms)
        self.max_delay_ms = max(1000, max_delay_ms)
        self.jitter_ms = max(0, jitter_ms)

    def embed_text(self, text: str) -> list[float]:
        """Obtiene el embedding de una consulta individual para busqueda vectorial."""

        vectors = self.embed_texts([text])
        if not vectors:
            raise RuntimeError("No se recibio embedding de Gemini.")
        return vectors[0]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Genera embeddings en lote para acelerar la indexacion de chunks textuales."""

        if not texts:
            return []

        contents = [types.Content(parts=[types.Part.from_text(text=text)]) for text in texts]
        config = self._embedding_config()
        response = self._with_retry(
            lambda: self.client.models.embed_content(
                model=self.embedding_model,
                contents=contents,
                config=config,
            ),
            operation="embedding",
        )

        return self._extract_embeddings(response, expected_count=len(texts), fallback_texts=texts)

    def embed_part(self, part: types.Part) -> list[float]:
        """Solicita un embedding multimodal para una entrada no textual."""

        content = types.Content(parts=[part])
        config = self._embedding_config()
        response = self._with_retry(
            lambda: self.client.models.embed_content(
                model=self.embedding_model,
                contents=[content],
                config=config,
            ),
            operation="embedding multimodal",
        )

        vectors = self._extract_embeddings(response, expected_count=1)
        if not vectors:
            raise RuntimeError("No se recibio embedding multimodal de Gemini.")
        return vectors[0]

    def embed_image_bytes(self, image_bytes: bytes, mime_type: str) -> list[float]:
        """Convierte una imagen en vector para habilitar recuperacion semantica visual."""

        return self.embed_part(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))

    def embed_pdf_bytes(self, pdf_bytes: bytes) -> list[float]:
        """Embebe un fragmento PDF directamente cuando el endpoint multimodal lo permite."""

        return self.embed_part(types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"))

    def embed_part_with_fallback(self, part: types.Part, fallback_text: str) -> list[float]:
        """Mantiene continuidad de ingesta al degradar a texto si falla el embedding multimodal."""

        try:
            return self.embed_part(part)
        except Exception:  # noqa: BLE001
            return self.embed_text(fallback_text)

    def _extract_embeddings(
        self,
        response: object,
        expected_count: int,
        fallback_texts: list[str] | None = None,
    ) -> list[list[float]]:
        """Normaliza respuestas de Gemini para devolver siempre vectores consistentes."""

        fallback = fallback_texts or []

        embeddings = getattr(response, "embeddings", None)
        if embeddings:
            out: list[list[float]] = []
            for item in embeddings:
                values = list(getattr(item, "values", []) or [])
                if not values:
                    raise RuntimeError("Respuesta de embedding vacia en lote.")
                out.append(values)
            if len(out) == expected_count:
                return out
            if len(out) == 1 and expected_count > 1 and fallback:
                return [self.embed_text(text) for text in fallback]
            raise RuntimeError(
                f"Gemini devolvio {len(out)} embeddings para {expected_count} entradas."
            )

        single = getattr(response, "embedding", None)
        if single and getattr(single, "values", None):
            if expected_count > 1 and fallback:
                return [self.embed_text(text) for text in fallback]
            return [list(single.values)]

        raise RuntimeError("No se recibieron embeddings de Gemini.")

    def _embedding_config(self) -> types.EmbedContentConfig | None:
        """Define opciones comunes de embedding para mantener dimensionalidad alineada."""

        if self.output_dimensionality is None:
            return None
        return types.EmbedContentConfig(output_dimensionality=self.output_dimensionality)

    def describe_image(self, image_bytes: bytes, mime_type: str, source_path: str) -> str:
        """Genera texto de apoyo para que imagenes recuperadas tengan contexto legible."""

        response = self._with_retry(
            lambda: self.client.models.generate_content(
                model=self.llm_model,
                contents=[
                    "Describe esta imagen para indexarla en un RAG. Incluye objetos, texto visible, contexto y palabras clave. Maximo 180 palabras.",
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                ],
            ),
            operation="descripcion de imagen",
        )

        text = (response.text or "").strip()
        if not text:
            return f"Imagen sin descripcion generada: {source_path}"
        return text

    def answer_with_context(self, question: str, context_blocks: list[str]) -> str:
        """Produce la respuesta final limitandose al contexto recuperado del indice."""

        context = "\n\n---\n\n".join(context_blocks)
        prompt = (
            "Responde usando solo el contexto proporcionado. "
            "Si no hay informacion suficiente, dilo claramente.\n\n"
            f"Contexto:\n{context}\n\n"
            f"Pregunta: {question}"
        )

        response = self._with_retry(
            lambda: self.client.models.generate_content(
                model=self.llm_model,
                contents=prompt,
            ),
            operation="generacion de respuesta",
        )
        return (response.text or "").strip()

    def _with_retry(self, call: Callable[[], object], operation: str) -> object:
        """Reintenta operaciones transitorias para reducir fallos por disponibilidad."""

        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                return call()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if not self._is_retryable_error(exc) or attempt == self.max_retries:
                    break
                sleep_sec = self._next_delay_seconds(attempt)
                time.sleep(sleep_sec)

        raise RuntimeError(f"Gemini fallo en {operation} tras {self.max_retries} intentos: {last_error}")

    def _next_delay_seconds(self, attempt: int) -> float:
        """Calcula la espera progresiva entre reintentos para estabilizar llamadas."""

        exponential_ms = self.base_delay_ms * (2 ** (attempt - 1))
        bounded_ms = min(exponential_ms, self.max_delay_ms)
        jitter = random.uniform(0, self.jitter_ms) if self.jitter_ms else 0
        return (bounded_ms + jitter) / 1000

    def _is_retryable_error(self, exc: Exception) -> bool:
        """Clasifica errores que conviene reintentar durante llamadas a Gemini."""

        if isinstance(exc, genai_errors.ServerError):
            status = getattr(exc, "status_code", None)
            if status in {500, 502, 503, 504}:
                return True
            return False

        if isinstance(exc, genai_errors.APIError):
            status = getattr(exc, "status_code", None)
            if status in {429, 500, 502, 503, 504}:
                return True

        message = str(exc).lower()
        transient_signals = ("timeout", "timed out", "connection", "temporarily", "unavailable")
        return any(token in message for token in transient_signals)
