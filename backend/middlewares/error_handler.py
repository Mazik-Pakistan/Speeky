import traceback
from typing import cast
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from utils.app_error import AppError


class AuthError(Exception):
    """401 shape used by require_auth — original requireAuth returns res.json({error})
    directly, bypassing errorHandler.js entirely. Kept as its own exception/shape
    for that reason (see middlewares/auth_middleware.py)."""

    def __init__(self, message: str, status_code: int = 401):
        self.message = message
        self.status_code = status_code
        super().__init__(message)

async def app_error_handler(
    _request: Request,
    exc: Exception,
) -> JSONResponse:
    exc = cast(AppError, exc)
    # Errors raised as AppError (currently just the 404 catch-all in main.py).

    print({"message": exc.message, "stack": traceback.format_exc()})
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": exc.status,
            "message": exc.message,
        },
    )

async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    print({"message": str(exc), "stack": traceback.format_exc()})
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "Something went wrong!"},
    )


async def validation_error_handler(
    _request: Request,
    exc: Exception,
) -> JSONResponse:
    exc = cast(RequestValidationError, exc)

    field_errors: dict[str, list[str]] = {}

    for err in exc.errors():
        field = str(err["loc"][-1]) if err["loc"] else "_"
        field_errors.setdefault(field, []).append(err["msg"])

    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "formErrors": [],
                "fieldErrors": field_errors,
            }
        },
    )

async def auth_error_handler(
    _request: Request,
    exc: Exception,
) -> JSONResponse:
    exc = cast(AuthError, exc)

    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message},
    )