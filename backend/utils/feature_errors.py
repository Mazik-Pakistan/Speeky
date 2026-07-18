"""
Domain errors for the ported feature services, mapped onto AppError so the existing
app_error_handler (middlewares/error_handler.py) renders them with the right status.
Replaces the incoming code's app.core.exceptions.
"""

from utils.app_error import AppError


class SessionNotFoundError(AppError):
    def __init__(self, message: str):
        super().__init__(message, 404)


class InvalidSubmissionError(AppError):
    def __init__(self, message: str):
        super().__init__(message, 400)


class SessionAlreadyEndedError(AppError):
    def __init__(self, message: str):
        super().__init__(message, 409)


class RateLimitedError(AppError):
    def __init__(self, message: str):
        super().__init__(message, 429)
