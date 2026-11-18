"""Central mapping from domain exceptions to HTTP responses.

Every error response has the same shape:
    {"error": {"code": str, "message": str, "fields": [...]?}}
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    AuralisError,
    ExplanationError,
    ExtractionError,
    InvalidFileError,
    InvalidReadingError,
    NotFoundError,
)
from app.core.logging_config import get_logger

logger = get_logger("api.errors")

DEFAULT_STATUS = 500


def status_for(exc: AuralisError) -> int:  # pylint: disable=too-many-return-statements
    """Return the HTTP status for an error."""
    if isinstance(exc, InvalidReadingError):
        return 422
    if isinstance(exc, NotFoundError):
        return 404
    if isinstance(exc, InvalidFileError):
        return 400
    if isinstance(exc, ExtractionError):
        return 422
    if isinstance(exc, ExplanationError):
        return 502
    return DEFAULT_STATUS


def _error_body(code: str, message: str, fields: list[dict] | None = None) -> dict:
    error: dict = {"code": code, "message": message}
    if fields is not None:
        error["fields"] = fields
    return {"error": error}


async def handle_auralis_error(request: Request, exc: AuralisError) -> JSONResponse:
    """Translate an expected domain error into its mapped status code."""
    status = status_for(exc)
    logger.warning("%s %s -> %s %s: %s", request.method, request.url.path,
                   status, exc.code, exc.message)
    return JSONResponse(status_code=status, content=_error_body(exc.code, exc.message))


async def handle_validation_error(request: Request,
                                  exc: RequestValidationError) -> JSONResponse:
    """Return schema errors per field so the frontend can show them next to the field."""
    fields = [
        {
            "field": ".".join(str(part) for part in err["loc"] if part != "body"),
            "message": err["msg"],
        }
        for err in exc.errors()
    ]
    logger.info("%s %s -> 422 validation_error: %s", request.method,
                request.url.path, fields)
    return JSONResponse(
        status_code=422,
        content=_error_body("validation_error", "Request data is invalid.", fields),
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Log the full traceback but never leak internal details to the client."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path,
                     exc_info=exc)
    return JSONResponse(
        status_code=DEFAULT_STATUS,
        content=_error_body("internal_error", "An unexpected error occurred."),
    )


def register_error_handlers(app: FastAPI) -> None:
    """Attach all handlers to the application."""
    app.add_exception_handler(AuralisError, handle_auralis_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
