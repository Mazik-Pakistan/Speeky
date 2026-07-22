class AppError(Exception):
    """Operational error (message safe to show to client). Port of utils/app_error.js."""

    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.status = "fail" if str(status_code).startswith("4") else "error"
        self.is_operational = True


# ponytail: catchAsync had no equivalent needed — FastAPI, like Express 5, already
# propagates exceptions raised inside `async def` route handlers to the error
# handlers registered in middlewares/error_handler.py.
