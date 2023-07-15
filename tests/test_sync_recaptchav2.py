import pytest
from playwright.sync_api import sync_playwright

from playwright_recaptcha import (
    CapSolverError,
    RecaptchaNotFoundError,
    RecaptchaRateLimitError,
    recaptchav2,
)


@pytest.mark.xfail(raises=RecaptchaRateLimitError)
def test_solver_with_normal_recaptcha() -> None:
    """Test the solver with a normal reCAPTCHA."""
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch()
        page = browser.new_page()
        page.goto("https://www.google.com/recaptcha/api2/demo")

        with recaptchav2.SyncSolver(page) as solver:
            solver.solve_recaptcha(wait=True)


@pytest.mark.xfail(raises=(RecaptchaNotFoundError, RecaptchaRateLimitError))
def test_solver_with_hidden_recaptcha() -> None:
    """Test the solver with a hidden reCAPTCHA."""
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch()
        page = browser.new_page()

        page.goto("https://www.google.com/recaptcha/api2/demo?invisible=true")
        page.get_by_role("button").click()

        with recaptchav2.SyncSolver(page) as solver:
            solver.solve_recaptcha(wait=True)


@pytest.mark.xfail(raises=RecaptchaRateLimitError)
def test_solver_with_slow_browser() -> None:
    """Test the solver with a slow browser."""
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch(slow_mo=1000)
        page = browser.new_page()
        page.goto("https://www.google.com/recaptcha/api2/demo")

        with recaptchav2.SyncSolver(page) as solver:
            solver.solve_recaptcha(wait=True)


@pytest.mark.xfail(raises=CapSolverError)
def test_solver_with_image_challenge() -> None:
    """Test the solver with an image challenge."""
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch()
        page = browser.new_page()
        page.goto("https://www.google.com/recaptcha/api2/demo")

        with recaptchav2.SyncSolver(page) as solver:
            solver.solve_recaptcha(wait=True, image_challenge=True)


def test_recaptcha_not_found_error() -> None:
    """Test the solver with a page that does not have a reCAPTCHA."""
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch()
        page = browser.new_page()
        page.goto("https://www.google.com/")

        with pytest.raises(RecaptchaNotFoundError), recaptchav2.SyncSolver(
            page
        ) as solver:
            solver.solve_recaptcha()
