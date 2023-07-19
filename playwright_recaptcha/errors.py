from typing import Optional


class CapSolverError(Exception):
    """An exception raised when the CapSolver API returns an error."""

    def __init__(self, message: Optional[str] = None) -> None:
        super().__init__(message or "The CapSolver API returned an error.")


class RecaptchaError(Exception):
    """Base class for reCAPTCHA exceptions."""


class RecaptchaNotFoundError(RecaptchaError):
    """An exception raised when the reCAPTCHA was not found."""

    def __init__(self, message: Optional[str] = None) -> None:
        super().__init__(message or "The reCAPTCHA was not found.")


class RecaptchaSolveError(RecaptchaError):
    """Base class for reCAPTCHA solve exceptions."""

    def __init__(self, message: Optional[str] = None) -> None:
        super().__init__(message or "The reCAPTCHA could not be solved.")


class RecaptchaRateLimitError(RecaptchaSolveError):
    """An exception raised when the reCAPTCHA rate limit has been exceeded."""

    def __init__(self) -> None:
        super().__init__("The reCAPTCHA rate limit has been exceeded.")


class RecaptchaTimeoutError(RecaptchaSolveError):
    """An exception raised when the reCAPTCHA solve timeout has been exceeded."""

    def __init__(self) -> None:
        super().__init__("The reCAPTCHA solve timeout has been exceeded.")
