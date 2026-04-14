from __future__ import annotations


class ApiError(Exception):
    """Error de dominio con metadatos listos para responder por HTTP."""

    def __init__(self, code: str, message: str, status_code: int = 400, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class NotFoundError(ApiError):
    """Error para recursos inexistentes solicitados por el cliente."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(code="not_found", message=message, status_code=404, details=details)


class ConflictError(ApiError):
    """Error para estados incompatibles con la operacion solicitada."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(code="conflict", message=message, status_code=409, details=details)
