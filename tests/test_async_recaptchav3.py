import pytest
from playwright.async_api import async_playwright

from playwright_recaptcha import RecaptchaTimeoutError, recaptchav3


@pytest.mark.asyncio
async def test_solver_with_normal_browser() -> None:
    """Test the solver with a normal browser."""
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch()
        page = await browser.new_page()

        async with recaptchav3.AsyncSolver(page) as solver:
            await page.goto("https://antcpt.com/score_detector/")
            await solver.solve_recaptcha()


@pytest.mark.asyncio
async def test_solver_with_slow_browser() -> None:
    """Test the solver with a slow browser."""
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch(slow_mo=1000)
        page = await browser.new_page()

        async with recaptchav3.AsyncSolver(page) as solver:
            await page.goto("https://antcpt.com/score_detector/")
            await solver.solve_recaptcha()


@pytest.mark.asyncio
async def test_recaptcha_not_found_error() -> None:
    """Test the solver with a page that does not have a reCAPTCHA."""
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch()
        page = await browser.new_page()

        with pytest.raises(RecaptchaTimeoutError):
            async with recaptchav3.AsyncSolver(page, timeout=10) as solver:
                await page.goto("https://www.google.com/")
                await solver.solve_recaptcha()


@pytest.mark.asyncio
async def test_solver_with_blocked_token_requests() -> None:
    """Test the solver with blocked token requests."""
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch()
        page = await browser.new_page()

        async with recaptchav3.AsyncSolver(page, block_token_requests=True) as solver:
            await page.goto("https://antcpt.com/score_detector/")
            await solver.solve_recaptcha()

        assert await page.get_by_text("And error occurred, sorry!").is_visible()
