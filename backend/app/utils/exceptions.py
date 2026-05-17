"""
Custom exception classes and FastAPI exception handlers.
"""

from fastapi import Request
from fastapi.responses import JSONResponse


# ── Custom Exceptions ──────────────────────────────────────────

class AppException(Exception):
    """Base application exception."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class NotFoundException(AppException):
    """Resource not found (404)."""

    def __init__(self, resource: str = "Resource", id: str = ""):
        detail = f"{resource} not found" + (f": {id}" if id else "")
        super().__init__(message=detail, status_code=404)


class DuplicateException(AppException):
    """Duplicate resource conflict (409)."""

    def __init__(self, resource: str = "Resource", field: str = ""):
        detail = f"{resource} already exists" + (f" (duplicate {field})" if field else "")
        super().__init__(message=detail, status_code=409)


class ValidationException(AppException):
    """Business logic validation error (422)."""

    def __init__(self, message: str):
        super().__init__(message=message, status_code=422)


class UnauthorizedException(AppException):
    """Authentication required (401)."""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(message=message, status_code=401)


# ── FastAPI Exception Handlers ─────────────────────────────────

async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Global handler for all AppException subclasses."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.message,
            "status_code": exc.status_code,
        },
    )
