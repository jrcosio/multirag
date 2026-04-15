from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, UploadFile

from app.core.dependencies import get_cleanup_service, get_document_service
from app.domain.exceptions import ApiError
from app.schemas.documents import (
    DeleteAllResponse,
    DeleteDocumentResponse,
    DocumentItem,
    ListDocumentsResponse,
    UploadDocumentsResponse,
)
from app.services.cleanup_service import CleanupService
from app.services.document_service import DocumentService
from multirag.loader import IMAGE_EXTENSIONS, PDF_EXTENSIONS, TEXT_EXTENSIONS, WORD_EXTENSIONS

ALLOWED_UPLOAD_EXTENSIONS = TEXT_EXTENSIONS | PDF_EXTENSIONS | IMAGE_EXTENSIONS | WORD_EXTENSIONS
ALLOWED_UPLOAD_LABEL = ", ".join(sorted(ALLOWED_UPLOAD_EXTENSIONS))

router = APIRouter()


@router.post(
    "/upload",
    response_model=UploadDocumentsResponse,
    summary="Sube uno o varios documentos",
)
async def upload_documents(
    files: list[UploadFile] = File(..., description="Archivos soportados para almacenar e indexar."),
    document_service: DocumentService = Depends(get_document_service),
) -> UploadDocumentsResponse:
    """Recibe archivos por multipart, valida formato y los persiste en almacenamiento local."""

    prepared: list[tuple[str, bytes]] = []
    for file in files:
        name = file.filename or "document"
        extension = Path(name).suffix.lower()
        if extension not in ALLOWED_UPLOAD_EXTENSIONS:
            raise ApiError(
                code="invalid_file_type",
                message=(
                    "Formato no soportado. Extensiones permitidas: "
                    f"{ALLOWED_UPLOAD_LABEL}."
                ),
                status_code=400,
                details={"filename": name},
            )
        content = await file.read()
        if not content:
            raise ApiError(
                code="empty_file",
                message="No se permiten archivos vacios.",
                status_code=400,
                details={"filename": name},
            )
        prepared.append((name, content))

    uploaded = document_service.upload_documents(prepared)
    return UploadDocumentsResponse(
        uploaded=[
            DocumentItem(
                document_id=item.document_id,
                filename=item.filename,
                size_bytes=item.size_bytes,
                file_hash=item.file_hash,
                updated_at=item.updated_at,
                indexed=False,
            )
            for item in uploaded
        ]
    )


@router.get("", response_model=ListDocumentsResponse, summary="Lista documentos")
def list_documents(document_service: DocumentService = Depends(get_document_service)) -> ListDocumentsResponse:
    """Entrega todos los documentos disponibles con su estado actual de indexacion."""

    items = document_service.list_documents()
    response_items = [
        DocumentItem(
            document_id=item["document"].document_id,
            filename=item["document"].filename,
            size_bytes=item["document"].size_bytes,
            file_hash=item["document"].file_hash,
            updated_at=item["document"].updated_at,
            indexed=item["indexed"],
            processing_status=item["processing_status"],
            last_job_id=item["last_job_id"],
            last_error=item["last_error"],
            last_indexed_at=item["last_indexed_at"],
        )
        for item in items
    ]
    return ListDocumentsResponse(total=len(response_items), items=response_items)


@router.delete(
    "/{document_id:path}",
    response_model=DeleteDocumentResponse,
    summary="Borra un documento y su estado vectorial",
)
def delete_document(
    document_id: str,
    cleanup_service: CleanupService = Depends(get_cleanup_service),
    document_service: DocumentService = Depends(get_document_service),
) -> DeleteDocumentResponse:
    """Elimina un documento concreto de almacenamiento, estado incremental y vectores."""

    document_service.ensure_exists(document_id)
    result = cleanup_service.delete_document(document_id)
    return DeleteDocumentResponse(document_id=document_id, **result)


@router.delete("", response_model=DeleteAllResponse, summary="Borra toda la base vectorial y documentos")
def delete_all(
    confirm: bool = Query(False, description="Debe ser true para ejecutar borrado total."),
    cleanup_service: CleanupService = Depends(get_cleanup_service),
) -> DeleteAllResponse:
    """Ejecuta limpieza completa de coleccion, estado incremental y archivos almacenados."""

    if not confirm:
        raise ApiError(
            code="confirmation_required",
            message="Para borrar todo debes enviar confirm=true.",
            status_code=400,
        )
    result = cleanup_service.delete_all()
    return DeleteAllResponse(**result)
