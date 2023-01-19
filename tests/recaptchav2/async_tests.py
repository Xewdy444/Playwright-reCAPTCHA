import unittest

from playwright.async_api import async_playwright

from playwright_recaptcha import (
    RecaptchaNotFoundError,
    RecaptchaRateLimitError,
    recaptchav2,
)


class TestRecaptchaSolver(unittest.IsolatedAsyncioTestCase):
    async def test_solver(self) -> None:
        async with async_playwright() as playwright:
            for playwright_browser in (
                playwright.chromium,
                playwright.firefox,
                playwright.webkit,
            ):
                browser = await playwright_browser.launch()
                page = await browser.new_page()
                await page.goto("https://www.google.com/recaptcha/api2")

                async with recaptchav2.AsyncSolver(page) as solver:
                    try:
                        token = await solver.solve_recaptcha()
                        self.assertIsNotNone(token)
                    except RecaptchaRateLimitError:
                        pass

    async def test_solver_with_slow_browser(self) -> None:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(slow_mo=1000)
            page = await browser.new_page()
            await page.goto("https://www.google.com/recaptcha/api2")

            async with recaptchav2.AsyncSolver(page) as solver:
                try:
                    token = await solver.solve_recaptcha()
                    self.assertIsNotNone(token)
                except RecaptchaRateLimitError:
                    pass

    async def test_recaptcha_not_found(self) -> None:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page()
            await page.goto("https://www.google.com/")

            with self.assertRaises(RecaptchaNotFoundError):
                async with recaptchav2.AsyncSolver(page) as solver:
                    await solver.solve_recaptcha()


if __name__ == "__main__":
    unittest.main()
