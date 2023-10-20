"""reCAPTCHA v3 solver for Playwright."""
from .async_solver import AsyncSolver
from .sync_solver import SyncSolver

__all__ = ["AsyncSolver", "SyncSolver"]
