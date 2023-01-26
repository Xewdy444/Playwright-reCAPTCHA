"""reCAPTCHA v2 solver for Playwright."""
from playwright_recaptcha.recaptchav2.async_solver import AsyncSolver
from playwright_recaptcha.recaptchav2.sync_solver import SyncSolver

__all__ = ["AsyncSolver", "SyncSolver"]
