from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Estructura estandar para errores de la API."""

    code: str = Field(description="Codigo interno de error.")
    message: str = Field(description="Descripcion legible del error.")
    details: dict = Field(default_factory=dict, description="Contexto adicional del error.")
    request_id: str = Field(description="Identificador de trazabilidad de la solicitud.")


class MessageResponse(BaseModel):
    """Respuesta simple para operaciones de confirmacion."""

    message: str
