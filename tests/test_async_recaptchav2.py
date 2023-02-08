import pytest
from playwright.async_api import async_playwright

from playwright_recaptcha import (
    RecaptchaNotFoundError,
    RecaptchaRateLimitError,
    recaptchav2,
)


@pytest.mark.asyncio
@pytest.mark.xfail(raises=RecaptchaRateLimitError)
async def test_solver() -> None:
    """Test the solver with a normal browser."""
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch()
        page = await browser.new_page()
        await page.goto("https://www.google.com/recaptcha/api2/demo")

        async with recaptchav2.AsyncSolver(page) as solver:
            await solver.solve_recaptcha()


@pytest.mark.asyncio
@pytest.mark.xfail(raises=RecaptchaRateLimitError)
async def test_solver_with_slow_browser() -> None:
    """Test the solver with a slow browser."""
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch(slow_mo=1000)
        page = await browser.new_page()
        await page.goto("https://www.google.com/recaptcha/api2/demo")

        async with recaptchav2.AsyncSolver(page) as solver:
            await solver.solve_recaptcha()


@pytest.mark.asyncio
async def test_recaptcha_not_found() -> None:
    """Test the solver with a page that does not have a reCAPTCHA."""
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch()
        page = await browser.new_page()
        await page.goto("https://www.google.com/")

        with pytest.raises(RecaptchaNotFoundError):
            async with recaptchav2.AsyncSolver(page) as solver:
                await solver.solve_recaptcha()
