import pytest
from playwright.sync_api import sync_playwright

from playwright_recaptcha import RecaptchaTimeoutError, recaptchav3


def test_solver_with_normal_browser() -> None:
    """Test the solver with a normal browser."""
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch()
        page = browser.new_page()

        with recaptchav3.SyncSolver(page) as solver:
            page.goto("https://antcpt.com/score_detector/")
            solver.solve_recaptcha()


def test_solver_with_slow_browser() -> None:
    """Test the solver with a slow browser."""
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch(slow_mo=1000)
        page = browser.new_page()

        with recaptchav3.SyncSolver(page) as solver:
            page.goto("https://antcpt.com/score_detector/")
            solver.solve_recaptcha()


def test_recaptcha_not_found_error() -> None:
    """Test the solver with a page that does not have a reCAPTCHA."""
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch()
        page = browser.new_page()

        with pytest.raises(RecaptchaTimeoutError), recaptchav3.SyncSolver(
            page, timeout=10
        ) as solver:
            page.goto("https://www.google.com/")
            solver.solve_recaptcha()


def test_solver_with_blocked_token_requests() -> None:
    """Test the solver with blocked token requests."""
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch()
        page = browser.new_page()

        with recaptchav3.SyncSolver(page, block_token_requests=True) as solver:
            page.goto("https://antcpt.com/score_detector/")
            solver.solve_recaptcha()

        assert page.get_by_text("And error occurred, sorry!").is_visible()
