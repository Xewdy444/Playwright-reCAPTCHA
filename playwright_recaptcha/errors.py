class RecaptchaError(Exception):
    """Base class for reCAPTCHA exceptions."""


class RecaptchaVersionError(RecaptchaError):
    """An exception raised when the reCAPTCHA is not version 3."""

    def __init__(self) -> None:
        super().__init__("The reCAPTCHA is not version 3.")


class RecaptchaNotFoundError(RecaptchaError):
    """An exception raised when the reCAPTCHA was not found."""

    def __init__(self) -> None:
        super().__init__("The reCAPTCHA was not found.")


class RecaptchaRateLimitError(RecaptchaError):
    """An exception raised when the reCAPTCHA rate limit has been reached."""

    def __init__(self) -> None:
        super().__init__("The reCAPTCHA rate limit has been reached.")


class RecaptchaSolveError(RecaptchaError):
    """An exception raised when the reCAPTCHA could not be solved."""

    def __init__(self) -> None:
        super().__init__("The reCAPTCHA could not be solved.")


class RecaptchaTimeoutError(RecaptchaError):
    """An exception raised when the reCAPTCHA solve timeout has been reached."""

    def __init__(self) -> None:
        super().__init__("The reCAPTCHA solve timeout has been reached.")
