import pytest
from playwright.sync_api import sync_playwright

from playwright_recaptcha import (
    RecaptchaTimeoutError,
    RecaptchaVersionError,
    recaptchav3,
)


def test_solver() -> None:
    """Test the solver with a normal browser."""
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch()
        page = browser.new_page()
        page.goto("https://antcpt.com/score_detector/")

        with recaptchav3.SyncSolver(page) as solver:
            solver.solve_recaptcha()


def test_solver_with_slow_browser() -> None:
    """Test the solver with a slow browser."""
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch(slow_mo=1000)
        page = browser.new_page()
        page.goto("https://antcpt.com/score_detector/")

        with recaptchav3.SyncSolver(page) as solver:
            solver.solve_recaptcha()


def test_recaptcha_not_found() -> None:
    """Test the solver with a page that does not have a reCAPTCHA."""
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch()
        page = browser.new_page()
        page.goto("https://www.google.com/")

        with pytest.raises(RecaptchaTimeoutError), recaptchav3.SyncSolver(
            page, timeout=10
        ) as solver:
            solver.solve_recaptcha()


def test_recaptcha_version_error() -> None:
    """Test the solver with a page that has a reCAPTCHA v2."""
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch()
        page = browser.new_page()
        page.goto("https://cobra.ehr.com/ESS/Home/Login.aspx")

        with pytest.raises(RecaptchaVersionError), recaptchav3.SyncSolver(
            page
        ) as solver:
            solver.solve_recaptcha()
