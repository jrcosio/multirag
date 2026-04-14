from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DocumentItem(BaseModel):
    """Representa un documento administrado por la API."""

    document_id: str = Field(description="Identificador del documento (ruta relativa).")
    filename: str = Field(description="Nombre base del archivo.")
    size_bytes: int = Field(description="Tamano del archivo en bytes.")
    file_hash: str = Field(description="Huella SHA-256 del archivo.")
    updated_at: datetime = Field(description="Fecha de ultima modificacion en UTC.")
    indexed: bool = Field(description="Indica si el hash actual ya fue indexado.")
    processing_status: str = Field(default="not_started", description="Estado de procesamiento del documento.")
    last_job_id: str | None = Field(default=None, description="Ultimo job asociado al documento.")
    last_error: str | None = Field(default=None, description="Ultimo error de indexacion si fallo.")
    last_indexed_at: datetime | None = Field(default=None, description="Fecha del ultimo indexado exitoso.")


class UploadDocumentsResponse(BaseModel):
    """Respuesta de subida de documentos."""

    uploaded: list[DocumentItem]


class ListDocumentsResponse(BaseModel):
    """Respuesta paginable simple para listado de documentos."""

    total: int
    items: list[DocumentItem]


class DeleteDocumentResponse(BaseModel):
    """Detalle de borrado por documento."""

    document_id: str
    vectors_deleted: bool
    state_deleted: bool
    file_deleted: bool


class DeleteAllResponse(BaseModel):
    """Detalle de borrado completo de datos y estado."""

    collection_deleted: bool
    state_cleared: bool
    files_deleted: int
