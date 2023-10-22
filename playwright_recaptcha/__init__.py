"""A library for solving reCAPTCHA v2 and v3 with Playwright."""

__author__ = "Xewdy444"
__version__ = "0.4.1"
__license__ = "MIT"

from .errors import (
    CapSolverError,
    RecaptchaError,
    RecaptchaNotFoundError,
    RecaptchaRateLimitError,
    RecaptchaSolveError,
    RecaptchaTimeoutError,
)
from .recaptchav2 import AsyncSolver as AsyncSolverV2
from .recaptchav2 import SyncSolver as SyncSolverV2
from .recaptchav3 import AsyncSolver as AsyncSolverV3
from .recaptchav3 import SyncSolver as SyncSolverV3

__all__ = [
    "CapSolverError",
    "RecaptchaError",
    "RecaptchaNotFoundError",
    "RecaptchaRateLimitError",
    "RecaptchaSolveError",
    "RecaptchaTimeoutError",
    "AsyncSolverV2",
    "SyncSolverV2",
    "AsyncSolverV3",
    "SyncSolverV3",
]
