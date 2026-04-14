from __future__ import annotations

from qdrant_client import QdrantClient
from qdrant_client.http import models

from multirag.types import Chunk


class VectorStore:
    """Abstrae operaciones de persistencia y consulta sobre Qdrant."""

    def __init__(self, url: str, collection_name: str) -> None:
        """Conecta con Qdrant y fija la coleccion objetivo del proyecto."""

        self.client = QdrantClient(url=url)
        self.collection_name = collection_name

    def ensure_collection(self, vector_size: int) -> None:
        """Garantiza que exista una coleccion compatible con la dimension de embeddings."""

        exists = self.client.collection_exists(collection_name=self.collection_name)
        if exists:
            return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
        )

    def collection_exists(self) -> bool:
        """Indica si la coleccion objetivo existe actualmente en Qdrant."""

        return self.client.collection_exists(collection_name=self.collection_name)

    def delete_collection(self) -> bool:
        """Borra la coleccion completa de Qdrant y devuelve si existia."""

        if not self.collection_exists():
            return False
        self.client.delete_collection(collection_name=self.collection_name)
        return True

    def remove_source(self, source_path: str) -> None:
        """Elimina vectores previos de una fuente para evitar duplicados tras reingesta."""

        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="source_path",
                            match=models.MatchValue(value=source_path),
                        )
                    ]
                )
            ),
            wait=True,
        )

    def upsert_chunks(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        """Inserta o actualiza chunks junto con metadatos utiles para recuperacion."""

        points: list[models.PointStruct] = []
        for chunk, vector in zip(chunks, vectors, strict=True):
            payload = {
                "text": chunk.text,
                "surrogate_text": chunk.surrogate_text or chunk.text,
                "source_path": chunk.source_path,
                "modality": chunk.modality,
                "chunk_index": chunk.chunk_index,
                "file_hash": chunk.file_hash,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "start_sec": chunk.start_sec,
                "end_sec": chunk.end_sec,
                "media_mime": chunk.media_mime,
                "media_kind": chunk.media_kind,
            }
            points.append(models.PointStruct(id=chunk.id, vector=vector, payload=payload))

        self.client.upsert(collection_name=self.collection_name, points=points, wait=True)

    def search(self, query_vector: list[float], limit: int) -> list[dict]:
        """Recupera los fragmentos mas similares que alimentan la respuesta final."""

        try:
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=limit,
                with_payload=True,
            )
            points = response.points
        except AttributeError:
            points = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit,
                with_payload=True,
            )

        results: list[dict] = []
        for point in points:
            payload = point.payload or {}
            results.append(
                {
                    "score": getattr(point, "score", 0.0),
                    "text": payload.get("text", ""),
                    "surrogate_text": payload.get("surrogate_text", payload.get("text", "")),
                    "source_path": payload.get("source_path", "desconocido"),
                    "modality": payload.get("modality", "unknown"),
                    "chunk_index": payload.get("chunk_index", -1),
                    "page_start": payload.get("page_start"),
                    "page_end": payload.get("page_end"),
                    "start_sec": payload.get("start_sec"),
                    "end_sec": payload.get("end_sec"),
                    "media_kind": payload.get("media_kind"),
                }
            )
        return results
