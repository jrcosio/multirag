from __future__ import annotations

from copy import deepcopy

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi

from app.api.v1.router import api_router
from app.core.errors import api_error_handler, generic_error_handler, validation_error_handler
from app.domain.exceptions import ApiError


def create_app() -> FastAPI:
    """Construye la aplicacion FastAPI con rutas y handlers globales."""

    app = FastAPI(
        title="MultiRAG API",
        version="1.0.0",
        description=(
            "API para ingesta multimodal, vectorizacion asincrona y consultas RAG sobre Qdrant + Gemini."
        ),
    )
    app.include_router(api_router, prefix="/api/v1")
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, generic_error_handler)
    app.openapi = _build_custom_openapi(app)
    return app


def _build_custom_openapi(app: FastAPI):
    """Genera OpenAPI compatible con selector de archivos en Swagger UI."""

    def custom_openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        patched = deepcopy(schema)
        _patch_binary_fields(patched)
        app.openapi_schema = patched
        return app.openapi_schema

    return custom_openapi


def _patch_binary_fields(node: object) -> None:
    """Convierte contentMediaType octet-stream a format=binary para Swagger UI."""

    if isinstance(node, dict):
        if node.get("type") == "string" and node.get("contentMediaType") == "application/octet-stream":
            node.pop("contentMediaType", None)
            node["format"] = "binary"
        for value in node.values():
            _patch_binary_fields(value)
        return

    if isinstance(node, list):
        for item in node:
            _patch_binary_fields(item)


app = create_app()
