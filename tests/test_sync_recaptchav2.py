import pytest
from playwright.sync_api import sync_playwright

from playwright_recaptcha import (
    RecaptchaNotFoundError,
    RecaptchaRateLimitError,
    recaptchav2,
)


@pytest.mark.xfail(raises=RecaptchaRateLimitError)
def test_solver() -> None:
    """Test the solver with a normal browser."""
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch()
        page = browser.new_page()

        page.goto(
            "https://www.google.com/recaptcha/api2/demo", wait_until="networkidle"
        )

        with recaptchav2.SyncSolver(page) as solver:
            solver.solve_recaptcha()


@pytest.mark.xfail(raises=RecaptchaRateLimitError)
def test_solver_with_slow_browser() -> None:
    """Test the solver with a slow browser."""
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch(slow_mo=1000)
        page = browser.new_page()

        page.goto(
            "https://www.google.com/recaptcha/api2/demo", wait_until="networkidle"
        )

        with recaptchav2.SyncSolver(page) as solver:
            solver.solve_recaptcha()


def test_recaptcha_not_found() -> None:
    """Test the solver with a page that does not have a reCAPTCHA."""
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch()
        page = browser.new_page()
        page.goto("https://www.google.com/")

        with pytest.raises(RecaptchaNotFoundError), recaptchav2.SyncSolver(
            page
        ) as solver:
            solver.solve_recaptcha()
