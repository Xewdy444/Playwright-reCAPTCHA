"""A libary for solving reCAPTCHA v2 and v3 with Playwright."""
from playwright_recaptcha.errors import (
    RecaptchaError,
    RecaptchaNotFoundError,
    RecaptchaRateLimitError,
    RecaptchaSolveError,
    RecaptchaTimeoutError,
    RecaptchaVersionError,
)
from playwright_recaptcha.recaptchav2.async_solver import AsyncSolver as AsyncSolverV2
from playwright_recaptcha.recaptchav2.sync_solver import SyncSolver as SyncSolverV2
from playwright_recaptcha.recaptchav3.async_solver import AsyncSolver as AsyncSolverV3
from playwright_recaptcha.recaptchav3.sync_solver import SyncSolver as SyncSolverV3

__all__ = [
    "RecaptchaError",
    "RecaptchaNotFoundError",
    "RecaptchaRateLimitError",
    "RecaptchaSolveError",
    "RecaptchaTimeoutError",
    "RecaptchaVersionError",
    "AsyncSolverV2",
    "SyncSolverV2",
    "AsyncSolverV3",
    "SyncSolverV3",
]
