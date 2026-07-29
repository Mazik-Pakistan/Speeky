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


# ── Pronunciation Coach (US-95) / Accent Assessment (US-93, US-89) ──────────────────
class UnreadableAudioError(AppError):
    """Upload isn't a readable/valid audio file (corrupt, empty, unsupported container)."""

    def __init__(self, message: str):
        super().__init__(message, 400)


class UploadTooLargeError(AppError):
    def __init__(self, message: str):
        super().__init__(message, 413)


class SentenceNotFoundError(AppError):
    def __init__(self, message: str):
        super().__init__(message, 404)


class PassageNotFoundError(AppError):
    def __init__(self, message: str):
        super().__init__(message, 404)


class NoCompletedAssessmentError(AppError):
    """US-89: profile/exercises requested before any completed Accent Assessment exists
    for this user — never returned as a silent default."""

    def __init__(self, message: str):
        super().__init__(message, 404)
