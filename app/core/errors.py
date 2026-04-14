from __future__ import annotations

import uuid

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.domain.exceptions import ApiError


def _request_id(request: Request) -> str:
    """Garantiza un id de trazabilidad por respuesta de error."""

    return request.headers.get("x-request-id") or str(uuid.uuid4())


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    """Mapea errores de dominio a respuestas HTTP estandar."""

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
            "request_id": _request_id(request),
        },
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Transforma validaciones de FastAPI en formato uniforme de error."""

    return JSONResponse(
        status_code=422,
        content={
            "code": "validation_error",
            "message": "La solicitud no cumple el esquema esperado.",
            "details": {"errors": exc.errors()},
            "request_id": _request_id(request),
        },
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Protege la API con una salida estable para fallos no controlados."""

    return JSONResponse(
        status_code=500,
        content={
            "code": "internal_error",
            "message": "Se produjo un error interno.",
            "details": {"error": str(exc)},
            "request_id": _request_id(request),
        },
    )
