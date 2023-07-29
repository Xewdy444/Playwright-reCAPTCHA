"""A library for solving reCAPTCHA v2 and v3 with Playwright."""

__author__ = "Xewdy444"
__version__ = "0.3.1"
__license__ = "MIT"

from playwright_recaptcha.errors import (
    CapSolverError,
    RecaptchaError,
    RecaptchaNotFoundError,
    RecaptchaRateLimitError,
    RecaptchaSolveError,
    RecaptchaTimeoutError,
)
from playwright_recaptcha.recaptchav2.async_solver import AsyncSolver as AsyncSolverV2
from playwright_recaptcha.recaptchav2.sync_solver import SyncSolver as SyncSolverV2
from playwright_recaptcha.recaptchav3.async_solver import AsyncSolver as AsyncSolverV3
from playwright_recaptcha.recaptchav3.sync_solver import SyncSolver as SyncSolverV3

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
