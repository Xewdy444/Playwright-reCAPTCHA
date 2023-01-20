import pytest
from playwright.sync_api import sync_playwright

from playwright_recaptcha import (
    RecaptchaNotFoundError,
    RecaptchaRateLimitError,
    recaptchav2,
)


def test_solver() -> None:
    """Test the solver with a normal browser."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto("https://www.google.com/recaptcha/api2/demo")

        with recaptchav2.SyncSolver(page) as solver:
            try:
                token = solver.solve_recaptcha()
            except RecaptchaRateLimitError:
                return

            assert token is not None


def test_solver_with_slow_browser() -> None:
    """Test the solver with a slow browser."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(slow_mo=1000)
        page = browser.new_page()
        page.goto("https://www.google.com/recaptcha/api2/demo")

        with recaptchav2.SyncSolver(page) as solver:
            try:
                token = solver.solve_recaptcha()
            except RecaptchaRateLimitError:
                return

            assert token is not None

def test_recaptcha_not_found() -> None:
    """Test the solver with a page that does not have a reCAPTCHA."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto("https://www.google.com/")

        with pytest.raises(RecaptchaNotFoundError), recaptchav2.SyncSolver(
            page
        ) as solver:
            solver.solve_recaptcha()
