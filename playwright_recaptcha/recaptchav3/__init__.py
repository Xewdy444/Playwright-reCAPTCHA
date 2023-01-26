"""reCAPTCHA v3 solver for Playwright."""
from playwright_recaptcha.recaptchav3.async_solver import AsyncSolver
from playwright_recaptcha.recaptchav3.sync_solver import SyncSolver

__all__ = ["AsyncSolver", "SyncSolver"]
